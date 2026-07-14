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
- **B3. Two independent signals mark a lease dead, and neither can reclaim a lease whose owner might
  still write.** Pid-death (same host, `os.kill(pid,0)` → `ESRCH`) is a *hard* guarantee the owner will
  never write again; TTL expiry is a *soft* signal that only becomes safe once every store write is
  fenced on `lease_id` (a reclaimed owner's write fails the fence and aborts — see D4/MF-1). PID reuse
  can only cause a *false-live* (refuse, safe-slow), never a false-dead. *If false → either two runners
  write concurrently, or crash-resume/GC stalls against a dead lease.* (TTL expiry alone, unfenced,
  would be unsound: a live-but-stalled owner past TTL would be reclaimed and then keep writing.)
- **B4. Under the `PreparedEvaluator` (`persist_outputs=False`), the certified evaluator's *per-case*
  failure surface is exactly `MODULE_EXECUTION`** — any module raise is wrapped into it
  (`evaluator.py:112-120`). `ENTRY_VALIDATION` is a bad entry model (a bridge defect); `PREPARATION`
  fails at prepare/startup before any candidate; `OUTPUT_WRITE` is unreachable with no persistence. *If
  false → the runner's failure-routing switch mis-classifies a real failure* (e.g. persists a bridge
  defect as an ordinary result, the exact bug the spec's loud-defect rule exists to prevent).

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
  `COALESCE(MAX(attempt_number), 0) + 1` for the candidate, **not** a row count (Option A has many rows
  per attempt; bare `MAX(...)+1` is NULL on the first attempt — MF-4).
- **D3. Non-finite on-disk encoding: canonical JSON with a recursive `{"__nonfinite__": tag}` sentinel,
  used for *both* the digest input and the on-disk bytes.** The staged file's bytes must re-hash to the
  referenced digest, so — unlike Item 10, where the tag is digest-input only — Item 11 makes the tag the
  actual encoding. *Rejected: `json.dumps(allow_nan=True)` (emits bare `NaN`/`Infinity`, non-standard
  JSON, not portably re-parseable, and defeats content-addressing) and storing a real float NaN (cannot
  round-trip through JSON at all).* **Injectivity (MF-3):** because Item 12's query layer *decodes* this
  form (unlike Item 10, where the tag was digest-input-only and never read back), the encoding must be
  injective — `"__nonfinite__"` is a **reserved key**. The encoder rejects loudly (`ValueError`) if a
  genuine value inside the opaque `report` is itself a one-key mapping `{"__nonfinite__": …}`, so no real
  value is ever silently reconstructed as a non-finite float. We reject rather than escape: the generated
  `ConstraintReport` is a typed schema that cannot emit this key, so a collision means an unexpected
  report shape that must fail rather than be papered over. Item 12 decodes on the same reserved-key
  contract.
- **D4. Runner lease is a fenced operational-state row: `lease_id` + heartbeat + pid/host, and every
  store write is fenced on `lease_id` (MF-1).** Acquire refuses a *live* lease (heartbeat within TTL) and
  reclaims a *dead* one (same-host pid gone, or heartbeat past TTL) by compare-and-swap on `lease_id`,
  minting a **new** `lease_id`. The reclaim signal alone is not enough to be safe, because a live-but-
  stalled owner (a slow evaluation or disk pause exceeding TTL) can be past TTL yet still about to write.
  So **fencing is the actual guarantee, not the TTL**: the case-commit transaction — and every
  transition/proposal insert — runs `... WHERE (SELECT lease_id FROM runner_lease WHERE singleton=1) =
  :my_lease_id` (or an equivalent in-transaction guard) and aborts loudly (`StudyLeaseLost`) if the row
  no longer holds `:my_lease_id`. A reclaimed stalled runner therefore fails its next fenced write,
  observes the lease loss, and aborts instead of double-writing. Heartbeat is a **background thread**
  updating `heartbeat_at` at an interval **≪ TTL** (default 10 s heartbeat, 30 s TTL), so a healthy
  runner's lease never ages out mid-evaluation and only a genuinely stalled/dead runner trips reclaim.
  *Rejected: bare pid+timestamp with no heartbeat (unreliable across hosts and PID reuse); TTL reclaim
  without fencing (unsound — reclaims a stalled-but-live owner that then keeps writing); an OS advisory
  file lock (not visible in the DB, doesn't survive the reader/GC needing to reason about a dead owner).*
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
- **D8. `strategy_config` encodes the *declared variable order* as an order-sensitive array of
  `[name, domain]` pairs, not a sorted mapping (MF-2).** A grid's proposal order comes from
  `itertools.product` over the *declared* variable order, so declared order is part of the study's
  identity. S6's `canonical_bytes` used `sort_keys=True`, which sorts variable keys alphabetically and
  discards declared order — so two grids declaring the same variables in a different order would digest
  identically yet enumerate a different proposal sequence, and a reopen would pass the compatibility
  check while re-proposing in a new order, remapping every positional `candidate_id` (silent resume
  corruption). Encoding `strategy_config` (and any order-bearing part of `study_definition_fingerprint`)
  as an ordered pair-array makes the order-bearing bytes order-sensitive by construction. **Consequence:
  reordering the declared variables is a new study lineage — correct, because the proposal order, and
  therefore positional identity, changes.** *Rejected: a `sort_keys` object over the variable→domain map
  (order-insensitive; the exact bug above) and hashing the enumerated proposal sequence itself (larger,
  and redundant with `study_definition_fingerprint`).* This is the property positional minting (INV-G,
  B1) rests on.

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
                          Policy.assess(evidence)               └ MODULE_EXECUTION (or any non-ENTRY phase) ─▶ execution_failed case
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
- **INV-F. Single fenced writer.** At most one runner holds the current `lease_id`; every store write is
  fenced on it and aborts (`StudyLeaseLost`) if reclaimed, so even a stalled-then-reclaimed runner cannot
  double-write. GC never runs against a live lease, and never touches a live lease's in-flight tmps.
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
  config); the config canonicalization is **order-preserving** for grids (D8). Bound once, checked on reopen.
- **`store.py` — `StudyStore`.** SQLite (`WAL` + `synchronous=FULL` as **contract**), staging protocol,
  lease acquire/heartbeat(-thread)/reclaim with **fenced writes** (D4), case commit, GC.
- **`runner.py` — `StudyRunner`.** The fixed order + failure-routing switch + retry loop.
- **`policy.py` — `Policy` protocol + a minimal `DispositionPolicy`.** Just enough to produce the three
  case states and exercise `assessment_failed`; the full policy/query/CLI is Item 12.
- **`failures.py`.** `IncompatibleStore`, `StudyLocked`, `StudyLeaseLost`, `StudyBridgeDefect`,
  `RetryableStoreError`.
- **`crash.py` — `CrashController`** (test affordance): `os._exit` at `mid_staging` / `before_commit`.

## Non-Goals

- Adaptive/stateful strategies and general feedback crash semantics (S7).
- Study-policy interpretation protocol, result queries, CLI (Item 12) — only the injected seam here.
- Power-loss / disk-cache-loss durability; block-layer fault injection. The claim is fsync-before-return.
- Any change to the Item 10 evaluator, entry source, evidence, or failure types.

## Implementation Notes

- **Attempt-number derivation (Option A gotcha):** `next_attempt_number = COALESCE(MAX(attempt_number),
  0) + 1` over the candidate's transition rows, not `COUNT(*)` (S6 counted rows; Option A has many rows
  per attempt). The `COALESCE` matters: bare `MAX(...)+1` is NULL on the first attempt (MF-4).
