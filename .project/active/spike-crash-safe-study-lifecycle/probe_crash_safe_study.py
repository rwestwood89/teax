"""Throwaway S6 driver: inject hard crashes, resume, and check every invariant.

Runs `study_lifecycle.py` as real child processes so crashes are genuine
`os._exit` process deaths (no Python cleanup runs), then resumes in a fresh
process against the same SQLite DB + artifact directory. Prints a JSON report;
exits non-zero if any invariant fails.

Reproduce from /home/reid/1cfe/teax:

    python3 .project/active/spike-crash-safe-study-lifecycle/probe_crash_safe_study.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE = HERE / "study_lifecycle.py"

sys.path.insert(0, str(HERE))
import study_lifecycle as sl  # noqa: E402

STUDY = sl.STUDY_ID
CAND = lambda i: f"{STUDY}:c{i:04d}"  # noqa: E731

# Fields that define a logical case. attempt_id and commit_order are deliberately
# excluded: a resumed run legitimately commits the crashed candidate on a later
# attempt, and the row's autoincrement id differs across processes.
CASE_KEYS = ("candidate_id", "proposal_id", "state", "inputs_json",
             "evidence_digest", "assessment_json")


def logical_cases(rows: list[dict]) -> list[dict]:
    return [{k: row[k] for k in CASE_KEYS} for row in rows]


def child_run(db: Path, crash_at: str | None) -> int:
    cmd = [sys.executable, str(MODULE), "run", "--db", str(db)]
    if crash_at:
        cmd += ["--crash-at", crash_at]
    return subprocess.run(cmd, cwd=str(HERE)).returncode


def open_store(db: Path) -> sl.StudyStore:
    return sl.StudyStore.create_or_open(db, sl.default_compatibility())


def evidence_digest_for(kind: str, x: float, *, satisfied: bool = True) -> str:
    """Recompute a completed-case artifact digest the way the store does."""
    ev = sl.FakeEvaluator().evaluate({"kind": kind, "x": x}, attempt_number=2)
    return sl.digest_of(ev.to_json())


def check(report: dict, name: str, ok: bool) -> None:
    report["checks"][name] = bool(ok)
    if not ok:
        report["failed"].append(name)


def artifact_present_and_valid(db: Path, digest: str) -> bool:
    path = db.parent / "artifacts" / f"{digest}.json"
    if not path.exists():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == digest


def invariants_on_final_store(report: dict, prefix: str, db: Path) -> list[dict]:
    store = open_store(db)
    try:
        rows = store.ordered_cases()
        referenced = store.referenced_digests()
        proposals = {
            r["proposal_id"]: dict(r)
            for r in store.conn.execute("SELECT * FROM proposals")
        }
        attempts = [dict(r) for r in store.conn.execute("SELECT * FROM attempts")]
    finally:
        store.close()

    by_cand = {r["candidate_id"]: r for r in rows}

    # No logical candidate commits twice.
    cand_ids = [r["candidate_id"] for r in rows]
    check(report, f"{prefix}:no_candidate_committed_twice",
          len(cand_ids) == len(set(cand_ids)))

    # No committed case references a missing/half-written artifact.
    check(report, f"{prefix}:no_missing_artifacts",
          all(artifact_present_and_valid(db, d) for d in referenced))

    # Invalid proposal persisted as a proposal record, never a case.
    inv = proposals.get(f"{STUDY}:p0003")
    check(report, f"{prefix}:invalid_proposal_is_record",
          inv is not None and inv["valid"] == 0 and inv["candidate_id"] is None)
    check(report, f"{prefix}:invalid_proposal_not_a_case",
          CAND(3) not in by_cand)

    # The three case states are present and distinct.
    states = {r["state"] for r in rows}
    check(report, f"{prefix}:three_case_states_present",
          {"completed", "execution_failed", "assessment_failed"} <= states)
    check(report, f"{prefix}:exec_fail_state",
          by_cand.get(CAND(4), {}).get("state") == "execution_failed")
    check(report, f"{prefix}:assess_fail_state",
          by_cand.get(CAND(5), {}).get("state") == "assessment_failed")
    # Assessment failure preserved evidence (real evidence digest, not a stub).
    assess_row = by_cand.get(CAND(5), {})
    check(report, f"{prefix}:assess_fail_preserves_evidence",
          assess_row.get("evidence_digest") == evidence_digest_for("assess_fail", 50.0))

    # Zero-assertion completed case exists.
    zero = by_cand.get(CAND(6), {})
    check(report, f"{prefix}:zero_assertion_case",
          zero.get("state") == "completed"
          and json.loads(zero.get("assessment_json") or "{}").get("headline") == "not-assessed")

    # Replicates: distinct candidate ids, identical inputs, shared artifact digest.
    ra, rb = by_cand.get(CAND(7), {}), by_cand.get(CAND(8), {})
    check(report, f"{prefix}:replicates_distinct_candidates",
          ra.get("candidate_id") != rb.get("candidate_id")
          and ra.get("inputs_json") == rb.get("inputs_json"))
    check(report, f"{prefix}:replicates_share_artifact",
          bool(ra) and ra.get("evidence_digest") == rb.get("evidence_digest"))

    # Retry: same candidate_id, new attempt_id, exactly one committed case on a2.
    retry_attempts = sorted(
        (a for a in attempts if a["candidate_id"] == CAND(9)),
        key=lambda a: a["attempt_number"],
    )
    check(report, f"{prefix}:retry_new_attempt_id",
          [a["attempt_number"] for a in retry_attempts] == [1, 2]
          and retry_attempts[0]["outcome"] == "retryable_failed"
          and retry_attempts[1]["outcome"] == "committed")
    check(report, f"{prefix}:retry_single_case",
          by_cand.get(CAND(9), {}).get("attempt_id") == f"{CAND(9)}:a2"
          and sum(1 for r in rows if r["candidate_id"] == CAND(9)) == 1)

    return rows


def main() -> int:
    report: dict = {"checks": {}, "failed": [], "detail": {}}
    workroot = Path(tempfile.mkdtemp(prefix="s6-spike-"))
    report["detail"]["workroot"] = str(workroot)

    try:
        # ---- 1. Baseline: uninterrupted run ------------------------------
        base_dir = workroot / "baseline"
        base_dir.mkdir()
        base_db = base_dir / "study.db"
        rc = child_run(base_db, crash_at=None)
        check(report, "baseline:child_exit_0", rc == 0)
        baseline_rows = invariants_on_final_store(report, "baseline", base_db)
        baseline_logical = logical_cases(baseline_rows)
        report["detail"]["baseline_case_count"] = len(baseline_rows)
        report["detail"]["baseline_candidate_order"] = [
            r["candidate_id"] for r in baseline_rows
        ]
        # Baseline commits the target on its first attempt.
        base_c0000 = next(r for r in baseline_rows if r["candidate_id"] == CAND(0))
        check(report, "baseline:target_first_attempt",
              base_c0000["attempt_id"] == f"{CAND(0)}:a1")

        # ---- 2. Crash BEFORE COMMIT, then resume -------------------------
        bc_dir = workroot / "before_commit"
        bc_dir.mkdir()
        bc_db = bc_dir / "study.db"
        rc = child_run(bc_db, crash_at=f"before_commit:{CAND(0)}")
        check(report, "before_commit:child_crashed", rc != 0)

        # At the crash: no case for the target, but its artifact is durably staged.
        c0000_digest = evidence_digest_for("all_satisfied", 10.0)
        store = open_store(bc_db)
        crashed_has_case = store.has_case(CAND(0))
        store.close()
        check(report, "before_commit:no_case_at_crash", not crashed_has_case)
        check(report, "before_commit:artifact_durable_at_crash",
              artifact_present_and_valid(bc_db, c0000_digest))
        # Crucially, no case references it yet -> it is orphan-but-durable.

        rc = child_run(bc_db, crash_at=None)  # resume
        check(report, "before_commit:resume_exit_0", rc == 0)
        bc_rows = invariants_on_final_store(report, "before_commit", bc_db)
        check(report, "before_commit:identical_ordered_cases",
              logical_cases(bc_rows) == baseline_logical)
        # Same candidate, but committed on a NEW attempt after the crash.
        bc_c0000 = next(r for r in bc_rows if r["candidate_id"] == CAND(0))
        check(report, "before_commit:target_committed_once",
              sum(1 for r in bc_rows if r["candidate_id"] == CAND(0)) == 1)
        check(report, "before_commit:target_new_attempt_id",
              bc_c0000["attempt_id"] == f"{CAND(0)}:a2")

        # ---- 3. Crash MID-STAGING, then resume ---------------------------
        ms_dir = workroot / "mid_staging"
        ms_dir.mkdir()
        ms_db = ms_dir / "study.db"
        rc = child_run(ms_db, crash_at=f"mid_staging:{CAND(6)}")
        check(report, "mid_staging:child_crashed", rc != 0)

        # At the crash: target's final artifact ABSENT, no case, a truncated tmp
        # sits in staging as collectable garbage.
        c0006_digest = evidence_digest_for("zero_assertions", 60.0)
        final_absent = not (ms_db.parent / "artifacts" / f"{c0006_digest}.json").exists()
        staging_tmps = list((ms_db.parent / "staging").glob("*.tmp"))
        store = open_store(ms_db)
        ms_crashed_case = store.has_case(CAND(6))
        store.close()
        check(report, "mid_staging:final_artifact_absent_at_crash", final_absent)
        check(report, "mid_staging:no_case_at_crash", not ms_crashed_case)
        check(report, "mid_staging:orphan_tmp_present", len(staging_tmps) >= 1)
        # A truncated tmp is genuinely incomplete (its bytes don't hash to the digest).
        truncated = any(
            hashlib.sha256(p.read_bytes()).hexdigest() != c0006_digest
            for p in staging_tmps
        )
        check(report, "mid_staging:tmp_is_truncated", truncated)

        rc = child_run(ms_db, crash_at=None)  # resume
        check(report, "mid_staging:resume_exit_0", rc == 0)
        ms_rows = invariants_on_final_store(report, "mid_staging", ms_db)
        check(report, "mid_staging:identical_ordered_cases",
              logical_cases(ms_rows) == baseline_logical)
        check(report, "mid_staging:target_artifact_now_present",
              artifact_present_and_valid(ms_db, c0006_digest))

        # ---- 4. Incompatible-fingerprint open fails ----------------------
        incompat_db = workroot / "incompat" / "study.db"
        incompat_db.parent.mkdir()
        open_store(incompat_db).close()  # create + bind
        mutated = sl.default_compatibility()
        mutated = sl.Compatibility(
            **{**mutated.__dict__, "executable_fingerprint": "exe-fingerprint-B"}
        )
        rejected = False
        try:
            sl.StudyStore.create_or_open(incompat_db, mutated)
        except sl.IncompatibleStore:
            rejected = True
        check(report, "incompatible_fingerprint_open_fails", rejected)
        # A matching reopen still succeeds.
        reopened_ok = False
        try:
            open_store(incompat_db).close()
            reopened_ok = True
        except sl.IncompatibleStore:
            reopened_ok = False
        check(report, "matching_fingerprint_open_succeeds", reopened_ok)

        report["ok"] = not report["failed"]
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1
    finally:
        shutil.rmtree(workroot, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
