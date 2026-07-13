# Spec: Study Store, Runner, and Strategies (Lists/Grids) — Item 11

**Status:** Draft
**Owner:** Reid W
**Created:** 2026-07-12
**Complexity:** HIGH
**Branch:** constraint-exec-epic

---

## Problem

The crash-safe study lifecycle is proven but still lives entirely in throwaway spike
code. Two spikes established its shape:

- **S6** built a SQLite study store with content-addressed artifact staging that survives
  hard `os._exit` crashes injected before case commit and mid artifact-staging, and on
  resume reproduces the uninterrupted run exactly — against a *fake* evaluator, which is
  where S6 said the lifecycle risk lives (`.project/active/spike-crash-safe-study-lifecycle/`).
- **Item 0** drove that same S6 machinery against S4's *real* sealed package through the
  S5-shaped evaluator with zero runner/store changes, and named the runner-side interface
  mismatches between the fake shape and the real one
  (`.project/active/constraint-study-integration-spike/findings.md`).

Item 10 is now CERTIFIED on this branch: `simkit/evaluation/` is a real evaluator —
`evaluate(typed_inputs) -> ModelEvidence`, a normalized `EvaluationFailed` taxonomy, Shape A
(instantiated-models-only) typed entry, and a canonical `satisfied | violated |
indeterminate | not_assessed` vocabulary. What does not yet exist is the production study
layer that sits on top of it: the `StudyDefinition`, the prepared list/grid strategies, the
fixed-order `StudyRunner`, the crash-safe `StudyStore` with its staging protocol and GC, and
— crucially — the S6 invariants proven as kept tests against the *real* evaluator, not only a
fake.

This item productionizes the S6 `study_lifecycle.py` shape and resolves the three runner-side
mismatches Item 0 assigned here (injected proposal-validation seam; proposal-validity as a
different axis from non-finite input; the strategy→candidate bridge that builds instantiated
entry models). It builds the store, runner, strategies, staging, and GC; it does **not** build
policy interpretation, query, or CLI (Item 12), and it does **not** touch adaptive strategies
or feedback crash semantics (S7).

## Success Criteria

- [ ] **All five S6 pass criteria hold as kept tests against the real Item 10 evaluator**, not
  only a fake: (1) resumed and uninterrupted runs produce identical ordered cases; (2) no
  logical candidate commits twice under `(study_id, candidate_id)`; (3) no committed case
  references a missing or half-written artifact; (4) invalid proposals persist as proposal
  records and never become cases; (5) opening the store with incompatible fingerprints fails.
- [ ] **The three S6 crash regimes are CI-runnable tests** driven against the real evaluator:
  crash-before-commit, crash-mid-staging, and resume-identical, using real `os._exit`
  child-process deaths and a fresh-process resume.
- [ ] **The full S6 outcome matrix re-runs against the real evaluator** — the four `completed`
  verdict classes (all-satisfied, violation, indeterminate via a non-finite operand,
  not-assessed/zero-assertions), an `execution_failed` case, an `assessment_failed` case with
  its real evidence preserved, deliberate replicates sharing one artifact, and a retry landing
  one committed case on a new `attempt_id`. (Item 0 exercised three verdict classes and
  crash-before-commit only; the rest had fake-evaluator coverage in S6 and must be re-pinned
  here.)
- [ ] **Changed anything mid-study starts a new lineage:** an incompatible-fingerprint reopen
  fails explicitly, and no reopen ever mixes datasets from two compatibility bindings.
- [ ] **GC collects exactly the orphaned staging garbage S6 characterized** (a truncated
  mid-staging `.tmp` whose bytes hash to no referenced digest) and never a content-addressed
  artifact shared by a committed replicate.

## Known Requirements

Grading note: items forced by how the *real* Item 10 evaluator API, SQLite, or the OS
durability primitives actually behave (several named by Item 0) are `[HARD]`; design intent
carried from the owner-ratified concept, the epic item, or an S6 review carry-forward is
`[INHERITED]` with its source cited. See `capture-fidelity.md`. One decision is deliberately
left open to the owner and marked `[RESERVED]`.

### `StudyDefinition`

- **[INHERITED]** A `StudyDefinition` selects variables and domains by parameter ID,
  observables by output ID, objectives, response roles, a failure policy, a strategy, a budget,
  and a retention policy; it **cannot redefine a predicate**. (concept "Study Layer"; epic
  Item 11 §1.)