- **Fenced writes (MF-1):** the case-commit transaction and every transition/proposal insert include an
  in-transaction guard on the current `lease_id` and raise `StudyLeaseLost` if it no longer equals the
  writer's `lease_id`. A stalled runner that was reclaimed wakes, fails its next fenced write, and aborts
  — it never double-writes. Heartbeat runs on a **background thread** at an interval ≪ TTL so a healthy
  slow evaluation never ages the lease out.
- **Transition rows are individually durable.** Write and commit the `started` transition *before*
  evaluate/stage/commit, so a crash leaves a `started` row with no terminal transition — the forensic
  signature of an in-flight attempt. Same for terminal transitions after commit.
- **Failure-routing switch** (runner, after catching `EvaluationFailed`). The failure enum has four
  phases (`failure.py:13-24`: `ENTRY_VALIDATION, PREPARATION, MODULE_EXECUTION, OUTPUT_WRITE`), but under
  the `PreparedEvaluator` (`persist_outputs=False`) the *per-case* surface is `MODULE_EXECUTION` only:
  `PREPARATION` fails at evaluator construction/startup (fail-loud, before any candidate, never a case)
  and `OUTPUT_WRITE` is unreachable with no persistence (NF-1). The switch is written against the enum,
  not against "two phases":
  ```
  if failure.phase == ENTRY_VALIDATION:  raise StudyBridgeDefect(failure)   # bridge defect, loud, never a case
  elif failure.phase == PREPARATION:     raise                              # startup fault, not a case
  else:  # MODULE_EXECUTION (today) / OUTPUT_WRITE (future persisting backend)
         commit execution_failed case (evidence_digest=NULL, failure_json=failure)
  ```
