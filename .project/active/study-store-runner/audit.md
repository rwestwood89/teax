# Audit: Study Store, Runner, and Strategies — Item 11

**Verdict:** Certify-with-notes
**Audited:** 2026-07-12
**Branch:** constraint-exec-epic
**Commit:** b70010f (Item 11 Phase 4; Phases 1–4 = 5c3a890, 4b4698b, bae7846, b70010f)

---

## Summary

The four phase commits deliver the `simkit/study/` subpackage the spec and design (rev 2)
call for: a crash-safe fenced `StudyStore`, prepared list/grid strategies, the fixed-order
`StudyRunner`, Shape-A bridge, order-sensitive compatibility, Option A attempt history, safe
GC, and the injective non-finite sentinel. I read every source and test file and traced the
mechanisms named in the brief. The implementation follows the design closely, with no
undocumented deviations — the deviations that exist are all recorded in plan.md's completion
notes. The five S6 pass criteria and the three crash regimes map to kept tests that drive the
**real** evaluator (`PreparedEvaluator` over the in-repo sealed fixture) through real `os._exit`
subprocess deaths via the production runner; the fence, the reorder-rejection, and Option A
forensics all have teeth by static trace.

**Why "with notes," not a clean Certify:** this session could not execute anything — every
Python/pytest/ruff invocation was permission-blocked. So the three execution claims in the
brief (29 study + 25 eval green; framework failures = exactly the 4 known; ruff clean) and the
requested fence-mutation probe are **statically corroborated but not run**. Exact commands and
expected outcomes are listed under "Requested live probes." Two minor coverage gaps and one
robustness observation are noted; none blocks certification.

---

## Findings

### Plan completion

All four phases are checked complete in plan.md and the code/tests backing each phase are
present and committed (working tree is clean under `packages/`). Phase completion notes are
honest and match the code:

- **Phase 1 (store/staging/fenced lease/GC):** `store.py` transcribes the Appendix A DDL
  verbatim (`store.py:39-78`), fences every write via `_fenced_execute` (`store.py:255-279`,
  `BEGIN IMMEDIATE` → re-read `runner_lease.lease_id` → `StudyLeaseLost` on mismatch), and
  derives the next attempt with `COALESCE(MAX(attempt_number),0)+1` (`store.py:299-305`, MF-4).
  The recorded deviation (`reclaim_lease()` folded into `acquire_lease()`) matches the Appendix
  A pseudocode, which is one procedure.
- **Phase 2 (strategies/bridge/definition/policy):** present; `GridStrategy` enumerates
  `itertools.product` over declared order (`strategy.py:63-67`).
- **Phase 3 (runner/evidence_io/wiring):** present; `RetryableStoreError` wrapping was
  backfilled into `store.py` (`_fenced_execute:273-275`, `_stage_artifact:369-371`) as noted.
- **Phase 4 (full oracle):** `_study_child.py` builds the real `PreparedEvaluator` +
  `StudyRunner` + `CrashController`; the six crash-regime tests drive it as a subprocess.

No placeholder code, no TODOs, no partial implementations found.

### Spec conformance

**Success criterion 1 — five S6 pass criteria as kept tests against the REAL evaluator.**
Mapped each criterion to its test and confirmed the evaluator path:

1. *Resumed == uninterrupted ordered cases* → `test_resume_identical`
   (`test_crash_regimes.py:79-105`). Genuine ordered comparison:
   `logical_cases(resumed) == baseline_logical` over 7 case fields
   (`candidate_id, proposal_id, state, inputs_json, evidence_digest, failure_json,
   assessment_json`) by `commit_order` (`:22-25, :38-39`). Real evaluator via `_study_child`;
   real `os._exit` child death (`child_run` asserts `rc != 0`). Also asserts the crashed
   candidate re-commits once on attempt `a2` (`:101-103`) — which proves the crashed `a1`
   `started` transition survived and `COALESCE` derived `a2`.
   *Note 1 below: the crash lands on cand-0 (first), so this exercises resume-from-empty, not
   resume-with-some-committed.*
2. *No double-commit* → `test_no_double_commit` (end-to-end `:125-137`), backed structurally by
   `UNIQUE(study_id, candidate_id)` (`store.py:70`) and operationally by the `has_case` skip
   (`runner.py:62-63`).