- **[HARD]** Variable selection resolves to a **model field, not a flat parameter-ID→scalar
  map.** The real typed entry is two-level: the EntryPoint emits one structured channel
  (`toy_plant_params: ToyPlantParams`) whose *fields* are the contract parameter IDs. "Vary
  `plant_budget`" therefore selects a field of the entry channel's model. (Item 0 mismatch 1;
  `simkit/evaluation/entry_source.py` Shape A; the real `pipeline.yaml` entry block.)
- **[INHERITED]** A defaulted formal is an overridable contract parameter — eligible for
  explicit study selection, never automatically a study variable — and retains its modeled
  default when not selected. (concept Architectural Bets, strict resolution.)

### Strategies (prepared lists and grids)

- **[INHERITED]** Prepared lists and grids implement `propose`/`observe`. `observe` is inert
  for these strategies by design; the runner still calls it in order so the fixed order stays
  honest for later adaptive strategies. (epic Item 11 §2; concept `CandidateStrategy`.)
- **[HARD]** **Candidate minting is positional and must be documented as a contract, with its
  reason.** `candidate_id` is derived from the proposal's position in the sequence (S6:
  `c{index:04d}`), so resume idempotency *presupposes* a deterministic proposal order —
  guaranteed for prepared lists and grids. Content-based IDs are explicitly rejected because
  they would collapse deliberate replicates into one identity. (S6 carry-forward (2).)
- **[INHERITED]** **Deliberate replicates are distinct candidates.** Two proposals with
  identical inputs get distinct `candidate_id`s and share exactly one content-addressed
  artifact. (concept "Study Layer"; S6.)
- **[INHERITED]** **Three-layer identity:** `proposal_id` (raw strategy output),
  `candidate_id` (the validated logical evaluation), `attempt_id` (one execution try), with
  idempotency scoped to `(study_id, candidate_id)`. (concept "Study Layer".)

### `StudyStore`

- **[HARD]** SQLite with `journal_mode=WAL` and `synchronous=FULL` is a **store contract —
  required behavior, not an implementation detail** — because the crash-safety proof binds to
  exactly these journal settings. Both must be stated as contract in code and docs. (S6
  carry-forward (3).)
- **[INHERITED]** **Compatibility is bound immutably at store creation** over: the executable,
  model-contract, and study-definition fingerprints; the input and evidence schema versions;
  and the strategy identity plus its configuration under a **stable canonicalization**.
  Opening the store with any incompatible value fails explicitly; any change starts a new
  study lineage. (concept "Study Layer"; epic Item 11 §3; S6.)
- **[HARD]** `UNIQUE(study_id, candidate_id)` on the cases table enforces no-double-commit
  structurally, backed operationally by resume skipping any candidate that already has a
  committed case. (S6, kept invariant.)
- **[INHERITED]** Committed cases and attempt history are **append-only**; controlled mutable
  operational state (e.g. cursors) is kept **separate** from them. The probe derives resume
  position from committed cases and needs no cursor — confirm whether production keeps that
  property or introduces a cursor. (concept "Study Layer"; S6 open follow-up.)
- **[HARD]** **Content-addressed artifact staging protocol:** write to a staging tmp → `fsync`
  the file → atomic rename to the content-addressed final path → `fsync` the directory → then
  a **single DB transaction** inserts the case row referencing the durable digest. Database and
  filesystem writes cannot share a transaction, so the artifact is durable *before* the commit.
  (concept "Study Layer" invariant; S6 staging protocol.)
- **[HARD]** **Final-path-complete invariant:** an artifact present at its final content-
  addressed path is always complete, because the final path only ever appears via an atomic
  rename of a fully-`fsync`'d tmp; staging dedup may therefore trust `exists()` at the final
  path. State this in the store contract. (S6 carry-forward (3).)
