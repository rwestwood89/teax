# Implementation Plan: Study Store, Runner, and Strategies (Item 11)

**Status:** Draft
**Created:** 2026-07-12
**Last Updated:** 2026-07-12
**Branch:** constraint-exec-epic

## Source Documents
- **Spec:** `.project/active/study-store-runner/spec.md`
- **Design (rev 2, authoritative):** `.project/active/study-store-runner/design.md` ← DDL (Appendix A), the S6-criterion→test map (Appendix B), D1–D8, INV-A…INV-H, and the four Key Bets live here. This plan does not restate them; it references them.
- **Reference implementation:** `.project/active/spike-crash-safe-study-lifecycle/study_lifecycle.py` (the proven S6 shape) and `probe_crash_safe_study.py` (the 58-check oracle).
- **Consumed as-is (Item 10):** `packages/teax-simkit/simkit/evaluation/` and the sealed fixture `packages/teax-simkit/simkit/tests/evaluation/fixtures/sealed_package/package_live`.

All new code lands under `packages/teax-simkit/simkit/study/`; all tests under `packages/teax-simkit/simkit/tests/study/`. Nothing in `simkit/evaluation/` changes (design.md Non-Goals).

---

## ⚠️ Flagged finding (read before Phase 3) — `not_assessed` is unreachable by input

The sealed fixture's aggregator declares exactly one fixed assertion and derives the headline from it (`.../modules/constraints/constraint_report_aggregator.py:13` `EXPECTED_IDS = ('toy_plant__demo_plant__affordable',)`; `:42-45` — `not_assessed` is the `else` branch taken only when `results` is empty). Input variation changes that one assertion's *status* (satisfied / violated / indeterminate), never its *count*. So the real evaluator over this fixture **cannot** produce the `not_assessed` completed class.