3. *No case → missing/half-written artifact* → `test_no_dangling_artifact`, both crash legs
   (`:108-122`): after crash+resume, every `referenced_digest` re-hashes to its file.
4. *Invalid proposal stays a record* → `test_invalid_proposal_record`
   (`test_runner_matrix.py:29-42`): the wrong-type proposal (index 3, `"not-a-number"`) persists
   with `valid=0, candidate_id=NULL` and never becomes a case. Confirmed non-finite is NOT
   treated as invalid — index 2 (`nan`) passes validation and reaches the evaluator as
   `indeterminate` (`conftest.py:111-116`, `_DISPOSITION_BY_HEADLINE`).
5. *Incompatible fingerprint reopen fails* → `test_incompatible_reopen_fails`
   (`test_compatibility.py:20-26`). Correctly store-only (n/a evaluator).

Crash regimes are real subprocess deaths through the production runner, not mocked kills:
`CrashController.maybe_crash` does `os._exit(137)` (`crash.py:26-33`); `_study_child` runs the
real `StudyRunner`; the seams sit in the store's staging/commit path downstream of a completed
`evaluate()` (`store.py:363` mid_staging, `store.py:396` before_commit). ✔

**Success criterion 2 — three crash regimes CI-runnable against the real evaluator.** Met:
`test_crash_before_commit`, `test_crash_mid_staging`, `test_resume_identical`
(`test_crash_regimes.py`), each via `_study_child` and real `os._exit`.

**Success criterion 3 — full S6 outcome matrix against the real evaluator.** Mostly met, with
one documented affordance:
- satisfied / violated / indeterminate: **real by input** (budgets 6000/1000/`nan`,
  `conftest.py:97-100`); the fixture cost is `4*3*250=3000`.
- `execution_failed`: real `EvaluationFailed(MODULE_EXECUTION)` raised by `NamedFaultEvaluator`
  (`conftest.py:131-137`) — byte-identical to what `evaluator.py:114-120` wraps a real module
  raise into; case carries `evidence_digest=NULL` + `failure_json` (D5, verified
  `test_runner_failures.py:28-38`).
- `assessment_failed`: **real evidence** preserved (`evidence_digest is not None`,
  `test_runner_failures.py:41-51`); the injected `DispositionPolicy` rejects one candidate.
- replicates share one artifact: `test_replicates_share_artifact` — distinct `candidate_id`s,
  identical `inputs_json`, identical `evidence_digest` (`test_crash_regimes.py:140-154`).
- retry on a new `attempt_id`: `test_retry_new_attempt` via `FlakyOnceStore`; asserts the full
  Option-A transition timeline `(1,started),(1,retryable_failed),(2,started),(2,committed)` and
  the committed case on `a2` (`test_runner_failures.py:54-79`).
- **`not_assessed` uses a named zero-assertion affordance, not real input** — see Note 2.

**Success criterion 4 — changed anything mid-study starts a new lineage.** Met.
`Compatibility` binds eight fields once at creation (`compatibility.py`, `store.py:142-151`);
any mismatch raises `IncompatibleStore`. The order-sensitive `strategy_config` (D8/MF-2) is
confirmed below.

**Success criterion 5 — GC collects exactly S6's orphan garbage, never a shared artifact.**
Met for the two asserted directions (see Note 3 for the untested direction). `test_gc_orphans_only`
collects the dead-lease orphan tmp and keeps the replicate-shared artifact
(`test_gc.py:21-48`); `test_gc_refuses_while_lease_live` proves live-lease tmps are untouchable
(`:12-18`).

**Tagged-requirement spot checks (all met):**
- `[HARD]` WAL + synchronous=FULL as contract, asserted every open — `store.py:106-121`
  (`_assert_pragma_contract`, `FULL==2`), stated in the module docstring.
- `[HARD]` positional minting documented with reason — `identity.py` docstring + `strategy.py`.
- `[HARD]` proposal validation is injected — `StudyDefinition.validate_proposal`
  (`definition.py:37`), used at `runner.py:48`.
- `[HARD]` evaluator protocol carries no `attempt_number`; retry is runner-owned —
  `runner.py:71-84`.
