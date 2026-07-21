# Spec: Model Evaluator and Typed Entry — Production API (Item 10)

**Status:** Draft
**Owner:** Reid W
**Created:** 2026-07-12
**Complexity:** HIGH
**Branch:** constraint-exec-epic

---

## Problem

The constraint-execution architecture is proven end to end but its runtime seam still lives
in throwaway spike code. Two spikes established the shape:

- **S5** proved TEAx can prepare a constraint-free graph once, then evaluate ~100 typed
  in-memory entry mappings with a fresh execution context per case, matching file-backed
  outputs exactly, rejecting invalid mappings before any module runs, and writing nothing in
  no-persist mode (`.project/active/spike-teax-typed-entry-scalar-continuity/findings.md`).
- **Item 0** drove S6's study lifecycle against S4's *real* sealed package through an
  S5-shaped evaluator, confirming the seam holds with zero changes to the runner/store logic
  and naming eight schema/naming/wiring mismatches between the spike shapes and the real
  package (`.project/active/constraint-study-integration-spike/findings.md`).

What does not yet exist is the production runtime the study layer (Item 11) will build on: a
typed in-memory entry source, a prepared-pipeline backend with the file-backed path kept for
audit, an immutable evidence envelope that never depends on generated classes, and one
normalized failure outcome that keeps "the design is infeasible" (evidence) separate from
"the run broke" (failure). Item 0's eight mismatches are the concrete gap list: each is a
schema/naming/wiring detail the production API must resolve now, before Item 11 freezes its
store schema against this evaluator.

This item productionizes that seam. It is the teax half of the "Contracts and the Evaluator"
concept section; it does not build the study store, runner, strategies, or policy (Item 11+).

## Success Criteria

- [x] **S5 invariants are kept teax tests:** mapping-vs-file case-level parity; pre-execution
  rejection of an invalid typed input (missing/extra/wrong-type) before any module runs;
  execution-context isolation across cases; and no output directory created when persistence is
  off.
- [x] **S4-lineage packages evaluate to evidence:** evaluating a sealed generated package
  (Item 0's setup now; Item 9's sealed output when it lands) returns `ModelEvidence` whose
  constraint verdicts are projected onto generic response keys using the runtime-owned canonical
  vocabulary pinned in this item (`satisfied | violated | indeterminate | not_assessed`), with
  the full generated report attached as an opaque artifact and no generated class imported by
  any runtime type. This is closable in Item 10 — the vocabulary is pinned here, not deferred to
  Item 9.
- [x] **Runtime never depends on generated classes (kept isolation test):** an import scan of
  the runtime evidence and entry-source modules finds no reference to any generated symbol; the
  modules import and construct evidence with the generated package absent from the path.
- [x] **Three phases are distinguishable:** a module exception, a schema-validation rejection
  at entry (`entry_validation` phase), and an infeasible (`indeterminate`) verdict land in three
  distinguishable places — the first two as the normalized failure outcome with different
  phase/cause (`module_execution` vs `entry_validation`), the third as ordinary evidence, never
  a failure.
- [x] **Non-finite input reaches the verdict, not the guard:** a well-formed candidate with a
  non-finite value (e.g. a NaN budget) passes entry validation and evaluates to
  `indeterminate` — it is never rejected as invalid input.
- [x] **Both backends agree (kept parity test):** the prepared in-memory backend and the
  file-backed backend return the equivalent-class-equal result (defined in Known Requirements)
  for the same canonical inputs, with the NaN/indeterminate case in the fixture set.
- [ ] S5's `RootModel[float]` continuity regression test is committed — **already discharged
  this run** (S5 carry-forward (1)); recorded here as done, not re-planned.

## Known Requirements

Grading note: items forced by how the *real* generated package and TEAx validator actually
behave (named by Item 0) are `[HARD]`; design intents carried from the owner-ratified concept
and epic are `[INHERITED]` with their source cited. See `capture-fidelity.md`.

### Typed entry source (`MappingEntrySource`)

