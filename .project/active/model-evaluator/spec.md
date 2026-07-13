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

- [ ] **S5 invariants are kept teax tests:** mapping-vs-file case-level parity; pre-execution
  rejection of missing, extra, and wrong-type entry inputs; execution-context isolation across
  cases; and no output directory created when persistence is off.
- [ ] **S4-lineage packages evaluate to evidence:** evaluating a sealed generated package
  (Item 0's setup now; Item 9's sealed output when it lands) returns `ModelEvidence` whose
  constraint verdicts are projected onto generic response keys, with the full generated report
  attached as an opaque artifact and no generated class imported by any runtime type.
- [ ] **Three phases are distinguishable:** a module exception, a schema/validation failure,
  and an infeasible (`indeterminate`) verdict land in three distinguishable places — the first
  two as the normalized failure outcome with different phase/cause, the third as ordinary
  evidence, never a failure.
- [ ] **Non-finite input reaches the verdict, not the guard:** a well-formed candidate with a
  non-finite value (e.g. a NaN budget) passes entry validation and evaluates to
  `indeterminate` — it is never rejected as invalid input.
- [ ] **Both backends agree:** the prepared in-memory backend and the file-backed backend
  return equivalent selected outputs and constraint results for the same canonical inputs
  (kept parity test).
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
- **[INHERITED]** **Wrong-type diagnostic names expected and got types.** When an entry value
  has the wrong type, the rejection message names both the expected type and the type actually
  supplied. This holds regardless of which `MappingEntrySource` shape is chosen and is the
  study layer's first line of defense — required behavior, not spike detail.
  (concept Appendix B, S5 carry-forward (3).)
- **[HARD]** **Non-finite floats are well-formed input, not invalid input.** The entry source
  rejects missing, extra, and wrong-*type* inputs before execution, but must let a non-finite
  float (`NaN`, `inf`) through — it is a well-formed candidate that the generated Kleene
  predicate evaluates to `indeterminate`. Conflating non-finite with invalid would make the
  entire indeterminate verdict class unreachable through typed entry. (Item 0 mismatches 1–2;
  the real `ToyPlantParams` is a non-strict float model that accepts non-finite values.)

### Prepared-pipeline backend and the file-backed path

- **[INHERITED]** **Prepare once, fresh context per case.** Validate and build the pipeline
  topology a single time; each case evaluates in its own fresh execution context. (concept;
  S5.) Prepare-once measured ~64× faster than rebuild-per-case on the real package (Item 0
  benchmark; ~4× on S5's toy graph — the speedup scales with model-validation cost).
- **[INHERITED]** **The file-backed path is retained for auditable runs**, producing the same
  evidence plus persisted artifacts. (concept "How It Works — Evaluate One Design Point".)
- **[INHERITED]** **Case-level parity between the two backends is a kept test** — equivalent
  selected outputs and constraint results for the same canonical inputs; a faster backend is
  admitted only on that parity. (concept; Required Invariant "auditable and fast evaluators
  return equivalent … results".)
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
- **[HARD]** **Headline vocabulary is normalized in the projection layer.** The generated
  report uses underscore headlines (`all_satisfied`, `not_assessed`); the study policy uses
  hyphenated ones (`all-satisfied`, `not-assessed`); `violation` and `indeterminate` already
  match. The projection must map to one canonical vocabulary so a naive projection does not
  `KeyError`. **The single canonical headline vocabulary is pinned jointly with Item 9** (the
  generated `ConstraintReport`); note the dependency where the canonical set is fixed.
  (Item 0 mismatch 5; `real_evaluator.py:HEADLINE_TO_POLICY`.)

### Normalized failure outcome

- **[INHERITED]** **One normalized outcome for every evaluation failure**, carrying: phase,
  module or channel when known, cause, retryability, and partial-artifact status. (concept
  "Contracts and the Evaluator".)
- **[INHERITED]** **Violation stays evidence; breakage stays failure.** An assertion whose
  actual value differs from expected returns `violated` as evidence with ordinary outputs
  intact; a non-finite operand yields `indeterminate` as evidence; only missing inputs, schema
  failures, thrown predicate code, or a missing aggregator field are failures. A module
  exception and a schema/validation failure are both failures but distinguishable by
  phase/cause. (concept Required Invariants "Graph and Evaluation"; epic Item 10 success
  criterion.)

### Package load and environment

- **[HARD]** **The sealed package loads under its declared package name.** The package's
  internal imports are absolute to its declared name (`from wi014_s4. …`), so the evaluator's
  package-load step must place/load it under that declared name, not its on-disk directory
  name. The canonical package-load protocol is **Item 9's** to own; Item 10 consumes it and
  must not hard-code a directory-name assumption. (Item 0 mismatch 8; `real_evaluator.py:load_package`.)
- **[INHERITED]** **Provision teax's own venv as the first implementation step.** teax's own
  `.venv`/`uv run` is broken for real-simkit runs; the spikes borrowed the fusion-tea (a.k.a.
  agentic-mbse) venv with a `PYTHONPATH`/`sys.path` insert. Items 10–12 must stand up teax's
  own working environment before building on it. (epic Risks: "teax environment provisioning";
  Item 0 / S5 Reproduction.)

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
- **Dependencies:** Item 0 (seam findings — landed); Item 9 (contract consumption + canonical
  headline vocabulary + package-load protocol — hardens this item when it lands).
- **Design:** `.project/active/model-evaluator/design.md` (to be created).

---

**Next Steps:** After approval, proceed to `/_my_spec_review` (fresh session), then
`/_my_design`. Design must resolve the reserved `MappingEntrySource` shape with the owner.
