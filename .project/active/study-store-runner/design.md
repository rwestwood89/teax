# Design: Study Store, Runner, and Strategies (Lists/Grids) — Item 11

**Status:** Draft
**Owner:** Reid W
**Created:** 2026-07-12
**Branch:** constraint-exec-epic
**Base commit:** cd646dc

---

## Overview

Productionize the S6 crash-safe study lifecycle as a `simkit/study/` subpackage on top of the
certified Item 10 evaluator: a `StudyDefinition`, prepared list/grid strategies, a fixed-order
`StudyRunner`, a crash-safe SQLite `StudyStore` with content-addressed staging, a runner lease,
safe GC — and the S6 invariants proven as kept CI tests against the *real* evaluator.

## Related Artifacts

- **Spec:** `.project/active/study-store-runner/spec.md`
- **Epic:** `.project/reference/epic_constraint_execution.md` (CONSTRAINT-EXEC, Item 11)
- **Required Reading (background):**
  - `.project/reference/constraint-execution-concept.md` — "Study Layer", Study Execution invariants
  - `.project/active/spike-crash-safe-study-lifecycle/` — S6 `study_lifecycle.py` (the proven shape),
    `probe_crash_safe_study.py` (58-check oracle), `findings.md`
  - `.project/active/constraint-study-integration-spike/findings.md` + `real_evaluator.py` — Item 0
    seam findings and the real bridge shape
  - `packages/teax-simkit/simkit/evaluation/` — the certified Item 10 evaluator, consumed as-is

## Research Findings

- **The proven shape is `study_lifecycle.py`.** Store (`StudyStore`, staging protocol, compatibility
  binding), runner (fixed order), strategy (`PreparedCandidateStrategy`), policy, and crash controller
  are all there and green under 58 checks. Item 11 is a productionization + three named adaptations,
  not a redesign.
- **The evaluator is a pure function.** `Evaluator.evaluate(typed_inputs: Mapping[str, BaseModel]) ->
  ModelEvidence` (`evaluator.py:30`). It carries no `attempt_number`. Any module exception is wrapped
  into `EvaluationFailed(phase=MODULE_EXECUTION, retryable=False)` (`evaluator.py:114-120`); a
  missing/extra/wrong-type entry channel raises `EvaluationFailed(phase=ENTRY_VALIDATION)` with an
  `"expects {X}, got {Y}"` cause (`entry_source.py:47-66`). The evaluator *never* sets `retryable=True`
  (`failure.py:26-38`).
- **Typed entry is two-level (Shape A).** The EntryPoint emits one structured channel
  `toy_plant_params: ToyPlantParams` (`conftest.py:19`, fixture `pipeline.yaml`); its *fields*
  (`toy_plant__Toy_Plant__plant_budget`, …) are the contract parameter IDs, each a defaulted
  `float` field (`schemas/toy_plant_params.py:9-12`). The caller owns constructing the channel model;
  `entry_source.validate` only checks channel presence + `isinstance` (`entry_source.py:41-68`).
- **Evidence holds the generated report opaque.** `ModelEvidence` (`evidence.py:45-58`) carries
  `responses`, `outputs: Mapping[str,float]`, `provenance`, and `report: Any` — the generated
  `ConstraintReport` object, read only by attribute in `projection.py`, never imported as a type.
  Serializing it for staging is Item 11's job, and a non-finite operand lives inside that report.
- **The real evaluator is constructible in teax's own pytest** via `ProvisionalPackageLoader` over the
  in-repo fixture `simkit/tests/evaluation/fixtures/sealed_package/package_live` (`conftest.py:29-39`).
  No cross-repo venv needed.

## Core Concept

A **study** is a fixed, deterministic sequence of candidate evaluations recorded into a crash-safe
log. The whole design rests on one idea: **every logical result is content-addressed and committed by
exactly one atomic step, and every identity in the run is derived positionally**, so a killed process
that resumes in a fresh process reconstructs the *same* run by replay, not by recovering in-flight
state. The runner re-proposes the identical sequence, skips any candidate that already has a committed
case (idempotency keyed on `(study_id, candidate_id)`), and re-does the rest. Durability comes from a
strict ordering — stage the artifact durably (fsync tmp → atomic rename → fsync dir) *before* the
single DB transaction that writes the case row — so a crash can leave a durable-but-unreferenced
artifact (harmless, GC-collectable) but never a committed case pointing at a missing file.

Item 11 productionizes that S6 shape and makes three adaptations Item 0 named, plus two hardening
mechanisms the concept requires:

1. **Real typed entry (Shape A bridge).** A study variable selects a *field* of the entry channel
   model, not a flat scalar. A `CandidateBridge` builds the instantiated `ToyPlantParams` and keys it
   by channel name; Item 10's `entry_source` remains the type checker.
2. **Validity ≠ non-finite.** Proposal validation (an *injected* dependency) means malformed / missing
   / wrong-type only. A non-finite value is a well-formed candidate the model evaluates to
   `indeterminate`.
3. **Runner-owned failure routing.** `ENTRY_VALIDATION` is a runner/bridge *defect* (fail loud, never
   a case); `MODULE_EXECUTION` / `OUTPUT_WRITE` is a terminal `execution_failed` case; retry belongs to
   the runner and covers only store-I/O transients (the evaluator is never retryable).
4. **Single-writer runner lease** in operational state, with a liveness rule that lets a fresh runner
   promptly reclaim a *dead* lease on resume — the precondition that makes GC safe.
5. **Append-only-per-transition attempt history (Option A)** — every attempt state change is its own
   ordered row, for the strongest crash forensics.

It composes with the certified evaluator (evaluate + failure taxonomy + entry source + evidence, all
as-is), teax's pipeline executor (untouched, reached only through the evaluator), stdlib `sqlite3`, and
`hashlib`/`json` for content addressing. It builds no parallel mechanism for anything those already own.

## Key Bets

- **B1. Resume-by-replay is sound because proposal order is deterministic and identity is positional.**
  Prepared lists and grids emit a byte-stable proposal sequence across fresh processes, so re-proposing
  reconstructs the same `proposal_id`/`candidate_id` for every position. *If false → a resumed run mints
  different IDs, double-commits, or produces a non-reproducible proposals table; the entire idempotency
  proof collapses.*
- **B2. `fsync`-before-return gives crash safety against process death.** An artifact at its final
  content-addressed path is always complete because it only ever appears via atomic rename of a
  fully-fsync'd tmp; a case row is durable because WAL + `synchronous=FULL` fsyncs the commit. *If false
  → a resumed reader sees a half-written artifact or a torn case row.* (Bounded: process death, not
  power/disk-cache loss.)
- **B3. A dead lease is promptly and safely distinguishable from a live one.** On same-host resume the
  crashed runner's pid is provably gone; cross-host, a stale heartbeat past TTL marks it dead. PID reuse
  can only cause a *false-live* (refuse, safe-slow), never a false-dead (reclaim a live runner). *If
  false → either two runners write concurrently, or crash-resume/GC deadlocks against a dead lease.*
- **B4. The certified evaluator's per-case failure surface is exactly two phases** — `MODULE_EXECUTION`
  (any module raise) and `OUTPUT_WRITE` — plus `ENTRY_VALIDATION` for a bad entry model. *If false →
  the runner's failure-routing switch mis-classifies a real failure* (e.g. persists a bridge defect as
  an ordinary result, the exact bug the spec's loud-defect rule exists to prevent).

## Key Decisions