- **Evidence serialization** never imports the generated report type; it reads the already-dumped JSON
  and tags non-finite recursively, rejecting a reserved-key collision (D3). `outputs` are plain floats; a
  non-finite operand only appears inside the dumped `report`.
- **Staging layout:** `root/staging/{lease_id}/{attempt_id}.tmp` → `root/artifacts/{digest}.json`. The
  per-lease subdir carries lease identity, the filename carries attempt identity — so a crashed orphan
  tmp is attributable to its (now dead) lease, distinct from a live runner's in-flight tmp (closes L2-1).
  The `staging/{lease_id}/` subdir is created with `mkdir(parents=True, exist_ok=True)` at lease-acquire
  (S6 wrote directly into `staging_dir`; the per-lease dir is new — NF-4). Dedup checks `exists()` at the
  final path first (INV-B).
- **WAL + synchronous=FULL are contract:** set on every open and asserted; state in the module docstring
  and store contract that the crash-safety proof binds to exactly these settings. **Store contract line
  (NF-3):** the store is single-host — the lease/GC reasoning and SQLite+WAL durability assume a local
  filesystem; a network filesystem is out of contract (SQLite+WAL is unreliable on NFS, and the pid-
  liveness fast path is meaningless cross-host). Cross-host is a bounded corner served only by the TTL
  path, not a supported deployment.
- **strategy_config canonicalization (D8):** a stable digest of the strategy's config — the proposals
  list for a list; for a grid, an **order-sensitive array of `[name, domain]` pairs** in declared
  variable order (never a `sort_keys` object, which would discard order and admit a silent resume
  remap). Stable across processes.

## Potential Risks

- **The deterministic toy package cannot natively raise or fail assessment**, so `execution_failed`,
  `assessment_failed`, and the store-transient retry cannot be triggered by a real *input* alone (Item 0
  confirmed the real package returns `indeterminate` on a non-finite operand and never raises). See
  Validation Approach for how the real evaluator is still the system under test.