- **[HARD]** Typed entry is **two-level, not a flat parameter-ID→scalar map.** The real
  EntryPoint emits one structured channel (`toy_plant_params: ToyPlantParams`) whose *fields*
  are the contract parameter IDs; downstream modules field-extract
  (`toy_plant_params.toy_plant__Toy_Plant__plant_budget`). The entry source must express the
  contract at both levels — channel → model, and model field → parameter ID — not as a single
  flat map keyed by parameter ID. (Item 0 mismatch 1; `real_evaluator.py:evaluate`.)
- **[INHERITED]** **No silent coercion under any shape.** A value must never be accepted under
  a mismatched contract parameter ID. (concept "Contracts and the Evaluator"; S5 findings
  Open Questions.)
- **[INHERITED]** **An invalid typed input is rejected before any module executes, with a
  diagnostic naming expected and got types.** "Invalid" means missing, extra, or wrong-type.
  The rejection happens before the first module runs and names both the expected type and the
  type actually supplied. **Which layer performs the rejection is exactly the reserved choice**
  (see Open Questions): under a validate-raw source it is the entry source at field-value
  granularity; under an instantiated-models source the source rejects a wrong *channel-model*
  and the field-value check lives at the Item 11 bridge. The requirement — rejected
  pre-execution, expected-and-got named — holds identically under both shapes; it is the study
  layer's first line of defense, required behavior, not spike detail. (concept Appendix B, S5
  carry-forward (3).)
- **[HARD]** **Non-finite floats are well-formed input, not invalid input.** Entry validation
  rejects missing, extra, and wrong-*type* inputs before execution (at whichever layer the
  reserved choice places it), but must let a non-finite float (`NaN`, `inf`) through — it is a
  well-formed candidate that the generated Kleene predicate evaluates to `indeterminate`. Conflating non-finite with invalid would make the
  entire indeterminate verdict class unreachable through typed entry. (Item 0 mismatches 1–2;
  the real `ToyPlantParams` is a non-strict float model that accepts non-finite values.)

### Prepared-pipeline backend and the file-backed path