- **D1. Module layout: a `simkit/study/` subpackage mirroring `simkit/evaluation/`.** One module per
  concern (see Component Overview). *Rejected: extending `simkit/evaluation/` (conflates the pure
  evaluator with the stateful store; the evaluator's isolation-clean invariant INV1 forbids it) and a
  single `study.py` (the S6 file is already 25 KB and Item 12 extends it).*
- **D2. Attempt history = Option A, append-only-per-transition. `[OWNER]` (Reid, 2026-07-12,
  orchestrated-run gate).** Every attempt state change is its own ordered row (`started` →
  `committed`/`*_failed`) with a `transition_seq` ordering column. Rationale the owner endorsed:
  strongest crash forensics — a full timeline of what was in flight at the crash — and the only shape
  that stays unambiguous once an attempt gains more than two transitions (S7 adaptive strategies).
  *Rejected: Option B, last-state-wins (the S6 probe's `INSERT OR REPLACE` shape) — simpler and
  sufficient for every S6 pass criterion, but loses the intra-attempt timeline and becomes ambiguous
  under multi-transition attempts.* Consequence: the next attempt number is derived from
  `MAX(attempt_number)` for the candidate, **not** a row count (Option A has many rows per attempt).
- **D3. Non-finite on-disk encoding: canonical JSON with a recursive `{"__nonfinite__": tag}` sentinel,
  used for *both* the digest input and the on-disk bytes.** The staged file's bytes must re-hash to the
  referenced digest, so — unlike Item 10, where the tag is digest-input only — Item 11 makes the tag the
  actual encoding. *Rejected: `json.dumps(allow_nan=True)` (emits bare `NaN`/`Infinity`, non-standard
  JSON, not portably re-parseable, and defeats content-addressing) and storing a real float NaN (cannot
  round-trip through JSON at all).*
- **D4. Runner lease: an operational-state row with `lease_id` + heartbeat + pid/host, TTL-plus-pid
  liveness.** Acquire refuses a *live* lease (heartbeat within TTL) and reclaims a *dead* one (same-host
  pid gone, or heartbeat past TTL) by compare-and-swap on `lease_id`. *Rejected: bare pid+timestamp with
  no heartbeat (unreliable across hosts and PID reuse) and an OS advisory file lock (not visible in the
  DB, doesn't survive the reader/GC needing to reason about a dead owner).*
- **D5. `execution_failed` cases carry a NULL artifact reference and a `failure_json`.** They produced
  no evidence, so `evidence_digest` is NULL and the `EvaluationFailure` is stored as JSON. *Rejected:
  S6's shape (a synthetic `failure` dict staged as evidence with a real digest) — the spec's GC
  reference-set rule (L3-5) requires the no-evidence case to hold a null reference so GC counts only
  real evidence digests.* Consequence: `cases.evidence_digest` is nullable.
- **D6. No cursor; resume position is derived from committed cases.** The operational-state table holds
  only the lease. *Rejected: a persisted proposal cursor — redundant with the committed-case set the
  probe already resumes from, and a second source of truth the append-only invariant would have to
  guard.* (Confirms the S6 open follow-up: production keeps the no-cursor property.)
- **D7. Retry covers store-I/O transients only, fixed limit 3, no backoff.** The evaluator is never
  retryable (`failure.py`), so the only retryable events are transient persistence failures the runner
  owns (staging/commit `OSError`, SQLite `OperationalError`). *Rejected: retrying evaluator failures
  (deterministic — a retry fails identically) and a configurable backoff (deferred; S6's fixed limit is
  adequate for this item, tuning is noted for later).*

## Architecture

```
StudyDefinition ── selects ──▶ Strategy.propose() ──▶ (proposal_id, raw)
   (variables, domains,              │
    validator, policy,               ▼
    budget, retention)      Runner: validate ─▶ [invalid] ProposalRecord (append-only)
                                     │
                                [valid] ─▶ CandidateBridge ─▶ typed entry model
                                     │
                                     ▼
                          Evaluator.evaluate(typed_inputs) ─▶ ModelEvidence
                                     │                    └─▶ EvaluationFailed
                                     ▼                          ├ ENTRY_VALIDATION ─▶ StudyBridgeDefect (loud)
                          Policy.assess(evidence)               └ MODULE_EXECUTION/OUTPUT_WRITE ─▶ execution_failed case
                                     │  └─▶ AssessmentFailed ─▶ assessment_failed case (evidence preserved)
                                     ▼
                    StudyStore: stage artifact durably ─▶ atomic commit case ─▶ record transitions
```

**Data flow / boundaries.** The runner is the only writer; it holds the lease for its lifetime. It
drives the concept's one fixed order: validate/canonicalize → (bridge →) evaluate → assess → stage
durably → atomically commit → advance feedback (inert for prepared strategies, still called). Filesystem
and DB writes cannot share a transaction, so the store stages the artifact to durability first, then
commits the case row referencing the durable digest in a single SQLite transaction. Readers and GC
touch the store only through the committed-case set and the lease.

**Integration points.** The evaluator subpackage is consumed entirely through its public `evaluate` +
failure/evidence/entry types; the study layer never imports the generated package or the pipeline
executor directly. The crash seams live in the store's staging/commit path, strictly *downstream* of
`evaluate()`, so the certified evaluator is never modified.

## Required Invariants

- **INV-A. `UNIQUE(study_id, candidate_id)` on `cases`.** Structural no-double-commit, backed by resume
  skipping any candidate that already has a committed case.
- **INV-B. Final-path-complete.** An artifact at `artifacts/{digest}.json` is always complete and
  re-hashes to `{digest}`; staging dedup may trust `exists()` at the final path.
- **INV-C. Stage-before-commit ordering.** The case-row transaction runs only after the artifact is
  durable (tmp fsync → atomic rename → dir fsync). A crash between them leaves a durable orphan artifact,
  never a dangling case.
- **INV-D. Append-only.** Cases are append-only; attempt history is append-only per transition (Option
  A); operational state (the lease) is the only mutable table and is kept separate.
- **INV-E. Compatibility is immutable at creation.** Any incompatible reopen fails explicitly; no reopen
  ever mixes datasets from two compatibility bindings.
- **INV-F. Single writer.** At most one live runner holds a study; GC never runs against a live lease.
- **INV-G. Determinism.** The same strategy definition emits a byte-identical proposal sequence across
  two fresh processes (grids get an independent pin, not only the composite resume test).
- **INV-H. Lossless evidence round-trip.** A committed case's referenced digest re-hashes to the present
  file's bytes, non-finite operands included.

## Component Overview

`simkit/study/` (all new):

- **`definition.py` — `StudyDefinition`.** Selects variables/domains by parameter ID, observables by
  output ID, objectives, response roles; carries the **injected** proposal validator and policy, the
  strategy, budget, and retention. Cannot redefine a predicate. Variable selection names a *field* of
  the entry channel model.
- **`strategy.py` — `CandidateStrategy` protocol, `PreparedListStrategy`, `GridStrategy`.**
  `propose(study_id) -> Iterable[(proposal_id, raw)]` with positional `p{index:04d}` IDs; `observe`
  inert but called in order. `GridStrategy` enumerates the domain product row-major over declared
  variable order via `itertools.product` (never a set/hash-ordered structure).
- **`bridge.py` — `CandidateBridge`.** Maps a validated candidate's selected fields onto the entry
  channel model (`ToyPlantParams(**selected, **modeled_defaults)`), returns `{channel_name: model}`.
  Does not type-check; delegates that to `entry_source`.
- **`identity.py`.** Canonical JSON bytes, sha256 digests, positional ID minting.
- **`evidence_io.py`.** Serializes `ModelEvidence` for staging: dumps the opaque `report` by
  `model_dump(mode="json")`, applies the recursive non-finite sentinel (D3), and canonicalizes — without
  importing any generated class as a runtime type.
- **`compatibility.py` — `Compatibility`.** The eight-field binding (executable / model-contract /
  study-definition fingerprints, input & evidence schema versions, strategy identity + canonicalized
  config); bound once, checked on reopen.
- **`store.py` — `StudyStore`.** SQLite (`WAL` + `synchronous=FULL` as **contract**), staging protocol,
  lease acquire/heartbeat/reclaim, case commit, GC.
- **`runner.py` — `StudyRunner`.** The fixed order + failure-routing switch + retry loop.
- **`policy.py` — `Policy` protocol + a minimal `DispositionPolicy`.** Just enough to produce the three
  case states and exercise `assessment_failed`; the full policy/query/CLI is Item 12.
- **`failures.py`.** `IncompatibleStore`, `StudyLocked`, `StudyBridgeDefect`, `RetryableStoreError`.
- **`crash.py` — `CrashController`** (test affordance): `os._exit` at `mid_staging` / `before_commit`.

## Non-Goals

- Adaptive/stateful strategies and general feedback crash semantics (S7).
- Study-policy interpretation protocol, result queries, CLI (Item 12) — only the injected seam here.
- Power-loss / disk-cache-loss durability; block-layer fault injection. The claim is fsync-before-return.
- Any change to the Item 10 evaluator, entry source, evidence, or failure types.

## Implementation Notes

- **Attempt-number derivation (Option A gotcha):** `next_attempt_number = MAX(attempt_number) + 1` over
  the candidate's transition rows, not `COUNT(*)` (S6 counted rows; Option A has many rows per attempt).
- **Transition rows are individually durable.** Write and commit the `started` transition *before*
  evaluate/stage/commit, so a crash leaves a `started` row with no terminal transition — the forensic
  signature of an in-flight attempt. Same for terminal transitions after commit.
- **Failure-routing switch** (runner, after catching `EvaluationFailed`):
  ```
  if failure.phase == ENTRY_VALIDATION:  raise StudyBridgeDefect(failure)   # loud, never a case
  else:                                  commit execution_failed case (evidence_digest=NULL,
                                                                        failure_json=failure)
  ```
- **Evidence serialization** never imports the generated report type; it reads the already-dumped JSON
  and tags non-finite recursively. `outputs` are plain floats; a non-finite operand only appears inside
  the dumped `report`.
- **Staging layout:** `root/staging/{lease_id}/{attempt_id}.tmp` → `root/artifacts/{digest}.json`. The
  per-lease subdir carries lease identity, the filename carries attempt identity — so a crashed orphan
  tmp is attributable to its (now dead) lease, distinct from a live runner's in-flight tmp (closes
  L2-1). Dedup checks `exists()` at the final path first (INV-B).
- **WAL + synchronous=FULL are contract:** set on every open and asserted; state in the module docstring
  and store contract that the crash-safety proof binds to exactly these settings.
- **strategy_config canonicalization:** canonical-JSON digest of the strategy's config (the proposals
  list for a list; the ordered variable→domain map for a grid) — stable across processes.

## Potential Risks

- **The deterministic toy package cannot natively raise or fail assessment**, so `execution_failed`,
  `assessment_failed`, and the store-transient retry cannot be triggered by a real *input* alone. See
  Validation Approach for how the real evaluator is still the system under test. This is the sharpest
  point for the design review.
- **Lease reclaim correctness.** The pid-liveness fast path must guard on hostname (a recorded pid is
  only meaningful on the same host). Cross-host relies on TTL; a too-short TTL could reclaim a slow-but-
  live runner. Mitigation: TTL ≫ heartbeat interval (default 30 s vs 10 s), and reclaim is CAS on
  `lease_id` so a racing live owner's write wins.
- **Non-finite encoding drift.** If `evidence_io` and the digest use different canonicalizations, INV-H
  breaks silently. Mitigation: one function produces the bytes; the digest is `sha256` of exactly those
  bytes (single source, as in S6's `_stage_artifact`).

## Integration Strategy

New subpackage; nothing existing changes. `simkit/evaluation/` is imported read-only. Crash tests live
under `simkit/tests/study/` and drive a small CLI child module (mirroring S6's `run --db --crash-at`)
that constructs the real `PreparedEvaluator` over the in-repo fixture package. Item 12 extends the
policy seam and adds query/CLI without reshaping the store.

## Validation Approach

The S6 probe's 58 checks are the behavioral oracle. Each maps to a named `pytest` under
`simkit/tests/study/`, run against the **real** evaluator over the in-repo fixture package (Appendix B
gives the full map). The system under test is always the real evaluator + real evidence + real failure
taxonomy; where the deterministic package cannot itself produce a failure, the trigger is a **thin,
named fault at the exact seam the real evaluator genuinely uses**, not a fake evaluator:

- **`execution_failed`:** a test-only `Evaluator` that delegates to `PreparedEvaluator` and, for one
  designated candidate, raises the authentic `EvaluationFailed(EvaluationFailure(phase=MODULE_EXECUTION,
  retryable=False))` — the identical exception `evaluator.py:114-120` raises when a real module throws.
  Tests the runner's terminal-failure routing against the real failure type. *Alternative — a second
  fixture package whose module raises — is heavier and deferred; noted for the review.*
- **`assessment_failed`:** the **real** evaluator returns real evidence; the injected minimal policy
  rejects a designated candidate, so the case preserves real evidence (exactly the criterion's intent).
- **retry / new `attempt_id`:** a transient store-I/O fault injected on the first persistence attempt
  (raises `RetryableStoreError`), succeeding on the second — real evaluator, real evidence.
- **crash regimes** (`crash-before-commit`, `crash-mid-staging`, `resume-identical`): real `os._exit`
  child deaths and fresh-process resume, seams in the store path downstream of a completed real
  `evaluate()`.

A tiny fake evaluator is kept **only** for fast pure-runner-state-machine unit tests (ID minting,
switch branches) where a full package load would dominate; it is never the oracle for a success
criterion. CI command: `pytest packages/teax-simkit/simkit/tests/study/`.

## Next-Stage Handoff

- **Fixed:** the `simkit/study/` layout (D1); Option A attempt schema (D2, `[OWNER]`); the non-finite
  sentinel encoding (D3); the lease model (D4); NULL artifact ref for `execution_failed` (D5); no cursor
  (D6); the failure-routing switch; the eight-field compatibility binding; WAL+FULL as contract.
- **Open (design-review targets):** the exact TTL/heartbeat numbers; whether the review accepts the
  named-fault approach for `execution_failed` vs. demanding a raising fixture package; retention↔GC
  interaction (spec left it open — this item ships GC of orphans + unreferenced artifacts, retention
  policy interpretation is minimal).
- **De-risk first:** stand up the store + staging + lease and re-run the S6 crash regimes against the
  real evaluator *before* building strategies/definition — that path carries B1/B2/B3 and is where the
  productionization risk concentrates.

## Appendix A — SQLite schema (DDL sketch)

```sql
CREATE TABLE compatibility (            -- singleton, bound once at creation (INV-E)
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  study_id TEXT NOT NULL,
  executable_fingerprint TEXT NOT NULL, model_contract_fingerprint TEXT NOT NULL,
  study_definition_fingerprint TEXT NOT NULL, input_schema_version TEXT NOT NULL,
  evidence_schema_version TEXT NOT NULL, strategy_identity TEXT NOT NULL,
  strategy_config TEXT NOT NULL);

CREATE TABLE proposals (                -- append-only; idempotent re-persist (INSERT OR IGNORE)
  proposal_id TEXT PRIMARY KEY, raw_json TEXT NOT NULL,
  valid INTEGER NOT NULL, reject_reason TEXT, candidate_id TEXT);

CREATE TABLE attempt_transitions (      -- Option A: one row per state change (D2, INV-D)
  transition_seq INTEGER PRIMARY KEY AUTOINCREMENT,   -- global order (crash timeline)
  attempt_id TEXT NOT NULL, candidate_id TEXT NOT NULL, proposal_id TEXT NOT NULL,
  attempt_number INTEGER NOT NULL,
  state TEXT NOT NULL);                  -- started | committed | execution_failed
                                         -- | assessment_failed | retryable_failed
CREATE INDEX ix_attempt_by_candidate ON attempt_transitions(candidate_id, attempt_number);

CREATE TABLE cases (                     -- append-only; one committed case per candidate (INV-A)
  commit_order INTEGER PRIMARY KEY AUTOINCREMENT,
  study_id TEXT NOT NULL, candidate_id TEXT NOT NULL, proposal_id TEXT NOT NULL,
  attempt_id TEXT NOT NULL, state TEXT NOT NULL,       -- completed|execution_failed|assessment_failed
  inputs_json TEXT NOT NULL,
  evidence_digest TEXT,                  -- NULL for execution_failed (D5); GC ref set = non-null (L3-5)
  failure_json TEXT,                     -- the EvaluationFailure for execution_failed
  assessment_json TEXT,
  UNIQUE (study_id, candidate_id));

CREATE TABLE runner_lease (              -- the ONLY mutable operational state (INV-D, INV-F)
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  lease_id TEXT NOT NULL, pid INTEGER NOT NULL, hostname TEXT NOT NULL,
  acquired_at REAL NOT NULL, heartbeat_at REAL NOT NULL, released INTEGER NOT NULL DEFAULT 0);
```

Lease acquire (pseudocode): read row; if none/released → CAS-insert. Else if
`heartbeat_at` within TTL → **live** → raise `StudyLocked`. Else if (same host and `os.kill(pid,0)`
raises `ESRCH`) or `heartbeat_at` past TTL → **dead** → CAS-replace `lease_id`. GC: refuse unless the
lease is released or dead; then collect `staging/{dead_lease}/*.tmp` and any
`artifacts/{digest}.json` whose digest is in no committed case's non-null `evidence_digest`.

## Appendix B — S6 criterion → kept-test map (oracle)

| S6 pass criterion (58-check oracle) | Kept test (`simkit/tests/study/`) | Evaluator path |
|---|---|---|
| Resumed == uninterrupted ordered cases | `test_resume_identical` | real + `os._exit` resume |
| No double-commit `(study_id, candidate_id)` | `test_no_double_commit` | real |
| No case → missing/half-written artifact | `test_no_dangling_artifact` (both crash legs) | real |
| Invalid proposal stays a record | `test_invalid_proposal_record` | real |
| Incompatible fingerprint reopen fails | `test_incompatible_reopen_fails` | n/a (store) |
| crash-before-commit | `test_crash_before_commit` | real child death |
| crash-mid-staging (final absent, truncated tmp) | `test_crash_mid_staging` | real child death |
| Four `completed` classes (satisfied/violation/indeterminate/not-assessed) | `test_completed_matrix` | real |
| `execution_failed` case | `test_execution_failed` | real + named MODULE_EXECUTION fault |
| `assessment_failed`, real evidence preserved | `test_assessment_failed` | real + policy rejection |
| Deliberate replicates share one artifact | `test_replicates_share_artifact` | real |
| Retry lands one case on a new `attempt_id` | `test_retry_new_attempt` | real + store-transient fault |
| Grid determinism across two processes (INV-G) | `test_grid_determinism_pin` | strategy only |
| GC collects orphan tmp, never a shared artifact | `test_gc_orphans_only` | store only |

---
Next Step: After approval → `/_my_design_review` (fresh session), then `/_my_plan`.