- **Lease reclaim correctness rests on fencing, not on TTL tuning.** A live-but-stalled runner past TTL
  can be reclaimed; the fencing guard (D4) makes that safe — its next write fails `StudyLeaseLost` and it
  aborts. The pid-liveness fast path still guards on hostname (a recorded pid is only meaningful on the
  same host). Residual risk is narrow: a reclaimed runner mid-`os.replace` of a tmp GC just deleted — but
  the fenced commit that would reference that artifact fails, so no case ever points at it. Mitigation:
  TTL ≫ heartbeat interval (30 s vs a 10 s background heartbeat) so healthy runs never trip reclaim, plus
  fencing for the stalled case.
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
  retryable=False))`. That a *real module raise* actually surfaces as `MODULE_EXECUTION` is not an
  Item-11 assumption — it is already certified in Item 10: `evaluator.py:112-120` wraps *any* exception
  from `_executor.run` into `MODULE_EXECUTION` (NF-2/B4). So the named fault raises byte-for-byte what a
  real module throw produces, and it exercises the runner's terminal-failure routing against the real
  failure type without needing a package that raises. *Alternative — a second fixture package whose
  module raises — would close it end-to-end but is not required given Item 10's coverage; deferred.*
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

- **Fixed:** the `simkit/study/` layout (D1); Option A attempt schema with `COALESCE` derivation (D2,
  `[OWNER]`; MF-4); the injective non-finite sentinel with a reserved key (D3, MF-3); the **fenced** lease
  model with a background-thread heartbeat (D4, MF-1); NULL artifact ref for `execution_failed` (D5); no
  cursor (D6); the order-preserving grid canonicalization (D8, MF-2); the four-phase failure-routing
  switch (NF-1); the eight-field compatibility binding; WAL+FULL as contract; the single-host store
  contract (NF-3).
- **Open (design-review targets):** the exact TTL/heartbeat numbers (30 s / 10 s are defaults, tunable);
  retention↔GC interaction (spec left it open — this item ships GC of orphans + unreferenced artifacts,
  retention policy interpretation is minimal). The named-fault approach for `execution_failed` is now
  grounded in Item 10's certified `MODULE_EXECUTION` wrapping (NF-2), so the raising-fixture alternative
  is optional, not a gate.
- **De-risk first:** stand up the store + staging + **fenced lease** and re-run the S6 crash regimes
  against the real evaluator *before* building strategies/definition — that path carries B1/B2/B3. **Fold
  the MF-1 fencing test (`test_lease_fence_blocks_reclaimed_writer`) and the MF-2 reorder-rejection test
  (`test_grid_reorder_is_new_lineage`) into this first slice**, since both live in exactly that path.

## Appendix A — SQLite schema (DDL sketch)

```sql
CREATE TABLE compatibility (            -- singleton, bound once at creation (INV-E)
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  study_id TEXT NOT NULL,
  executable_fingerprint TEXT NOT NULL, model_contract_fingerprint TEXT NOT NULL,
  study_definition_fingerprint TEXT NOT NULL, input_schema_version TEXT NOT NULL,
  evidence_schema_version TEXT NOT NULL, strategy_identity TEXT NOT NULL,
  strategy_config TEXT NOT NULL);       -- order-preserving digest for grids (D8): a reorder is a new lineage

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

**Lease acquire** (pseudocode): read row; if none/released → CAS-insert a fresh `lease_id`. Else if
`heartbeat_at` within TTL → **live** → raise `StudyLocked`. Else if (same host and `os.kill(pid,0)`
raises `ESRCH`) or `heartbeat_at` past TTL → **dead** → CAS-replace with a fresh `lease_id`. A
background thread updates `heartbeat_at` every ~10 s (TTL ~30 s).

**Fenced write** (MF-1) — every case-commit / transition / proposal insert runs inside one transaction
that first re-reads the lease and aborts if reclaimed:
```sql
-- inside the same transaction as the case INSERT:
SELECT lease_id FROM runner_lease WHERE singleton = 1;   -- must equal :my_lease_id, else raise StudyLeaseLost
INSERT INTO cases (...) VALUES (...);                     -- only reached when the fence holds
```
A stalled-then-reclaimed runner fails this fence and aborts — it cannot double-write. `UNIQUE(study_id,
candidate_id)` remains the structural backstop for a same-candidate race.

**GC**: refuse unless the lease is `released` or **dead** by the acquire rule above — GC never runs while
a lease is live, so a live runner's in-flight `staging/{live_lease}/*.tmp` are untouchable. Only after a
lease is reclaimed/dead do its `staging/{dead_lease}/*.tmp` become collectible; GC also collects any
`artifacts/{digest}.json` whose digest is in no committed case's non-null `evidence_digest` (replicate-
shared digests counted once, so a shared artifact is never collected — L3-5).

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
| Reclaimed-lease writer fails the fence, never double-writes (MF-1, INV-F) | `test_lease_fence_blocks_reclaimed_writer` | store only |
| Variable reorder is rejected as incompatible (MF-2, INV-G) | `test_grid_reorder_is_new_lineage` | store + strategy |

The first two added rows (fencing, reorder-rejection) fold into the de-risk-first slice below, since both
live in exactly the store+lease path stood up first.

---
Next Step: After approval → `/_my_design_review` (fresh session), then `/_my_plan`.