- `[HARD]` bridge builds instantiated entry model (Shape A), delegates type-checking to
  `entry_source` — `bridge.py:25-26`, `test_bridge.py:13`.
- `[HARD]` bridge-produced `ENTRY_VALIDATION` is a loud runner defect, never a case —
  `runner.py:111-112` raises `StudyBridgeDefect`; `test_bridge_defect_is_loud` asserts
  `ordered_cases()==[]` (`test_runner_failures.py:82-108`).
- `[HARD]` staged evidence round-trips non-finite losslessly, one function for bytes+digest —
  `evidence_io.encode_evidence` produces the dict, `store._stage_artifact` is the single
  `canonical_bytes`→sha256 source (`store.py:346-347`); `test_evidence_roundtrip_nonfinite`
  reloads the bytes as standard JSON and re-hashes to the digest.
- `[INHERITED]` three case states never merge; assessment never mutates evidence —
  `runner.py` commits distinct `state` values; `assessment_failed` stores the encoded real
  evidence, `ModelEvidence` is frozen (`evidence.py:45`).

**Non-goals respected:** no adaptive strategy behavior (both `observe` are inert,
`strategy.py:38-39,69-70`); no policy/query/CLI beyond the minimal injected seam
(`policy.py`); `simkit/evaluation/` is imported read-only and unchanged (git shows no eval
edits). ✔

### Design conformance

Implementation follows design rev 2. Verified the four mechanisms the brief called out:

- **MF-1 (fence has teeth).** `_fenced_execute` re-reads `lease_id` inside the same
  `BEGIN IMMEDIATE` transaction as the write and raises `StudyLeaseLost` on mismatch
  (`store.py:265-279`). `test_lease_fence_blocks_reclaimed_writer` forces a dead lease, lets `b`
  reclaim (new `lease_id`), then asserts `a.commit_case(...)` raises `StudyLeaseLost` **and**
  `b.has_case("cand-X")` is False (`test_lease.py:35-56`). Static mutation trace: deleting the
  `store.py:270-271` check lets `a`'s INSERT proceed → no exception → both assertions flip →
  test RED. The test targets exactly that line. (Live mutation probe requested below to confirm
  RED/GREEN empirically.)
- **MF-2 (order-sensitive fingerprint).** `canonical_bytes` uses `sort_keys=True` but that only
  sorts *object keys*, never array element order (`identity.py:1-19`). `strategy_config` is
  encoded as an **ordered `[name, domain]` pair-array**, not a `{name: domain}` object
  (`strategy.py:57-61`). Confirmed `sort_keys` is NOT applied to the pair-array: reordering
  yields a different digest — `test_grid_config_is_order_sensitive` and the store-level
  `test_grid_reorder_is_new_lineage` (reorder → `IncompatibleStore`). ✔
- **Option A execution (D2).** `attempt_transitions` is one row per state change with a
  `transition_seq AUTOINCREMENT` global order (`store.py:54-60`); the `started` transition is
  written+committed *before* evaluate/stage/commit and terminal transitions *after* commit
  (`runner.py:90-93, 121-124, 150-153`); next attempt is `COALESCE(MAX(attempt_number),0)+1`,
  not `COUNT(*)` (`store.py:299-305`). Crashed-attempt forensics (a `started` row with no
  terminal row) are verified indirectly but soundly: `test_resume_identical` asserting the
  re-commit on `a2` requires the crashed `a1` `started` row to have survived
  (`test_crash_regimes.py:103`), and `test_retry_new_attempt` asserts the explicit
  `(1,started)` + `(1,retryable_failed)` + `(2,started)` + `(2,committed)` timeline.
- **GC safety.** Reference set = union of non-null `evidence_digest` across all committed cases
  (`store.py:419-425, 441`); a replicate-shared digest is counted once (set semantics), so a
  shared artifact is never collected; GC refuses while a lease is live (`store.py:437-439`);
  live-lease in-flight tmps are unreachable; dead/released-lease tmps become collectible. ✔