- **Impact:** Appendix B's `test_completed_matrix` row is labelled "real" for all four completed classes, but `not_assessed` has no real-input path through this fixture.
- **Resolution (design-consistent, not a new decision):** use the design's already-blessed pattern for "the deterministic package cannot itself produce this" (design.md#validation-approach, used for `execution_failed`, `assessment_failed`, and retry). Cover `not_assessed` with a **named zero-assertion affordance** — a test-only evaluator wrapper that, for one designated candidate, returns a real-shaped `ModelEvidence` whose report has `results=[]` and `headline="not_assessed"` (the real projection already maps this; `evidence.py:20-27` `CANONICAL_HEADLINE` includes `not_assessed`). The other three classes stay real-by-input (`satisfied.json`, `violated.json`, and a `NaN` operand via `f_output.json` for `indeterminate`).
- **Owner check:** confirm this affordance rather than a second zero-assertion fixture package (heavier; deferred in the design's `execution_failed` note). Recorded here so it is not silently resolved; the plan proceeds on the affordance.

---

## Implementation Strategy

**Phasing rationale — de-risk the crash-safety core first, wire the real evaluator last.**
The whole item rests on Key Bets B1–B3 (design.md#key-bets), which live entirely in the store: content-addressed staging, stage-before-commit ordering, and the fenced single-writer lease. None of that depends on *which* evaluator produced the evidence. So Phase 1 proves the store mechanics in isolation with fast, subprocess crash tests and direct store-API drivers — no runner, no package load. Phases 2–3 then build the strategies/bridge and the fixed-order runner and only then pay the cost of loading the real sealed package. Phase 4 runs the full Appendix B oracle end-to-end against the real evaluator.

**Critical path:** store + staging + fenced lease (P1) → strategies + bridge + definition (P2) → runner + `evidence_io` + real-evaluator wiring (P3) → full oracle + crash regimes (P4).

**First proof point:** a subprocess that `os._exit`s at the `before_commit` seam leaves the artifact durable at its content-addressed path with **no** case row (Phase 1, `test_store_seam_before_commit`). That single test proves the ordering INV-C the entire crash-safety claim rests on.

**Biggest risks (full analysis: design.md#potential-risks):**
- Lease reclaim correctness rests on *fencing*, not TTL tuning (B3/D4). Mitigation: the MF-1 fence test is folded into Phase 1, not deferred.
- Grid proposal-order identity: an order-insensitive `strategy_config` silently remaps positional IDs on resume (D8/MF-2). Mitigation: the order-sensitive canonicalization and its reorder-rejection test are folded into Phase 1.
- Non-finite encoding drift breaks INV-H silently. Mitigation: one function produces both the digest input and the on-disk bytes (design.md#implementation-notes).

**Validation approach:** each phase is test-first and leaves its own `pytest` green. The S6 58-check oracle (`probe_crash_safe_study.py`) is the behavioral reference; Appendix B maps each criterion to a kept test. Fake/thin drivers are used **only** for Phase 1 store mechanics (speed); every success-criterion oracle in Phases 3–4 runs against the real evaluator (design.md#validation-approach).

**Note on the "fake vs real" crash tests.** The design's de-risk note says "re-run the S6 crash regimes against the real evaluator." The orchestrator refined this: prove the *store seam physics* fast with a thin store-driver (Phase 1), then prove the *end-to-end crash regimes* (`test_crash_before_commit`, `test_crash_mid_staging`, `test_resume_identical`) against the **real** evaluator via the production runner (Phase 4, exactly as Appendix B labels them). These are the same seams in `store.py`, proven at two layers — not duplicated logic.

---

## Pre-flight (Phase 0 gate — run before any code)

**See CLAUDE.md for environment rules.** Item 10 provisioned teax's venv.

- [ ] Smoke-check the venv and the consumed evaluator:
  - `.venv/bin/python -m pytest packages/teax-simkit/simkit/tests/evaluation/ -q` → **25 passed** (the baseline this item must keep green).
  - `.venv/bin/python -c "from simkit.evaluation.evaluator import PreparedEvaluator; from simkit.evaluation.failure import EvaluationFailed, EvaluationFailure, EvaluationPhase; print('ok')"`
- [ ] Confirm the framework suite baseline: `.venv/bin/python -m pytest packages/teax-simkit/ -q` → green **except the four known pre-existing failures** (record their node IDs now so the final gate can distinguish them from regressions).
- [ ] Create package skeletons: `simkit/study/__init__.py`, `simkit/tests/study/__init__.py`.

---

## Phase 1 — Store, staging, fenced lease, GC (crash-safety core)

### Goal
Stand up `StudyStore` with the Appendix A DDL, the content-addressed staging protocol, the fenced single-writer lease, and safe GC — and prove B1/B2/B3 mechanics with subprocess crash tests, before any runner or strategy exists.

### Assumption Under Test
That stage-before-commit ordering (INV-C), final-path-complete (INV-B), lease fencing (INV-F / MF-1), and order-sensitive `strategy_config` (D8 / MF-2) hold at the store layer against real `os._exit` process death — independent of the evaluator.

### Test Stencil (write first)
```python
# tests/study/test_store_seam.py — the first proof point
def test_store_seam_before_commit(tmp_path):
    db = tmp_path / "study.db"
    # child stages one artifact durably, then os._exit BEFORE the case insert
    rc = run_store_child(db, crash_at="before_commit:cand-A")
    assert rc != 0                                   # genuine process death
    store = open_store(db)
    assert not store.has_case("cand-A")              # INV-C: no dangling case
    assert artifact_present_and_valid(db, EXPECTED_DIGEST)  # INV-B: durable orphan

def test_lease_fence_blocks_reclaimed_writer(tmp_path):   # MF-1, INV-F
    a = open_store(db); a.acquire_lease()
    b = open_store(db); force_dead(a); b.reclaim_lease()   # b mints a new lease_id
    with pytest.raises(StudyLeaseLost):
        a.commit_case(...)                            # a's fenced write aborts

def test_grid_reorder_is_new_lineage(tmp_path):           # MF-2, D8, INV-G
    c1 = compat_with_strategy_config([["b", d_b], ["a", d_a]])
    StudyStore.create_or_open(db, c1).close()
    c2 = compat_with_strategy_config([["a", d_a], ["b", d_b]])  # same vars, reordered
    with pytest.raises(IncompatibleStore):
        StudyStore.create_or_open(db, c2)             # reorder ⇒ different lineage
```

### Changes Required
**See design.md for:** DDL → Appendix A (transcribe **verbatim**); staging layout & seams → design.md#implementation-notes; lease acquire/fence/GC pseudocode → Appendix A; invariants → design.md#required-invariants (INV-A…INV-F, INV-H).

Files under `simkit/study/`:
- [ ] `failures.py` — `IncompatibleStore`, `StudyLocked`, `StudyLeaseLost`, `StudyBridgeDefect`, `RetryableStoreError` (design.md#component-overview).
- [ ] `identity.py` — canonical JSON bytes, `sha256` digests, positional ID minting, and the **order-sensitive** `strategy_config` canonicalization (ordered `[name, domain]` pair-array, never `sort_keys`; D8). Contrast with the S6 `canonical_bytes` `sort_keys=True` (`study_lifecycle.py:43-49`) which this deliberately replaces for order-bearing config.
- [ ] `compatibility.py` — the eight-field `Compatibility` binding (design.md#component-overview); `strategy_config` uses the order-preserving canonicalization from `identity.py`.
- [ ] `crash.py` — `CrashController` with `maybe_crash(phase, candidate_id)` doing `os._exit`; default no-op instance for production (port `study_lifecycle.py:246-264`).
- [ ] `store.py` — `StudyStore`:
  - DDL from Appendix A verbatim (`compatibility`, `proposals`, `attempt_transitions`, `cases`, `runner_lease`, + `ix_attempt_by_candidate`). Note the deltas from S6's schema: `attempt_transitions` replaces `attempts` (Option A, D2), `cases.evidence_digest` is **nullable** (D5), and `runner_lease` is new.
  - `PRAGMA journal_mode=WAL` + `PRAGMA synchronous=FULL`, set on every open and **asserted** as contract; state it in the module docstring and the single-host contract line (NF-3, design.md#implementation-notes).
  - Staging protocol: `root/staging/{lease_id}/{attempt_id}.tmp` → fsync → atomic rename → `root/artifacts/{digest}.json` → fsync dir, with the two seams (`mid_staging`, `before_commit`) exactly where `study_lifecycle.py:423-486` puts them. Per-lease staging subdir created at lease-acquire (NF-4).
  - Fenced writes (MF-1): every case-commit / transition / proposal insert runs the in-transaction lease guard (Appendix A "Fenced write"), raising `StudyLeaseLost` on mismatch.
  - Lease acquire/heartbeat(background thread)/reclaim per Appendix A pseudocode (defaults: 10 s heartbeat, 30 s TTL; `os.kill(pid,0)`→`ESRCH` same-host fast path).
  - Attempt-number derivation: `COALESCE(MAX(attempt_number),0)+1` over the candidate's transition rows — **not** `COUNT(*)` (MF-4; contrast S6 `study_lifecycle.py:397-402`).
  - GC: refuse unless lease `released`/dead; collect dead-lease `staging/{dead}/*.tmp` and any `artifacts/{digest}.json` whose digest is in no committed case's non-null `evidence_digest` (Appendix A "GC"; L3-5).
- [ ] `tests/study/_store_child.py` — minimal subprocess driver: open store, acquire lease, stage+commit one (or a few) case(s) directly via the store API with a `CrashController`. ~40 lines, store-only, no runner/strategy. Runnable as `python -m simkit.tests.study._store_child --db ... --crash-at PHASE:CAND`.

Tests (`tests/study/`):
- [ ] `test_store_seam.py` — `test_store_seam_before_commit`, `test_store_seam_mid_staging` (final absent, truncated tmp; mirror `probe_crash_safe_study.py:199-222`).
- [ ] `test_lease.py` — `test_lease_fence_blocks_reclaimed_writer` (MF-1), `test_second_live_runner_refused` (`StudyLocked`).
- [ ] `test_compatibility.py` — `test_incompatible_reopen_fails`, `test_grid_reorder_is_new_lineage` (MF-2), matching-reopen succeeds.
- [ ] `test_gc.py` — `test_gc_orphans_only`: dead-lease orphan tmp collected, a replicate-shared artifact kept.

### Validation
- [ ] `.venv/bin/python -m pytest packages/teax-simkit/simkit/tests/study/ -q` → all Phase-1 tests pass.
- [ ] `.venv/bin/python -m pytest packages/teax-simkit/simkit/tests/evaluation/ -q` → still 25 passed.
- [ ] `ruff check packages/teax-simkit/simkit/study packages/teax-simkit/simkit/tests/study` → clean.

**What we know works after Phase 1:** the store survives both crash seams (B2/INV-B/INV-C), a reclaimed writer cannot double-write (B3/INV-F), reordered grid variables start a new lineage (D8/INV-G identity property), and GC collects only unreferenced garbage — all without the evaluator.

---

## Phase 2 — Strategies, bridge, definition, policy

### Goal
Build the real `PreparedListStrategy` / `GridStrategy`, the `CandidateBridge` (Shape A), the `StudyDefinition`, and the minimal `DispositionPolicy` — the pieces the runner composes.

### Assumption Under Test
That a grid emits a byte-stable proposal sequence across two fresh processes (B1 / INV-G), and that the bridge builds a valid `ToyPlantParams` from selected fields so `entry_source.validate` accepts it.

### Test Stencil (write first)
```python
# tests/study/test_strategy.py
def test_grid_determinism_pin(tmp_path):                  # INV-G, "two processes"
    seq1 = subprocess_dump_grid_proposals()               # fresh process A
    seq2 = subprocess_dump_grid_proposals()               # fresh process B
    assert seq1 == seq2                                    # byte-identical (proposal_id, raw)

# tests/study/test_bridge.py
def test_bridge_builds_entry_model(prepared):             # Shape A
    entry = CandidateBridge(...).build({"toy_plant__Toy_Plant__plant_budget": 6000.0})
    assert set(entry) == {"toy_plant_params"}
    prepared._source.validate(entry)                      # must not raise ENTRY_VALIDATION
```

### Changes Required
**See design.md for:** strategy contract → design.md#component-overview (`strategy.py`); Shape A bridge → design.md#core-concept item 1 and spec.md#runner; grid row-major over declared order → D8.

Files under `simkit/study/`:
- [ ] `strategy.py` — `CandidateStrategy` protocol; `PreparedListStrategy` (port `PreparedCandidateStrategy`, `study_lifecycle.py:202-219`, positional `p{index:04d}`); `GridStrategy` enumerating `itertools.product` over **declared** variable order, config exposed as the order-sensitive pair-array from `identity.py`. `observe` inert but present.
- [ ] `bridge.py` — `CandidateBridge`: maps a validated candidate's selected fields onto `ToyPlantParams(**selected)` (all four fields are defaulted floats — `.../schemas/toy_plant_params.py:9-14`; unselected fields keep modeled defaults, plus any study-fixed constants) and returns `{"toy_plant_params": model}` (channel ID from `tests/evaluation/conftest.py:19` `ENTRY_CH`). Does **not** type-check — delegates to `entry_source`.
- [ ] `definition.py` — `StudyDefinition`: selects variables/domains by parameter ID (a *field* of the entry channel), observables, objectives, response roles; carries the **injected** proposal validator + policy, strategy, budget, retention; cannot redefine a predicate (spec.md#studydefinition).
- [ ] `policy.py` — `Policy` protocol + minimal `DispositionPolicy` producing the three case states and able to reject a designated candidate for `assessment_failed` (port `DeterministicPolicy`, `study_lifecycle.py:182-195`, adapted to the real `responses["headline"]` vocabulary).

Tests:
- [ ] `test_strategy.py` — `test_grid_determinism_pin` (two-process pin), `test_proposal_determinism_idempotent` (same positional `proposal_id` re-proposed, incl. an invalid entry; L3-3), `test_grid_config_is_order_sensitive` (GridStrategy feeds the ordered pair-array).
- [ ] `test_bridge.py` — `test_bridge_builds_entry_model`, `test_bridge_defaults_unselected`.

### Validation
- [ ] `pytest packages/teax-simkit/simkit/tests/study/ -q` → Phase 1 + 2 green.
- [ ] `ruff check` on study + study tests → clean.

**What we know works after Phase 2:** grids replay byte-identically across processes (the B1 property positional identity rests on), and the bridge produces entry models the certified `entry_source` accepts.

---

## Phase 3 — Runner, `evidence_io`, real-evaluator wiring (per-case behavior)

### Goal
Build the fixed-order `StudyRunner` (validate → bridge → evaluate → assess → stage → commit → observe), the failure-routing switch, the retry loop, and `evidence_io` (non-finite sentinel + reserved-key rejection) — proven against the **real** evaluator, one case at a time.

### Assumption Under Test
That the runner routes the real `EvaluationFailed` taxonomy correctly (B4): `ENTRY_VALIDATION` → loud `StudyBridgeDefect`, `MODULE_EXECUTION` → `execution_failed` case, retry only on store-transient faults; and that staged evidence round-trips non-finite operands losslessly (INV-H, D3).

### Test Stencil (write first)
```python
# tests/study/test_runner_matrix.py — against the REAL PreparedEvaluator
def test_completed_matrix(study_env):
    cases = run_study(study_env)                          # real evaluator over the fixture
    headlines = {c.candidate_id: c.headline for c in cases if c.state == "completed"}
    assert set(headlines.values()) == {"satisfied", "violated", "indeterminate", "not_assessed"}
    # satisfied/violated/indeterminate by real input (indeterminate via a NaN operand);
    # not_assessed via the named zero-assertion affordance (see Flagged finding).

def test_execution_failed(study_env):                     # named MODULE_EXECUTION fault
    # a test evaluator delegating to PreparedEvaluator that, for one candidate, raises
    # the authentic EvaluationFailed(EvaluationFailure(phase=MODULE_EXECUTION, retryable=False))
    case = case_for(run_study(study_env), "cand-exec-fail")
    assert case.state == "execution_failed" and case.evidence_digest is None  # D5

def test_evidence_roundtrip_nonfinite(study_env):         # INV-H, D3
    digest = staged_digest_for_nan_case(study_env)
    assert sha256(read_artifact_bytes(digest)) == digest  # bytes re-hash to the digest
```

### Changes Required
**See design.md for:** fixed order → design.md#architecture; failure-routing switch (against the enum) → design.md#implementation-notes; retry (store-I/O only, limit 3, no backoff) → D7; non-finite encoding + reserved-key rejection → D3; the `execution_failed`/`assessment_failed`/retry trigger recipes → design.md#validation-approach.

Files under `simkit/study/`:
- [ ] `evidence_io.py` — serialize `ModelEvidence` for staging: `report.model_dump(mode="json")`, then apply the **recursive** `{"__nonfinite__": tag}` sentinel to the whole payload (outputs/responses/report), used for **both** the digest input and the on-disk bytes (single source — design.md#potential-risks). Reject a reserved-key collision loudly (`ValueError`) if a genuine value is a one-key `{"__nonfinite__": …}` mapping (MF-3). Never imports a generated report class as a runtime type (`evidence.py:45-58` holds `report: Any`).
- [ ] `runner.py` — `StudyRunner`, fixed order with injected evaluator/strategy/validator/bridge/policy. Write and commit the `started` transition *before* evaluate/stage/commit; terminal transitions after commit (design.md#implementation-notes). Failure-routing switch written against `EvaluationPhase` (four phases; `failure.py:13-24`), not "two phases":
  - `ENTRY_VALIDATION` → `raise StudyBridgeDefect(failure)` (loud, never a case; spec.md#runner);
  - `PREPARATION` → re-raise (startup fault, not a case);
  - else (`MODULE_EXECUTION` today / `OUTPUT_WRITE` future) → `execution_failed` case with `evidence_digest=NULL`, `failure_json=failure` (D5).
  - Retry loop: only `RetryableStoreError` (staging/commit `OSError`, SQLite `OperationalError`) retries, new `attempt_id`, limit 3, no backoff (D7). The evaluator is never retryable (`failure.py:31-38`).
- [ ] `tests/study/conftest.py` — real-evaluator fixtures reusing `PreparedEvaluator(loader, SPEC_PATH)` with `ProvisionalPackageLoader(package_dir=FIXTURE_DIR, package_name="wi014_s4", link_root=...)` (mirror `tests/evaluation/conftest.py:29-39`); the study-definition variables; and the named test affordances (MODULE_EXECUTION-raising wrapper, zero-assertion wrapper, store-transient fault, policy rejection).

Tests:
- [ ] `test_runner_matrix.py` — `test_completed_matrix` (four classes; see Flagged finding for `not_assessed`), `test_invalid_proposal_record` (validator injection; well-formed-but-invalid stays a `ProposalRecord`, never a case — and **non-finite is NOT invalid**, spec.md#runner), `test_no_double_commit`.
- [ ] `test_runner_failures.py` — `test_execution_failed` (named MODULE_EXECUTION fault), `test_assessment_failed` (policy rejection, real evidence preserved), `test_retry_new_attempt` (store-transient fault, one case on a new `attempt_id`), `test_bridge_defect_is_loud` (an `ENTRY_VALIDATION` from a deliberately wrong bridge raises `StudyBridgeDefect`, never a case).
- [ ] `test_evidence_io.py` — `test_evidence_roundtrip_nonfinite` (INV-H), `test_reserved_key_rejected` (MF-3).

### Validation
- [ ] `pytest packages/teax-simkit/simkit/tests/study/ -q` → Phases 1–3 green.
- [ ] `pytest packages/teax-simkit/simkit/tests/evaluation/ -q` → still 25.
- [ ] `ruff check` → clean.

**What we know works after Phase 3:** every per-case outcome the runner must produce is proven against the real evaluator + real failure taxonomy + real evidence, and evidence round-trips losslessly.

---

## Phase 4 — Full Appendix B oracle: crash regimes + cross-candidate invariants

### Goal
Run the S6 crash regimes and cross-candidate invariants end-to-end through the production runner over the **real** evaluator, closing every remaining Appendix B row and the final gates.

### Assumption Under Test
That a killed real run, resumed in a fresh process, reconstructs the identical ordered cases by replay (B1/B2), commits each candidate exactly once, and never references a missing/half-written artifact.

### Test Stencil (write first)
```python
# tests/study/test_crash_regimes.py — real runner via the study child, real os._exit
def test_resume_identical(tmp_path):
    baseline = child_run(db_a, crash_at=None)             # uninterrupted
    child_run(db_b, crash_at="before_commit:cand-0")      # crash
    child_run(db_b, crash_at=None)                        # resume, fresh process
    assert logical_cases(db_b) == logical_cases(db_a)     # identical ordered cases
    assert committed_once(db_b, "cand-0") and attempt_of(db_b, "cand-0") == "a2"

def test_no_dangling_artifact(tmp_path):                  # both crash legs
    for seam in ("before_commit:cand-0", "mid_staging:cand-6"):
        child_run(db, crash_at=seam); child_run(db, crash_at=None)
        assert all(artifact_present_and_valid(db, d) for d in referenced_digests(db))
```

### Changes Required
**See design.md for:** the crash-regime recipes and the "seams downstream of a completed real `evaluate()`" rule → design.md#validation-approach and spec.md#crash-tests.

- [ ] `tests/study/_study_child.py` — the production-runner CLI child: builds the real `PreparedEvaluator` + `StudyRunner` + `CrashController`, mirroring S6's `run --db --crash-at` (`study_lifecycle.py:663-678`). This is the child the crash regimes drive (distinct from Phase 1's store-only `_store_child.py`). Reuse a fixed multi-candidate `StudyDefinition` shared by driver and child so resume compares against a stable baseline (mirror `study_lifecycle.py:617-660`).
- [ ] `test_crash_regimes.py` — `test_crash_before_commit`, `test_crash_mid_staging`, `test_resume_identical`, `test_no_dangling_artifact`, `test_no_double_commit` (end-to-end), `test_replicates_share_artifact` (two candidates, identical inputs, one shared artifact; distinct `candidate_id`s).

### Validation (final gates)
- [ ] **All Appendix B tests green:** `pytest packages/teax-simkit/simkit/tests/study/ -q`.
- [ ] **Evaluation suite still green:** `pytest packages/teax-simkit/simkit/tests/evaluation/ -q` → 25 passed.
- [ ] **Framework suite green except the four known pre-existing failures:** `pytest packages/teax-simkit/ -q` → only the four node IDs recorded in Pre-flight fail; no new failures.
- [ ] **Ruff clean:** `ruff check packages/teax-simkit/simkit/study packages/teax-simkit/simkit/tests/study`.

**What we know works after Phase 4:** the full S6 oracle holds against the real Item 10 evaluator — the item's success criteria (spec.md#success-criteria) are met as kept CI tests.

---

## Risk Management

**Full analysis: design.md#potential-risks.** Phase-specific mitigations:
- **Phase 1:** MF-1 fence test and MF-2 reorder-rejection test are folded in here (not deferred), because both live in the store+lease path stood up first (design.md#next-stage-handoff).
- **Phase 3:** `evidence_io` uses one function for both digest input and on-disk bytes, so INV-H cannot drift silently; the failure switch is written against the four-phase enum, not "two phases," so a future persisting backend's `OUTPUT_WRITE` routes correctly.
- **Phase 3/4:** the deterministic fixture cannot raise, fail assessment, or emit zero assertions by input; every such cell uses the design's named-affordance pattern at the exact real seam (design.md#validation-approach), and `not_assessed` specifically follows the Flagged finding above.

## Implementation Notes

[TO BE FILLED DURING IMPLEMENTATION — leave empty now]

### Phase 1 Completion
**Completed:** …  **Actual Changes:** …  **Issues:** …  **Deviations:** …

### Phase 2 Completion

### Phase 3 Completion

### Phase 4 Completion

---

**Status:** Draft → In Progress → Complete
</content>
</invoke>