- **[INHERITED]** A reader never sees a committed case pointing at a missing or half-written
  artifact. (concept Required Invariant "a committed case never references half-written
  artifacts".)

### Runner

- **[INHERITED]** **One fixed order:** validate/canonicalize the proposal → evaluate → assess
  the immutable evidence → stage the artifact durably → atomically commit the case → advance
  strategy feedback. Atomic case commit precedes feedback. (concept "Study Layer"; epic Item
  11 §4.)
- **[HARD]** **Proposal validation is an injected dependency**, carried by the
  `StudyDefinition`/runner, not a module-global function. (Item 0 mismatch 3: reusing S6's
  runner required monkeypatching a module global because there was no injection point.)
- **[HARD]** **Proposal validity means malformed / missing / wrong-type only — never
  non-finite.** A non-finite value is a *well-formed candidate* that the model evaluates to
  `indeterminate`; bouncing it as an invalid proposal would make the entire indeterminate
  verdict class unreachable. This matches Item 10, whose entry source lets non-finite floats
  through by construction. (Item 0 mismatch 2; `entry_source.py` "a non-finite float passes by
  construction".)
- **[INHERITED]** **Invalid proposals persist as append-only `ProposalRecord`s** keyed by
  `proposal_id`; they never reach the evaluator and never become cases. (concept "Study
  Layer"; epic Item 11 §4.)
- **[HARD]** **The evaluator protocol is `evaluate(typed_inputs) -> ModelEvidence` and carries
  no `attempt_number`.** Retry and attempt bookkeeping are runner-owned. (Item 0 mismatch 4;
  `simkit/evaluation/evaluator.py` `Evaluator` protocol.)
- **[HARD]** **The strategy→candidate bridge builds the instantiated entry model(s)** the
  evaluator consumes, under Shape A (the caller owns constructing each channel's typed model;
  the entry source only refuses a missing/extra/wrong-channel model). The bridge maps a
  validated candidate's selected fields onto the entry channel's model. (Item 0 findings;
  `entry_source.py` docstring, Shape A.)
- **[HARD]** **Evaluator failures surface as Item 10's `EvaluationFailed` / `EvaluationFailure`**
  (phase, cause, module-or-channel when known, `retryable`, partial-artifact status). The
  evaluator is deterministic and never sets `retryable=True`, so an evaluator failure is
  **terminal → an `execution_failed` case**. Retryable events are infrastructure/persistence
  failures the runner owns, retried under a new `attempt_id`. (`simkit/evaluation/failure.py`;
  concept "persistence fails … a retryable phase-tagged event, replay from the last commit".)
- **[INHERITED]** **A retry runs under a new `attempt_id`, same `candidate_id`;** failed
  attempts are preserved and a candidate commits at most one case. (concept idempotency; S6.)
- **[INHERITED]** **Three case states — `completed`, `execution_failed`, `assessment_failed` —
  never merge**, and assessment never mutates stored evidence; an `assessment_failed` case
  preserves the real evidence, not a stub. (concept Required Invariant "proposal records and
  the three case states never merge".)

### Assessment / policy boundary

- **[INHERITED]** The runner's assess step runs through a **pluggable, injected policy seam**
  sufficient to produce the three case states and to exercise `assessment_failed` in tests. The
  full study-policy protocol, result queries, and CLI are **Item 12**; this item delivers only
  the seam and a minimal policy adequate to drive the outcome matrix. (concept; epic Item 12
  scope — "Policy protocol, query API, CLI".)

### Staged evidence schema

- **[HARD]** **Staged evidence round-trips non-finite operands losslessly**, in a JSON-stable,
  content-addressable form. A committed case's referenced digest must re-hash to the present
  file's bytes, so the encoding must be canonical and deterministic. Item 10's `_json_safe`
  non-finite tag is explicitly **digest-input only, never the on-disk evidence encoding**, so
  Item 11 owns the on-disk choice. (Item 0 mismatch 6; `evaluator.py` `_json_safe` docstring.
  The exact encoding form is deferred — see Open Questions.)
- **[INHERITED]** Evidence is serialized for staging without importing any generated class into
  a runtime type. `ModelEvidence.report` is held opaque; serialization reads it, never depends
  on its generated type. (concept "runtime types never depend on generated classes"; Item 10
  `ModelEvidence`.)

### Lifecycle hygiene / GC

- **[INHERITED]** **Safe GC collects only artifacts unreferenced by any committed case.**
  Content-addressed artifacts may be shared by replicates, so collection is by "unreferenced by
  any committed case," **never by attempt**. (S6 findings, GC follow-up; epic Item 11 §5.)
- **[INHERITED]** **The durability boundary is stated in docs: `fsync`-before-return.** The
  protocol survives a killed process; it does **not** claim power-loss or disk-cache-loss
  safety. (S6 bounds of claim.)

### Crash tests

- **[INHERITED]** S6's three regimes are **CI-runnable kept tests** — crash-before-commit,
  crash-mid-staging, and resume-identical — using real `os._exit` child-process deaths and a
  fresh-process resume against the same DB and artifact directory. (epic Item 11 §6; brief.)
- **[HARD]** These crash tests run against the **real Item 10 evaluator**, not only the fake.
  Item 0 proved the seam holds and drove three verdict classes plus crash-before-commit against
  the real package; `execution_failed`, `assessment_failed`, zero-assertion, and the
  `mid_staging` phase against the real evaluator were **not** exercised there and must be
  covered here. (Item 0 "Not exercised" note; brief.)

### Attempt-history record granularity — `[RESERVED: owner decision at design]`

Attempt history is append-only *across attempts* — a superseded attempt (e.g. a crashed `a1`)
is never erased when `a2` supersedes it. That much is settled by the concept. The reserved
question is the granularity of a **single attempt's** record:

- **What S6's probe did:** one row per `attempt_id` (primary key `attempt_id`), updated in
  place via `INSERT OR REPLACE` — effectively **last-state-wins** within an attempt (`started`
  is overwritten by the terminal outcome). A crashed attempt that never recorded its outcome
  stays at `started`.
- **Option A — append-only-per-transition:** every attempt state change is its own row
  (`started`, then `committed`/`*_failed`), ordered. Strongest crash-resume forensics — a full
  timeline of what was in flight at the crash, and the only shape that stays unambiguous once an
  attempt has more than two transitions (relevant when adaptive strategies arrive, S7). Cost:
  more rows and a transition-ordering column.
- **Option B — last-state-wins:** one row per attempt carrying its final outcome (the probe's
  shape). Simpler and sufficient for every S6 pass criterion; loses the intra-attempt timeline.

**Requirements that hold under either option** (spec them now; the schema choice does not move
them): the crashed attempt is preserved in append-only attempt history; a candidate commits at
most one case under `(study_id, candidate_id)`; resume reproduces the uninterrupted run's
ordered cases; and attempt history stays separate from the controlled mutable operational
state (cursors) the concept keeps apart. The owner (Reid) decides A vs B at design; the spec
does not pick one.

## Non-Goals

- Adaptive/stateful strategies and general feedback crash semantics — S7 gates them, and a
  prepared-candidates strategy ignores feedback, so that claim would be unfalsifiable here.
- Study-policy interpretation protocol, result queries, and the CLI surface — Item 12.
- Power-loss / disk-cache-loss durability and block-layer fault injection — the claim is
  `fsync`-before-return only.
- Any change to the Item 10 evaluator, entry source, evidence, or failure types — Item 11
  consumes them as-is.

## Open Questions / Deferred to design

- **Attempt-history record granularity (A vs B above)** — `[RESERVED]` for the owner at design;
  listed here so it is not lost.
- **Canonical on-disk non-finite encoding** for staged evidence. The requirement (lossless,
  JSON-stable, content-addressable) is fixed above; the exact form is a design choice. The
  probe's `{"__nonfinite__": "nan"}` tag is one option, not a recommendation. (Item 0 mismatch
  6.)
- **Exact SQLite schema** — table columns, indices, and the operational-state (cursor) tables
  beyond the named `UNIQUE(study_id, candidate_id)` constraint and the append-only rule.
- **How much of the assessment/policy seam lands in Item 11 vs Item 12** — this item needs
  enough to produce the three case states; the shared seam shape is a design coordination point
  with Item 12.
- **Retry limit and backoff** for infrastructure-retryable failures (S6 used a fixed limit of
  3, no backoff).
- **GC trigger** — a manual operation, an on-open sweep, both — and how retention policy
  interacts with GC.
- **Confirming the compatibility fingerprint set is exactly the fields that start a new
  lineage**, and pinning the `strategy_config` canonicalization form. (S6 open follow-up.)

---

## Related Artifacts

- **Epic:** `.project/reference/epic_constraint_execution.md` (CONSTRAINT-EXEC, Item 11)
- **Required Reading:**
  - `.project/reference/constraint-execution-concept.md` — "Study Layer", Study Execution
    invariants, Vocabulary (owner-ratified concept-design)
  - `.project/active/spike-crash-safe-study-lifecycle/findings.md` + `study_lifecycle.py` — S6
    result, staging protocol, three-layer identity, and the four carry-forward follow-ups
  - `.project/active/constraint-study-integration-spike/findings.md` — Item 0 seam findings
    (runner-side mismatches 2, 3, 6 assigned to this item)
  - `simkit/evaluation/` — the CERTIFIED Item 10 evaluator API this item builds on
    (`evaluator.py`, `entry_source.py`, `evidence.py`, `failure.py`)
- **Design:** `.project/active/study-store-runner/design.md` (to be created)

---

**Next Steps:** After approval, proceed to `/_my_spec_review` (fresh session), then
`/_my_design`. The attempt-history granularity gate is the owner's to resolve at design.