Other design decisions confirmed present: D3 injective reserved-key sentinel
(`evidence_io.py:20-32`, `test_reserved_key_rejected`), D5 NULL artifact ref for
`execution_failed`, D6 no cursor (only `runner_lease` is mutable), D7 retry limit 3 no backoff
(`runner.py:30, 71`), single-host contract line in the store docstring (NF-3), per-lease
staging subdir (NF-4). The four-phase failure-routing switch is written against the enum, with
`PREPARATION` re-raise kept as deliberate (unreachable-per-case) dead code per NF-1
(`runner.py:111-115`) — flagged in plan.md, matches the design's explicit instruction.

### Code integrity

No slop or leaky abstractions. Functions are single-purpose and their contracts read from the
signatures. `encode_evidence` keeps the reserved-key policy at the encoder (correct home), not
in a utility. Three minor observations (none block certification):

- **`runner.py:113-114` — `PREPARATION` re-raise is dead code by construction.** The design
  requires the switch shaped against all four phases for a future persisting backend; this is
  documented (plan.md Phase 3 notes, NF-1), not an oversight. Acceptable.
- **`store.py:232-243` — heartbeat thread has no per-iteration guard.** If the background
  `UPDATE runner_lease ... heartbeat_at` hits `sqlite3.OperationalError` (lock held past the
  30 s connection timeout), the exception unwinds the loop, `conn.close()` runs, and the thread
  dies silently — the lease then ages out and could be reclaimed under a still-live runner. The
  fence makes this *safe* (the next fenced write aborts), but it can surface as a spurious
  `StudyLeaseLost`. With TTL 30 s ≫ heartbeat 10 s this is unlikely; worth a comment or a
  narrow retry. Robustness note, not a correctness defect.
- **`store.py:170-172` — `_lease_is_dead` treats `PermissionError` on `os.kill(pid,0)` as
  not-dead-via-this-path, then falls through to TTL.** Correct (a PID-reused-by-another-user
  process must not be declared dead); the fall-through to TTL is the intended soft path.

---

## Notes (the "with-notes")

1. **Resume-identical crashes on the first candidate (cand-0).** `test_resume_identical`
   (`test_crash_regimes.py:93`) crashes at `before_commit:CAND(0)`, so no case is committed
   before the crash and resume re-runs the whole sequence. The ordered comparison is genuine,
   but the strongest form — crash *mid-sequence* so resume must skip already-committed cases
   **and** reproduce the tail in identical order against a baseline — is not asserted by any
   single test. The mid-sequence skip is exercised separately (`test_store_seam_mid_staging`
   asserts `has_case(cand-A)` true after a `cand-B` crash; `test_no_dangling_artifact` uses
   `mid_staging:cand-6`), but neither does a full ordered-equality against a baseline. Coverage
   gap, low risk given the store-layer skip proof.

2. **`not_assessed` completed class is proven via a test affordance, not real input.** The
   fixture aggregator has one fixed assertion (`constraint_report_aggregator.py:13`
   `EXPECTED_IDS`), so `results` is never empty and the `not_assessed` (`else`) branch
   (`:42-45`) is unreachable by input. plan.md flags this ("⚠️ Flagged finding") and resolves it
   with the design's already-blessed named-affordance pattern (a zero-assertion evaluator
   wrapper, `conftest.py:142-158`), owner-checked in the plan. This is a **surfaced, documented**
   scope handling consistent with how `execution_failed`/`assessment_failed`/retry are covered —
   not a silent cut. Recording it so certification is honest about which matrix cells are
   real-by-input (satisfied/violated/indeterminate) versus real-shaped-affordance
   (not_assessed/execution_failed).

3. **GC never positively tests unreferenced-artifact collection.** `test_gc_orphans_only`
   asserts `artifacts_collected == 0` (shared artifact kept). No test asserts that an artifact
   whose digest is in *no* committed case IS collected (`artifacts_collected > 0`), so the
   artifact-sweep branch (`store.py:448-452`) is exercised only in its "keep" direction.
   Likewise GC is only run after a *released* lease, never after a *dead-but-unreleased* lease
   (the reclaim path shares `_lease_is_dead`, so this is low risk). Coverage gap.

---

## Requested live probes (execution was blocked in this session)

Every `.venv/bin/python`, `python3`, and `uvx` invocation returned "requires approval" in this
non-interactive session, so the suite/gate claims and the fence mutation could not be run. The
static analysis above supports all of them; these confirm empirically. Run from repo root
`/home/reid/1cfe/teax`:

1. `.venv/bin/python -m pytest packages/teax-simkit/simkit/tests/study/ -q`
   → **expected: 29 passed** (test-function count verified by reading: 2+2+3+2+3+2+3+4+2+6 = 29).
2. `.venv/bin/python -m pytest packages/teax-simkit/simkit/tests/evaluation/ -q`
   → **expected: 25 passed** (baseline this item must keep green).
3. `.venv/bin/python -m pytest packages/teax-simkit/ -q`
   → **expected: green except exactly these 4 pre-existing node IDs** —
   `simkit/tests/test_no_battery_deps.py::{test_no_battery_imports_in_framework,
   test_no_battery_config_imports, test_no_load_profile_imports, test_no_geography_imports}`.
   Corroborated statically: those 4 subprocess-check tests hard-code `cwd="/home/reid/teax"`
   (`test_no_battery_deps.py:72,84,95,…`) while the repo lives at `/home/reid/1cfe/teax`, so they
   fail on a missing cwd — unrelated to Item 11.
4. `uvx ruff check packages/teax-simkit/simkit/study packages/teax-simkit/simkit/tests/study`
   → **expected: clean** (no local `ruff` binary in `.venv`; plan used `uvx`).
5. **Fence-teeth mutation probe (MF-1).** In `store.py:270-271`, comment out
   `if row is None or row["lease_id"] != self.lease_id: raise StudyLeaseLost(...)`, then run
   `.venv/bin/python -m pytest
   packages/teax-simkit/simkit/tests/study/test_lease.py::test_lease_fence_blocks_reclaimed_writer -q`
   → **expected: RED** (`DID NOT RAISE StudyLeaseLost`, and `b.has_case("cand-X")` becomes True).
   Revert → **GREEN**.

---

## Certification

**Checked (static, by reading source + tests against spec/design/plan):**
- All five S6 pass criteria mapped to kept tests; each drives the real evaluator (or is
  correctly store-only for the compatibility criterion); crash regimes use real `os._exit`
  subprocess deaths through the production runner, not mocked kills.
- Fence (MF-1), order-sensitive `strategy_config` (MF-2), Option A per-transition history +
  `COALESCE` derivation, GC reference-set safety, D3 injective sentinel, D5 NULL ref, D7 retry,
  WAL+FULL contract — all present and matching design rev 2.
- Full outcome matrix present; the `not_assessed` affordance and the retry/exec-fail/assess-fail
  affordances sit at the real seams, documented in plan.md.
- Non-goals respected; `simkit/evaluation/` unchanged; no placeholders/TODOs; plan phases
  genuinely complete; working tree clean.
- The `[OWNER]` Option A decision is executed as specified (rows per transition, `transition_seq`
  ordering, `COALESCE` on first attempt, crashed-attempt `started`-row-without-terminal
  forensics).

**Not checked (requires the live probes above — blocked this session):**
- Actual green runs of the study (29), evaluation (25), and framework suites, and that the
  framework failure set is *exactly* the 4 known node IDs (not, say, 5).
- `ruff` cleanliness empirically.
- The fence mutation going RED-then-GREEN empirically (traced statically; not executed).
- Runtime behavior of the real fixture evaluator for each budget (that 6000→satisfied,
  1000→violated, `nan`→indeterminate hold at runtime) — relied on Item 0 + the test assertions,
  not independently executed.
- Any concurrency/timing behavior of the heartbeat thread under real lock contention.

Spec/epic success-criteria checkboxes are left for the orchestrator to mark once probes 1–4
pass, since "green suite" is the one claim I could not verify by reading. Everything statically
verifiable is certified; the verdict is **Certify-with-notes** on that basis.

---

## Addendum: Probes 1–5 executed by orchestrator (2026-07-12)

- **P1 study suite:** 29 passed. **P2 evaluation suite:** 25 passed. **P3 framework:** failure set = exactly the four known `test_no_battery_deps.py` pre-existing failures.
- **P4 ruff:** `simkit/study` clean.
- **P5 fence mutation:** deleted the `store.py:270-271` lease check → exactly `test_lease_fence_blocks_reclaimed_writer` FAILED → revert → all lease tests green. The fence has teeth, empirically.

**Final verdict: Certify** (upgraded from Certify-with-notes; all runtime claims executed).
