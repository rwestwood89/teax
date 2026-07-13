"""Item-0 integration spike driver: S6 lifecycle x S5 evaluator x S4 package.

THROWAWAY SPIKE CODE. Reuses S6's `study_lifecycle.py` machinery AS-IS (imported,
never edited): StudyStore, StudyRunner, DeterministicPolicy, PreparedCandidate-
Strategy, Compatibility, CrashController. The only substitutions are the ones the
concept requires at this seam:

  * the evaluator: S6's FakeEvaluator -> RealPreparedEvaluator over S4's package;
  * the domain validator: S6's fake `kind`/`x` rule -> a real budget-point rule,
    installed by MONKEYPATCHING the module global (no edit to the S6 file). This
    swap is itself a named finding: StudyRunner.run() hard-references the module
    global `validate_and_canonicalize`, so "reuse as-is" needs either a patch
    (here) or an injected validation seam (production).

Subcommands:
  run    --db PATH [--crash-at PHASE:CANDIDATE_ID]   one runner pass (child process)
  verify [--workroot DIR]                            uninterrupted vs crash+resume
  bench  [--n N]                                     prepare-once vs rebuild timing

Run under a licensed host venv with simkit on the path:
    PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit \
      /home/reid/1cfe/fusion-tea/.venv/bin/python integration_probe.py verify
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Optional

HERE = Path(__file__).resolve().parent
S6_DIR = Path("/home/reid/1cfe/teax/.project/active/spike-crash-safe-study-lifecycle")
for p in (str(S6_DIR), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import study_lifecycle as sl  # noqa: E402  (S6 machinery, imported as-is)
from real_evaluator import RealPreparedEvaluator, verify_seal  # noqa: E402


# --------------------------------------------------------------------------
# Real study definition: budget points over S4's toy plant (cost is fixed 3000)
# --------------------------------------------------------------------------

# Order is meaningful and stable (prepared-candidates strategy).
REAL_PROPOSALS: list[dict] = [
    {"budget": 5000.0},    # 0 -> completed / feasible      (3000 <= 5000 satisfied)
    {"budget": 2500.0},    # 1 -> completed / infeasible    (3000 <= 2500 violated)
    {"budget": "nan"},     # 2 -> completed / indeterminate (3000 <= NaN -> unknown)
    {"currency": "USD"},   # 3 -> INVALID proposal (no budget key) -> ProposalRecord
    {"budget": 5000.0},    # 4 -> replicate of 0 (distinct candidate_id, same inputs)
]

STUDY_ID = "study-item0-real"
_NONFINITE = {"nan", "inf", "-inf", "infinity", "-infinity"}


def real_validate_and_canonicalize(raw: Mapping[str, Any]) -> Optional[dict]:
    """A well-formed candidate carries a numeric `budget`.

    Crucially, a NON-FINITE budget is VALID here: the model can evaluate it
    (Kleene -> indeterminate). "Is this a well-formed candidate" and "does its
    verdict come back indeterminate" are different axes. Invalid means malformed
    (missing/garbage), never merely non-finite -- this is the exact conflation
    S6's fake `kind`/`x` rule made, and the reason it cannot express the
    indeterminate class.
    """
    budget = raw.get("budget")
    if isinstance(budget, bool):  # bool is an int subclass; reject it explicitly
        return None
    if isinstance(budget, (int, float)):
        return {"budget": float(budget)}
    if isinstance(budget, str) and budget.strip().lower() in _NONFINITE:
        return {"budget": budget.strip().lower()}  # JSON-clean sentinel; float in evaluator
    return None


def real_compatibility() -> "sl.Compatibility":
    strategy = sl.PreparedCandidateStrategy(REAL_PROPOSALS)
    fingerprint = verify_seal()
    return sl.Compatibility(
        study_id=STUDY_ID,
        executable_fingerprint=fingerprint,               # the REAL sealed fingerprint
        model_contract_fingerprint="659d0298caaa51ac4f4f9bee5ecde14d9ef929cf5c8ced3ca2e7857bce87d00f",
        study_definition_fingerprint=sl.digest_of(REAL_PROPOSALS),
        input_schema_version="input-v1",
        evidence_schema_version="evidence-v1",
        strategy_identity=strategy.identity,
        strategy_config=strategy.config_fingerprint(),
    )


def run_study(db_path: Path, crash_spec: Optional[str]) -> None:
    # Install the real domain validator into the S6 module global (no file edit).
    sl.validate_and_canonicalize = real_validate_and_canonicalize
    compat = real_compatibility()
    store = sl.StudyStore.create_or_open(db_path, compat)
    runner = sl.StudyRunner(
        store,
        sl.PreparedCandidateStrategy(REAL_PROPOSALS),
        RealPreparedEvaluator(),
        sl.DeterministicPolicy(),
        sl.CrashController(crash_spec),
    )
    try:
        runner.run()
    finally:
        store.close()


# --------------------------------------------------------------------------
# Read helpers (raw sqlite, no compat coupling)
# --------------------------------------------------------------------------

def _rows(db: Path, sql: str) -> list[dict]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def ordered_cases_stable(db: Path) -> list[dict]:
    """Cases in commit order, excluding attempt_id (differs after a resume)."""
    out = []
    for r in _rows(db, "SELECT * FROM cases ORDER BY commit_order"):
        out.append({
            "candidate_id": r["candidate_id"],
            "proposal_id": r["proposal_id"],
            "state": r["state"],
            "inputs_json": r["inputs_json"],
            "evidence_digest": r["evidence_digest"],
            "assessment_json": r["assessment_json"],
        })
    return out


def referenced_artifacts_present(db: Path) -> bool:
    art_dir = db.parent / "artifacts"
    digests = {r["evidence_digest"] for r in _rows(db, "SELECT evidence_digest FROM cases")}
    return all((art_dir / f"{d}.json").exists() for d in digests)


# --------------------------------------------------------------------------
# verify: uninterrupted vs crash+resume
# --------------------------------------------------------------------------

def _child(db: Path, crash_at: Optional[str]) -> int:
    cmd = [sys.executable, str(HERE / "integration_probe.py"), "run", "--db", str(db)]
    if crash_at:
        cmd += ["--crash-at", crash_at]
    return subprocess.run(cmd).returncode


def verify(workroot: Path) -> int:
    if workroot.exists():
        shutil.rmtree(workroot)
    checks: list[tuple[str, bool]] = []
    ok = lambda name, cond: checks.append((name, bool(cond)))  # noqa: E731

    # -- leg 1: uninterrupted --
    d1 = workroot / "uninterrupted"
    d1.mkdir(parents=True)
    rc1 = _child(d1 / "study.db", None)
    ok("uninterrupted run exited 0", rc1 == 0)
    cases1 = ordered_cases_stable(d1 / "study.db")

    # -- leg 2: crash before committing the indeterminate candidate, then resume --
    d2 = workroot / "crash_resume"
    d2.mkdir(parents=True)
    crash_candidate = f"{STUDY_ID}:c0002"  # the non-finite / indeterminate point
    rc_crash = _child(d2 / "study.db", f"before_commit:{crash_candidate}")
    ok("crash child exited 137", rc_crash == 137)
    cases_mid = ordered_cases_stable(d2 / "study.db")
    ok("crash left the crashed candidate uncommitted",
       crash_candidate not in {c["candidate_id"] for c in cases_mid})
    rc_resume = _child(d2 / "study.db", None)
    ok("resume run exited 0", rc_resume == 0)
    cases2 = ordered_cases_stable(d2 / "study.db")

    # -- resume reproduces the uninterrupted run --
    ok("resumed ordered cases == uninterrupted (attempt_id excluded)", cases1 == cases2)

    # -- three verdict classes each land as a completed case with correct evidence --
    by_cand = {c["candidate_id"]: c for c in cases1}
    def _evidence(digest: str) -> dict:
        return json.loads((d1 / "artifacts" / f"{digest}.json").read_text())

    want = {
        f"{STUDY_ID}:c0000": ("completed", "all-satisfied", "satisfied"),
        f"{STUDY_ID}:c0001": ("completed", "violation", "violated"),
        f"{STUDY_ID}:c0002": ("completed", "indeterminate", "indeterminate"),
        f"{STUDY_ID}:c0004": ("completed", "all-satisfied", "satisfied"),
    }
    for cand, (state, headline, status) in want.items():
        row = by_cand.get(cand)
        present = row is not None
        ok(f"{cand} present as a case", present)
        if not present:
            continue
        ok(f"{cand} state == {state}", row["state"] == state)
        ev = _evidence(row["evidence_digest"])
        ok(f"{cand} report headline == {headline}", ev["report"]["headline"] == headline)
        ok(f"{cand} constraint status == {status}",
           ev["report"]["constraints"][0]["status"] == status)
        # every completed verdict rides on real ordinary outputs (cost fixed 3000)
        ok(f"{cand} carries real ordinary outputs (cost=3000)", ev["outputs"]["cost"] == 3000.0)

    # indeterminate specifics: actual_value None, budget operand a non-finite tag
    ind = _evidence(by_cand[f"{STUDY_ID}:c0002"]["evidence_digest"])
    con = ind["report"]["constraints"][0]
    ok("indeterminate actual_value is null", con["actual_value"] is None)
    ok("indeterminate margin is null", con["margin"] is None)
    ok("indeterminate operand budget tagged non-finite",
       con["observed"]["budget"] == {"__nonfinite__": "nan"})

    # -- invalid proposal stays a ProposalRecord, never a candidate/case --
    props = {p["proposal_id"]: p for p in _rows(d1 / "study.db", "SELECT * FROM proposals")}
    invalid_pid = f"{STUDY_ID}:p0003"
    inv = props.get(invalid_pid)
    ok("invalid proposal recorded", inv is not None)
    if inv is not None:
        ok("invalid proposal marked invalid", inv["valid"] == 0)
        ok("invalid proposal has no candidate_id", inv["candidate_id"] is None)
    ok("invalid proposal has no case",
       not any(c["proposal_id"] == invalid_pid for c in cases1))

    # -- replicate: distinct candidate_id, identical inputs, shared artifact --
    c0 = by_cand[f"{STUDY_ID}:c0000"]
    c4 = by_cand[f"{STUDY_ID}:c0004"]
    ok("replicate has distinct candidate_id", c0["candidate_id"] != c4["candidate_id"])
    ok("replicate has identical inputs", c0["inputs_json"] == c4["inputs_json"])
    ok("replicate shares one content-addressed artifact",
       c0["evidence_digest"] == c4["evidence_digest"])

    # -- no committed case references a missing artifact (both legs) --
    ok("uninterrupted: all referenced artifacts present", referenced_artifacts_present(d1 / "study.db"))
    ok("crash+resume: all referenced artifacts present", referenced_artifacts_present(d2 / "study.db"))

    # -- idempotency: no logical candidate committed twice --
    dupes = _rows(d2 / "study.db",
                  "SELECT candidate_id, COUNT(*) n FROM cases GROUP BY candidate_id HAVING n > 1")
    ok("no candidate committed twice under (study_id, candidate_id)", not dupes)
    # the crashed candidate's crashed attempt is preserved in append-only history
    att = _rows(d2 / "study.db",
                f"SELECT * FROM attempts WHERE candidate_id = '{crash_candidate}' ORDER BY attempt_number")
    ok("crashed candidate has >=2 attempts (a1 crashed, a2 committed)", len(att) >= 2)

    # -- incompatible reopen fails --
    reopen_ok = False
    try:
        bad = sl.Compatibility(**{**real_compatibility().__dict__,
                                  "executable_fingerprint": "TAMPERED"})
        sl.StudyStore.create_or_open(d1 / "study.db", bad)
    except sl.IncompatibleStore:
        reopen_ok = True
    ok("incompatible-fingerprint reopen raises IncompatibleStore", reopen_ok)

    passed = sum(1 for _, c in checks if c)
    print(f"\n=== verify: {passed}/{len(checks)} checks ===")
    for name, cond in checks:
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    all_ok = passed == len(checks)
    print("\nINTEGRATION VERIFY " + ("PASSED" if all_ok else "FAILED"))
    return 0 if all_ok else 1


# --------------------------------------------------------------------------
# bench: prepare-once vs rebuild on the REAL package (S5 carry-forward 2)
# --------------------------------------------------------------------------

def bench(n: int) -> int:
    import real_evaluator as re_mod

    verify_seal()
    package = re_mod.load_package()
    ToyPlantParams = package.ToyPlantParams
    budgets = [3000.0 + 10.0 * i for i in range(n)]  # straddles the 3000 boundary

    def make_params(b: float):
        return ToyPlantParams(
            toy_plant__Toy_Plant__plant_budget=b,
            toy_plant__Toy_Plant__plant_length=4.0,
            toy_plant__Toy_Plant__plant_unit_cost=250.0,
            toy_plant__Toy_Plant__plant_width=3.0,
        )

    # prepare-once
    t0 = perf_counter()
    executor, graph, registry, source, MappingContext = re_mod._build_prepared(package)
    prepare_seconds = perf_counter() - t0

    def run_once(exec_, graph_, reg_, src_, ctx_cls, b):
        validated = src_.validate({re_mod.ENTRY_CH: make_params(b)})
        context = ctx_cls(reg_, validated)
        return exec_.run(graph_, context, persist_outputs=False)

    t0 = perf_counter()
    prepared_results = [run_once(executor, graph, registry, source, MappingContext, b) for b in budgets]
    prepared_seconds = perf_counter() - t0

    # rebuild-per-case (validate + build topology every time)
    t0 = perf_counter()
    rebuilt_results = []
    for b in budgets:
        ex, gr, rg, sr, cc = re_mod._build_prepared(package)
        rebuilt_results.append(run_once(ex, gr, rg, sr, cc, b))
    rebuild_seconds = perf_counter() - t0

    # parity: identical verdict + margin per budget across the two paths
    def verdict(r):
        ev = dict(r.outputs)[re_mod.EVAL_CH]
        return (ev.status, ev.margin, dict(r.outputs)[re_mod.COST_CH].root)
    parity = sum(verdict(a) == verdict(b) for a, b in zip(prepared_results, rebuilt_results))

    speedup = rebuild_seconds / prepared_seconds
    report = {
        "package": re_mod.PACKAGE_NAME,
        "executable_fingerprint": verify_seal(),
        "n_cases": n,
        "prepare_once_ms": round(prepare_seconds * 1000, 3),
        "prepared_eval_total_ms": round(prepared_seconds * 1000, 3),
        "rebuild_eval_total_ms": round(rebuild_seconds * 1000, 3),
        "prepared_per_case_ms": round(prepared_seconds / n * 1000, 4),
        "rebuild_per_case_ms": round(rebuild_seconds / n * 1000, 4),
        "prepare_once_speedup_over_rebuild": round(speedup, 3),
        "prepare_once_materially_faster_1_25x": speedup >= 1.25,
        "prepared_vs_rebuild_parity_cases": parity,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if parity == n else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("run")
    rp.add_argument("--db", required=True)
    rp.add_argument("--crash-at", default=None)
    vp = sub.add_parser("verify")
    vp.add_argument("--workroot", default=str(HERE / "_work"))
    bp = sub.add_parser("bench")
    bp.add_argument("--n", type=int, default=100)
    args = parser.parse_args(argv)

    if args.cmd == "run":
        run_study(Path(args.db), args.crash_at)
        return 0
    if args.cmd == "verify":
        return verify(Path(args.workroot))
    if args.cmd == "bench":
        return bench(args.n)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