- **[INHERITED]** **Prepare once, fresh context per case.** Validate and build the pipeline
  topology a single time; each case evaluates in its own fresh execution context. (concept;
  S5.) Prepare-once measured ~64× faster than rebuild-per-case on the real package (Item 0
  benchmark; ~4× on S5's toy graph — the speedup scales with model-validation cost).
- **[INHERITED]** **The file-backed path is retained for auditable runs**, producing the same
  evidence plus persisted artifacts. (concept "How It Works — Evaluate One Design Point".)
- **[INHERITED]** **Case-level parity between the two backends is a kept test**, over an
  explicit equivalence class; a faster backend is admitted only on that parity. (concept;
  Required Invariant "auditable and fast evaluators return equivalent … results".) The
  equivalence class:
  - **Compared:** selected outputs, matched by stable ID, with **NaN-aware numeric equality** —
    two values are equal if they are numerically equal *or* both non-finite of the same kind
    (both NaN counts equal; `+inf`≡`+inf`, `-inf`≡`-inf`). Constraint verdict statuses are
    compared **exactly** (string equality on the canonical vocabulary).
  - **Excluded (enumerated):** provenance, timestamps, input digests, artifact paths, and the
    opaque report's on-disk encoding — the file-backed path serializes and the in-memory path
    does not, so byte-level report form is not a parity field.
  - **The NaN / indeterminate case MUST be in the parity fixture set.** It is the case the whole
    architecture exists to preserve, and it is exactly where a naive field compare fails: the
    file-backed path round-trips a NaN through JSON while the in-memory path holds a real
    `float('nan')`, and `NaN != NaN`. The NaN-aware rule above is what makes the two agree.
- **[INHERITED]** **No-persist mode writes nothing** — no output directory is created when
  persistence is off. (S5 findings; concept.)
- **[HARD]** **The validator requires ExitPoint write handlers even in no-persist mode.** A
  pure in-memory evaluator that never writes still must build an output router with JSON write
  handlers for the generated custom types, because `PipelineValidator` demands a write handler
  per ExitPoint output type unconditionally (validity coupled to writability). The in-memory
  backend must construct that router (or the design must decouple validity from writability).
  (Item 0 mismatch 7; `real_evaluator.py:_build_prepared`.)
- **[HARD]** **Evaluator protocol is `evaluate(typed_inputs) -> Evidence`** — it carries no
  `attempt_number`. The prepared pipeline is deterministic and stateless per case; the spike's
  `attempt_number` argument was unused. Retry/attempt bookkeeping belongs to the runner
  (Item 11), not the evaluator protocol. (Item 0 mismatch 4; `real_evaluator.py:evaluate`.)

### `ModelEvidence`

- **[INHERITED]** **Immutable, runtime-owned generic envelope.** `ModelEvidence` carries:
  response entries keyed by stable IDs (constraint verdicts project onto generic response
  keys), selected outputs, provenance, and the full generated report attached as an opaque
  model artifact. (concept "Contracts and the Evaluator".)
- **[INHERITED]** **Runtime types never import generated classes.** The evidence envelope and
  every other runtime type depend only on generic/runtime types; the generated
  `ConstraintReport` is held opaquely, never imported. Item 0 confirmed the generic projection
  is clean. (concept; Item 0 mismatch 6.)
- **[INFERRED]** **The no-generated-import rule is a kept isolation test**, not a property left
  to design. The test scans the runtime evidence and entry-source modules for any reference to a
  generated symbol and asserts none, and imports/constructs evidence with the generated package
  absent from the path. It is the only guard that keeps the concept's central
  runtime-independent-of-generated-classes bet from silently rotting. *(Orchestrator decision,
  agent-grade, 2026-07-12.)*
- **[INFERRED]** **Headline value is projected by a read-only normalization; the report artifact
  stays opaque and unmodified.** The projection layer *reads* the generated report's headline and
  normalizes only the value it writes onto the generic response key — it never mutates or rewrites
  the attached report, which stays opaque and byte-unchanged in evidence. The generated report
  uses underscore headlines (`all_satisfied`, `not_assessed`); `violation` and `indeterminate`
  already match. (Item 0 mismatch 5; `real_evaluator.py:189` `HEADLINE_TO_POLICY`, adapted from
  the spike's dict-rewrite to a read-only projection because production evidence holds the report
  opaque.) *(Orchestrator decision, agent-grade, 2026-07-12.)*
- **[INFERRED]** **The canonical evidence vocabulary is pinned in this item, runtime-owned:**
  `satisfied | violated | indeterminate | not_assessed` (underscore forms). The runtime owns its
  evidence surface; packages conform. **Ownership direction:** Item 9's contract conforms the
  *generated* side to the runtime's vocabulary, not the reverse — so the projection normalizes to
  a target fixed *here*, and SC2 is closable in Item 10 without waiting for Item 9. Item 9 must
  align the generated `ConstraintReport` headline vocabulary to this set. *(Orchestrator decision,
  agent-grade, 2026-07-12; resolves review L1-1/L1-2.)*

### Normalized failure outcome

- **[INHERITED]** **One normalized outcome for every evaluation failure**, carrying: phase,
  module or channel when known, cause, retryability, and partial-artifact status. (concept
  "Contracts and the Evaluator".)
- **[HARD]** **The `phase` field ranges over teax's real per-run phases**, in order:
  1. **`entry_validation`** — the typed entry input is rejected before any module runs
     (missing/extra/wrong-type). A genuinely distinct pre-execution phase.
  2. **`preparation`** — topology and write-handler validation. Runs **once at prepare**
     (`PipelineExecutor.build_graph` → `PipelineValidator.validate`,
     `pipeline_executor.py:104`), not per case; the write-handler-per-ExitPoint-type demand
     (`pipeline_validator.py:326`) and producer/declaration type-mismatch check
     (`pipeline_validator.py:~352`) live here. A whole study hits these once, not per candidate.
  3. **`module_execution`** — everything raised inside `module.run()` during the per-case run
     loop (`pipeline_executor.py:126–140`): an arbitrary module exception, a Pydantic
     `ValidationError` (generated modules validate inside `run()`), the aggregator's exact-schema
     rejecting a missing result, a `MultiOutput` missing field (`:205`), a field-extraction
     failure (`:397`). These are **one phase**, distinguished by `cause`, not by phase.
  4. **`output_write`** — writing artifacts on the file-backed path (never reached in no-persist
     mode).
- **[HARD]** **SC3's three distinguishable places, bound to the taxonomy:** a **module
  exception** is a `module_execution` failure; the **"schema failure"** SC3 means is the
  **pre-execution `entry_validation` rejection** — a real, separate phase from module execution;
  an **infeasible (`indeterminate`) verdict** is ordinary evidence, never a failure. An *in-run*
  schema failure (aggregator missing-field, Pydantic error inside `run()`) is **not** a separate
  phase — it is a `module_execution` failure carrying cause detail, matching the concept, which
  buckets "missing inputs, schema failures, thrown predicate code, or a missing aggregator field"
  together as execution failures (Required Invariants "Graph and Evaluation"). SC3's kept test
  exercises the `entry_validation` schema rejection, not the in-`run()` one.
- **[INHERITED]** **Violation stays evidence; breakage stays failure.** An assertion whose
  actual value differs from expected returns `violated` as evidence with ordinary outputs
  intact; a non-finite operand yields `indeterminate` as evidence. Only the `entry_validation`,
  `preparation`, `module_execution`, and `output_write` failures above are failures. (concept
  Required Invariants "Graph and Evaluation"; epic Item 10 success criterion.)

### Package load

- **[HARD]** **The sealed package loads under its declared package name.** The package's
  internal imports are absolute to its declared name (`from wi014_s4. …`), so the evaluator's
  package-load step must place/load it under that declared name, not its on-disk directory
  name. The canonical package-load protocol is **Item 9's** to own; Item 10 consumes it and
  must not hard-code a directory-name assumption. (Item 0 mismatch 8; `real_evaluator.py:load_package`.)
- **[INFERRED]** **Item 10 uses a provisional loader pending Item 9.** Item 9 has not landed, but
  Item 10 must load Item 0's package now to run any test — via the symlink-under-declared-name
  approach the spike uses (`real_evaluator.py:73`). "Item 9 owns the protocol" does **not** mean
  "Item 10 can't load anything yet"; the provisional loader is replaced when Item 9's protocol
  lands. *(Resolves review L3-3.)*

## Implementation Prerequisites (not API requirements)

These are sequencing/ops prerequisites for building the item, not contract obligations of the
evaluator API. Nothing about `MappingEntrySource`, `ModelEvidence`, or the failure outcome
depends on them — they belong to the plan, not the API surface.

- **Provision teax's own venv as the first implementation step.** teax's own `.venv`/`uv run`
  is broken for real-simkit runs; the spikes borrowed the fusion-tea (a.k.a. agentic-mbse) venv
  with a `PYTHONPATH`/`sys.path` insert. Items 10–12 must stand up teax's own working environment
  before building on it. (epic Risks: "teax environment provisioning"; Item 0 / S5 Reproduction.)

## Non-Goals

- **Study semantics** — `StudyDefinition`, strategies, the runner, the SQLite store, atomic
  case commit, proposal records, and resume are Item 11. This item builds only the evaluator,
  entry source, evidence types, and failure outcome the runner calls into.
- **Optimizers and adaptive strategies** — deferred with S7.
- **Contract *authoring/sealing*** — `ModelContract`/`PackageContract` derivation and the seal
  are Item 9. Item 10 *consumes* the sealed package; it does not produce contracts.
- **Proposal validation** — deciding malformed/missing/wrong-type vs non-finite for *proposals*
  is Item 11's runner concern (Item 0 mismatches 2–3). Item 10 only guarantees its entry source
  does not itself misclassify non-finite input.
- **Canonical non-finite operand *encoding* in serialized evidence** — Item 0 flagged the
  observed-operand NaN JSON-encoding as a schema decision tagged to Item 11. Item 10 holds the
  report opaquely and does not freeze that on-disk encoding (see Open Questions).

## Open Questions / Deferred to design

### RESERVED — owner decision at design: `MappingEntrySource` API shape

`[RESERVED: owner decision at design]` — Reid has reserved this choice. Both candidate shapes,
with consequences, captured here so design can execute the decision without re-deriving it. The
choice does **not** relax any requirement above: no silent coercion, and the wrong-type
diagnostic naming expected/got types, hold under either shape.

- **Shape A — instantiated-models-only.** The source accepts already-constructed Pydantic
  entry models (e.g. a `ToyPlantParams` instance), as the S5 strict probe did.
  - *Consequence:* type correctness is guaranteed by construction; the caller (Item 11's
    strategy→candidate bridge) owns building the channel model from parameter-ID values, and
    that bridge is where the two-level mapping (channel → model; field → parameter ID) is
    resolved. Non-finite floats pass through automatically (non-strict float model).
  - *Consequence:* the wrong-type diagnostic fires at *bridge construction*, not inside the
    entry source; the source must still refuse an instance of the wrong channel model and name
    expected vs got.
- **Shape B — validate-raw-mappings.** The source accepts raw mappings and validates them into
  the declared entry channel model itself.
  - *Consequence:* the source owns the two-level resolution and the type validation, so the
    wrong-type diagnostic lives here; it must permit non-finite floats through validation (a
    strict model would reject `NaN`/`inf` and silently kill the indeterminate class).
  - *Consequence:* raw-mapping validation is closer to the file-backed loader's behavior, which
    may simplify backend parity — but requires an explicit "no coercion across parameter IDs"
    rule that Shape A gets for free.
  - *Consequence (weighs against the no-generated-import rule):* the declared entry channel model
    is a *generated* class (e.g. `ToyPlantParams`), obtained dynamically from the loaded package.
    To validate raw mappings *into* it, the Shape B source must reference that generated model
    shape at runtime. It is a dynamic dependency, not a static import, so the letter of
    "runtime types never import generated classes" is met — but the spirit is strained, and the
    isolation test above must be written to allow the dynamic lookup while still forbidding a
    static generated import. Under Shape A the caller builds the model and the source never
    touches a generated class. *(Resolves review L3-2.)*
- **Cross-cutting for either shape:** Item 0 mismatch 1 means the contract the source validates
  against is channel→model→field, so whichever shape is chosen, the design must define how a
  study variable ("vary `plant_budget`") selects a *field* of the entry channel model.

### Deferred to design

- **Provenance contents of `ModelEvidence`** — which fields (executable fingerprint, input
  digest, generator/runtime versions, timestamp) the provenance record carries. The concept
  says "provenance"; the exact set is a design decision, constrained by what Item 11's resume
  join needs (lineage + executable/study fingerprints + candidate identity).
- **Opaque-report storage form** — whether the "full report as opaque artifact" is held as the
  in-memory generated object, a serialized blob, or a content-addressed reference. Interacts
  with Item 11's store and with the deferred non-finite encoding decision; keep it opaque to
  runtime types either way.
- **Retryability classification** — which failure phases/causes are marked retryable vs
  terminal in the normalized outcome. The evaluator is deterministic per case, so most failures
  are not transiently retryable; design should state the rule rather than leave the field free.
- **Whether the ExitPoint-write-handler coupling is worked around or accepted** — the in-memory
  backend can either build the JSON router unconditionally (Item 0's approach) or the design can
  decouple validator-validity from ExitPoint-writability. A local fix here vs a validator change
  is a design call; note if it grows beyond Item 10.

---

## Related Artifacts

- **Epic:** `.project/reference/epic_constraint_execution.md` — Item 10 (canonical:
  sysml-codegen `.project/backlog/epic_constraint_execution.md`).
- **Required Reading (from the epic):**
  - `.project/reference/constraint-execution-concept.md` — "Contracts and the Evaluator",
    Required Invariants (Graph and Evaluation; Study Execution), Appendix B S5 result +
    carry-forwards.
  - `.project/active/spike-teax-typed-entry-scalar-continuity/findings.md` — S5 result and
    carry-forwards.
  - `.project/active/constraint-study-integration-spike/findings.md` — Item 0 findings; the
    eight named evaluator-interface mismatches.
- **Dependencies:** Item 0 (seam findings — landed); Item 9 (contract consumption + package-load
  protocol, and conforming the generated report's headline vocabulary to *this item's*
  runtime-owned canonical set — hardens this item when it lands; the vocabulary itself is pinned
  here, not by Item 9).
- **Design:** `.project/active/model-evaluator/design.md` (to be created).

---

**Next Steps:** After approval, proceed to `/_my_spec_review` (fresh session), then
`/_my_design`. Design must resolve the reserved `MappingEntrySource` shape with the owner.
