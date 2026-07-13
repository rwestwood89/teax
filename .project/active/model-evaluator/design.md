# Design: Model Evaluator and Typed Entry — Production API (Item 10)

**Status:** Draft
**Owner:** Reid W
**Created:** 2026-07-12
**Branch:** constraint-exec-epic
**Base commit:** 8a6bcdf

---

## Overview

Productionize the constraint-execution runtime seam that three spikes proved: a typed
in-memory entry source, a prepare-once pipeline backend (file-backed path kept for audit),
an immutable evidence envelope that never imports generated classes, and one normalized
failure outcome that keeps "the design is infeasible" (evidence) apart from "the run broke"
(failure). This is the teax half of "Contracts and the Evaluator"; the study store, runner,
and strategies are Item 11.

## Related Artifacts

- **Spec:** `.project/active/model-evaluator/spec.md` (review-revised, committed)
- **Spec review:** `.project/active/model-evaluator/spec-review.md`
- **Probe (shape to productionize):** `.project/active/constraint-study-integration-spike/real_evaluator.py`
- **Item 0 findings (eight mismatches):** `.project/active/constraint-study-integration-spike/findings.md`
- **S5 findings (four invariants):** `.project/active/spike-teax-typed-entry-scalar-continuity/findings.md`
- **Concept:** `.project/reference/constraint-execution-concept.md` — "Contracts and the Evaluator"
- **Epic:** `.project/reference/epic_constraint_execution.md` — Item 10

## Research Findings

The runtime already gives us every mechanism this design composes with. We add a thin
evaluation layer on top; we do not fork the executor.

- **Executor is already prepare/run split.** `PipelineExecutor.build_graph` validates once
  (`pipeline_executor.py:104` → `PipelineValidator.validate`); `run` executes modules per
  case with no re-validation (`pipeline_executor.py:126–140`). Prepare-once is a first-class
  runtime property, not a spike trick — Item 0 measured ~64× over rebuild on the real package.
- **Entry loading is a single overridable method.** `_execute_entry` (`pipeline_executor.py:171`)
  loads each EntryPoint channel from a file. The probe subclasses the serial executor and
  overrides only this method to pull already-typed values from the context
  (`real_evaluator.py:_build_prepared`, `MappingExecutor`). Everything else runs unchanged.
- **The write-handler demand is unconditional and confirmed.** `PipelineValidator` requires a
  write handler per ExitPoint output type with no persist guard (`pipeline_validator.py:326`).
  `create_output_router_with_json_schemas(..., in_memory=True)` (`output_router.py:288`) builds
  exactly the router the in-memory backend needs — validates, writes nothing.
- **`RootModel[float]` scalar outputs unwrap via `.root`** (`real_evaluator.py:_project`), the
  regression already committed this run (SC7).
- **S6's `Evidence`/`ExecutionFailed`** (`study_lifecycle.py:89,102`) are the throwaway targets
  the probe projected onto; production replaces them with runtime-owned `ModelEvidence` and the
  normalized `EvaluationFailure`. S6's `Compatibility` row (`study_lifecycle.py:56`) names what
  Item 11's resume join binds — it constrains our provenance fields.

## Core Concept

The evaluator is a **pure function from a typed candidate to immutable evidence**, wrapped
around the unchanged teax executor. It has two lifecycle steps that already exist in the
runtime: **prepare once** (validate topology, build the graph, register write handlers) and
**evaluate per case** (set typed entry channels into a fresh context, run, project the result).

The one hard rule that shapes everything: **runtime evidence and entry types never depend on
generated classes.** The generated `ConstraintReport` is held opaque — read by duck-typed
attribute access at projection time, never imported, never mutated. This is what lets Item 11
freeze a store schema against `ModelEvidence` without ever seeing a generated symbol, and it is
enforced by a kept isolation test, not left to discipline.

Three outcomes must stay distinguishable, and the runtime already separates them: an infeasible
design is **evidence** (`indeterminate` verdict, ordinary outputs intact); a broken run is a
**failure** (normalized outcome carrying phase + cause); and a malformed candidate is rejected
**before any module runs** (`entry_validation` phase). The evaluator's whole job is to preserve
that separation across the seam from the generated package into runtime-owned types.

We build from the Item 0 probe's proven shape and change exactly what the spec requires:
drop `attempt_number` from the protocol, hold the report opaque instead of projecting it to a
dict, normalize the headline read-only to a runtime-owned vocabulary, and split the probe's
single stringly-typed `ExecutionFailed` into a normalized outcome over teax's real phases.

## Key Bets

- **B1. The generated report is fully readable by duck-typed attribute access
  (`report.headline`, `report.results`, `r.status`, `r.margin`, `r.observed`).** Projection
  never needs the generated *type*, only its attributes. *If false → the runtime must import a
  generated class to read evidence, and the central no-generated-dependency bet collapses.*
  (Item 0 confirmed the projection is clean; `real_evaluator.py:_project`.)
- **B2. The evaluator is a deterministic, stateless function of (typed inputs, sealed
  executable).** Same inputs + same fingerprint → byte-identical evidence. *If false → resume
  can't reproduce a run, and Item 11's crash-safe join is unsound.* (Item 0: byte-identical
  ordered cases across crash+resume.)
- **B3. `ToyPlantParams` and every generated entry model is a non-strict float model, so a
  non-finite field passes construction and flows to the Kleene predicate.** *If false → the
  `indeterminate` verdict class is unreachable through typed entry, and the architecture's
  reason to exist is gone.* (Item 0 mismatch 1–2; the real model accepts `NaN`/`inf`.)
- **B4. No failure the evaluator raises is transiently retryable.** A deterministic function
  fails the same way every time. *If false → we'd drop real transient signal on the floor —
  but transient/infra retry is the runner's layer (S6's `RetryableError`), not the evaluator's,
  so the evaluator never raises it.* (Constrains D4.)

## Key Decisions

- **D1. `MappingEntrySource` = Shape A (instantiated-models-only).** `[OWNER]` (Reid,
  2026-07-12, orchestrated-run gate). The source accepts already-constructed Pydantic entry
  models keyed by EntryPoint channel ID and refuses a wrong *channel-model instance*, naming
  expected vs got. The caller (Item 11's strategy→candidate bridge) owns building the channel
  model from parameter-ID values and resolving the two-level mapping (channel → model; field →
  parameter ID); field-value type correctness is guaranteed by construction. Non-finite floats
  pass by construction. *Rejected: Shape B (validate-raw-mappings) — it must reference the
  generated channel-model shape at runtime to validate into it, straining the no-generated-import
  rule, and needs an explicit "no coercion across parameter IDs" rule that Shape A gets for
  free (spec RESERVED section, review L3-2).*
- **D2. New `simkit/evaluation/` subpackage; the isolation-clean core is physically separate
  from the package-touching backend.** `evidence.py`, `entry_source.py`, `failure.py`,
  `projection.py` are generated-import-clean and construct with the generated package absent;
  `evaluator.py` and `package_load.py` legitimately touch the package and are excluded from the
  isolation scan by design. *Rejected: putting these in `core/` — `core/` is pipeline
  orchestration, evaluation is a distinct layer on top, and a dedicated package makes the
  isolation-scan target crisp.*
- **D3. Evaluator protocol is `evaluate(typed_inputs: Mapping[str, BaseModel]) -> ModelEvidence`;
  no `attempt_number`.** *Rejected: carrying `attempt_number` (the probe did, unused) — retry
  bookkeeping is the runner's, and the prepared pipeline is stateless per case (Item 0 mismatch 4).*
- **D4. Failure surfaces as a raised `EvaluationFailed` carrying an immutable `EvaluationFailure`;
  `retryable` is always `False` for evaluator failures.** The evaluator raises, the runner
  catches and commits the case; a raise (not a return-union) matches S6's runner control flow.
  *Rejected: a `Result[ModelEvidence, EvaluationFailure]` return union — it would force every
  caller to branch and diverges from the S6 runner the seam is validated against; and a
  free-form `retryable` field — the rule is fixed (deterministic → terminal), so we state it,
  not leave it open (spec deferred item 3).*
- **D5. In-memory backend builds the JSON router unconditionally (local workaround), not a
  validator change.** `create_output_router_with_json_schemas(generated_type_names,
  in_memory=True)`. *Rejected: decoupling validator-validity from ExitPoint-writability — that
  touches shared validation semantics other pipelines rely on, is out of Item 10 scope, and the
  workaround is a three-line construction. **Flag:** if a later item needs a genuinely
  handler-free in-memory validation path, revisit the `pipeline_validator.py:326` coupling then
  (spec deferred item 4; Item 0 mismatch 7).*
- **D6. Headline normalization is a read-only projection onto the runtime-owned canonical
  vocabulary `satisfied | violated | indeterminate | not_assessed` (underscore).** The
  projection reads the generated report's headline and writes a normalized value onto the
  generic response key; the attached report stays opaque and byte-unchanged. *Rejected:
  normalizing to S6's hyphen policy vocabulary (`all-satisfied`, the probe's `HEADLINE_TO_POLICY`)
  — Item 10 owns the evidence surface and pins the underscore set here; packages conform (Item 9
  aligns the generated side later). Also rejected: the probe's dict-rewrite of the report —
  production holds it opaque (spec `ModelEvidence` section, review L1-1/L1-2).*
- **D7. Package loading is a `PackageLoader` seam; Item 10 ships a provisional
  symlink-under-declared-name loader that verifies the seal.** *Rejected: hard-coding the
  on-disk directory name — the package's internal imports are absolute to its declared name
  (`from wi014_s4. …`), Item 9 owns the canonical protocol, and the seam lets Item 9 swap in
  without touching the evaluator (Item 0 mismatch 8; spec package-load section).*

## Architecture

Three layers, generated-package dependency increasing outward:

```
  candidate values ──(Item 11 bridge, out of scope)──▶ typed entry models
        │
        ▼
  MappingEntrySource.validate(values)                 [entry_source.py — isolation-clean]
        │  refuses wrong channel-model instance (expected vs got); non-finite passes
        ▼
  PreparedEvaluator.evaluate(typed_inputs)            [evaluator.py — touches package]
        │  fresh context → override _execute_entry → executor.run(persist=False)
        ▼
  project(run_result, opaque_report)                  [projection.py — duck-typed, isolation-clean]
        │  read-only headline normalize; report held opaque
        ▼
  ModelEvidence(responses, outputs, provenance, report)   [evidence.py — isolation-clean]
```

**Prepare once (study startup):** `PreparedEvaluator(loader, spec_path)` calls the loader
(verify seal → load package under declared name → executable fingerprint), builds the schema
registry / entry loaders / in-memory JSON router from the package's `CUSTOM_SCHEMA_TYPES`,
`build_graph(spec)` (validates topology — the `preparation` phase runs here, once), and derives
the `MappingEntrySource` from the EntryPoint's declared channel→type bindings.

**Evaluate per case:** validate typed inputs against the source → build a fresh
`PipelineExecutionContext` seeded with those channel values → `run(graph, context,
persist_outputs=False)` → project. The executor subclass overrides only `_execute_entry` to read
from the seeded context instead of loading files (`real_evaluator.py` `MappingExecutor`).

**File-backed backend (audit):** the standard `execute_pipeline` path — file entry, real router,
`persist_outputs=True` — then the *same* `project(...)`. It produces the same evidence plus
persisted artifacts. Both backends share projection and vocabulary; the parity test is what
admits the fast in-memory path.

**Data flow into evidence.** `ModelEvidence` carries: `responses` (stable-ID-keyed entries —
per-constraint verdict statuses, already canonical, plus the normalized headline), `outputs`
(selected numeric outputs, unwrapped from `RootModel[float]`), `provenance` (see D-below), and
`report` (the opaque generated object, held as `Any`, never introspected by runtime types).

## Required Invariants

- **INV1. No runtime evidence/entry/failure/projection module references any generated symbol,
  statically or dynamically, and each imports and constructs with the generated package absent
  from the path.** (Kept isolation test.)
- **INV2. Entry validation rejects missing / extra / wrong channel-model instances before the
  first module runs, naming expected and got; a non-finite float is never rejected.**
- **INV3. `prepare` runs topology + write-handler validation exactly once; `evaluate` never
  re-validates topology.**
- **INV4. Same (typed inputs, executable fingerprint) → equal evidence under the parity
  equivalence class** (selected outputs NaN-aware-equal; verdict statuses string-exact;
  provenance/timestamps/digests/artifact-paths/report-encoding excluded).
- **INV5. An `indeterminate` verdict is always evidence, never a failure; the four failure
  phases (`entry_validation`, `preparation`, `module_execution`, `output_write`) are the only
  failures.**
- **INV6. No output directory is created when `persist_outputs=False`.**

## Component Overview

`simkit/evaluation/` (new subpackage):

- **`evidence.py`** *(isolation-clean).* `ModelEvidence` (frozen), `ResponseEntry`,
  `EvidenceProvenance`, and `CANONICAL_HEADLINE` vocabulary constant. Runtime-owned, depends only
  on generic types. Public.
- **`entry_source.py`** *(isolation-clean).* `MappingEntrySource` (Shape A) — `from_spec`
  derives expected channel→type map from the EntryPoint bindings; `validate` refuses wrong
  channel-model instance / missing / extra, naming expected vs got. Ported from
  `real_evaluator.py` `MappingEntrySource`, unchanged in shape. Public.
- **`failure.py`** *(isolation-clean).* `EvaluationPhase` enum (`entry_validation | preparation |
  module_execution | output_write`), `EvaluationFailure` (frozen: phase, cause, module_or_channel,
  retryable, partial_artifacts), `EvaluationFailed` exception carrying it. Public.
- **`projection.py`** *(isolation-clean, duck-typed).* `project(run_result, report) ->
  ModelEvidence` — read-only headline normalization, per-constraint status pass-through, output
  unwrap, opaque report attach. Reads the report by attribute; never imports it.
- **`evaluator.py`** *(touches package).* `Evaluator` protocol, `PreparedEvaluator` (in-memory,
  prepare-once), `FileBackedEvaluator` (audit). Ports `real_evaluator.py` `_build_prepared` /
  `RealPreparedEvaluator`, minus `attempt_number`, minus dict-rewrite. Public.
- **`package_load.py`** *(touches package).* `PackageLoader` protocol, `ProvisionalPackageLoader`
  (symlink-under-declared-name + inlined seal verification, from `real_evaluator.py:verify_seal`/
  `load_package`). Public, provisional pending Item 9.

**Public API** (`simkit/evaluation/__init__.py`): `MappingEntrySource`, `ModelEvidence`,
`ResponseEntry`, `EvidenceProvenance`, `CANONICAL_HEADLINE`, `EvaluationPhase`,
`EvaluationFailure`, `EvaluationFailed`, `Evaluator`, `PreparedEvaluator`, `FileBackedEvaluator`,
`PackageLoader`, `ProvisionalPackageLoader`.

### Deferred-item decisions (recorded)

- **Provenance fields** (`EvidenceProvenance`): `executable_fingerprint` (from the seal),
  `evidence_schema_version` (runtime-owned; Item 11 binds compatibility on it), `evaluator_version`,
  and `input_digest` (canonical-serialized content hash of the typed inputs — a cross-check anchor
  for the resume join). *Deliberately excluded:* `study_id`, `candidate_id`, `proposal_id`,
  `strategy_*`, wall-clock timestamp — those are runner-owned (S6 `Compatibility` / three-layer
  identity) and stamping them here would break B2's determinism. The evaluator is study-agnostic;
  Item 11 wraps evidence with its own identity. *(Resolves spec deferred item 1.)*
- **Opaque-report storage form:** held as the **in-memory generated object** (`Any`), never
  introspected. The file-backed path serializes it to JSON for its persisted artifact, but that
  encoding is excluded from parity and does not freeze Item 11's non-finite on-disk decision.
  *Rejected: serialize-at-evaluate (forces the deferred non-finite encoding now) or
  content-addressed reference (needs a store — that's Item 11).* *(Resolves spec deferred item 2.)*
- **Retryability rule:** every evaluator-raised `EvaluationFailure` is `retryable=False`. The
  evaluator is deterministic per case (B2/B4); transient/infra retry lives in the runner. State
  the rule; don't leave the field free. *(Resolves spec deferred item 3.)*
- **ExitPoint-write-handler coupling:** local workaround (D5). *(Resolves spec deferred item 4.)*

## Non-Goals

- **Study store, runner, strategies, policy, resume, atomic commit** — Item 11.
- **Contract authoring / sealing** (`ModelContract`/`PackageContract`) — Item 9. Item 10
  *consumes* the sealed package.
- **Proposal validation** (malformed vs non-finite for *proposals*) — Item 11's runner.
- **Canonical non-finite operand encoding in serialized evidence** — Item 11; the report stays
  opaque here.
- **Canonical package-load protocol** — Item 9; Item 10 uses the provisional loader.

## Implementation Notes

- **Phase → real failure map** (the taxonomy, bound to teax):
  - `entry_validation` — `MappingEntrySource.validate` raises (missing/extra/wrong channel-model).
    Pre-execution, a genuinely distinct phase. **This is the "schema failure" SC3 exercises.**
  - `preparation` — `build_graph`→`validate` at prepare (write-handler, producer/declaration
    mismatch, `pipeline_validator.py:326,~352`). Once per study, aborts before any case.
  - `module_execution` — anything raised inside `module.run()` (`pipeline_executor.py:126–140,205,
    397`): arbitrary exception, Pydantic `ValidationError`, aggregator missing-result, MultiOutput
    missing field, field-extraction failure. **One phase, distinguished by `cause`, not phase** —
    an in-`run()` schema failure is *not* a separate phase.
  - `output_write` — file-backed persistence only; never reached in no-persist mode.
- **The evaluator catches executor exceptions and normalizes them**, replacing the probe's
  `except Exception → ExecutionFailed(str)` (`real_evaluator.py:evaluate`) with a mapping to
  `EvaluationFailure(phase=module_execution, cause=type+message, module_or_channel=<key when
  known>, retryable=False, partial_artifacts=none)`.
- **`input_digest` uses a stable non-finite tag** (`{"__nonfinite__": "nan"}`, from
  `real_evaluator.py:_json_safe`) *inside the digest only* — this is not the on-disk evidence
  encoding (Item 11's to freeze), just a deterministic hash input.
- **Projection code snippet (shape, not implementation):**
  ```python
  def project(result, report) -> ModelEvidence:            # report: opaque, duck-typed
      headline = CANONICAL_HEADLINE[report.headline]        # read-only normalize
      responses = {r.constraint_id: r.status for r in report.results}  # already canonical
      outputs = {k: v.root for k, v in selected(result)}    # RootModel[float] unwrap
      return ModelEvidence(responses={**responses, "headline": headline},
                           outputs=outputs, provenance=..., report=report)
  ```
- **Non-finite must survive to the verdict.** Do not add strict-float validation anywhere on the
  entry path (INV2, B3). The isolation and NaN-parity tests guard this.

## Potential Risks

- **Isolation rot via a convenience import.** Someone adds `from wi014_s4 import ...` to
  `projection.py` for a type hint. *Mitigation:* INV1 kept test (import scan + package-absent
  construction) fails the build.
- **Provenance under-serves Item 11's resume join.** If Item 11 needs a field we omitted.
  *Mitigation:* fields chosen against S6's `Compatibility` row and the resume-join constraint
  (lineage + executable/study fingerprints + candidate identity); the evaluator-owned subset is
  small and additive-safe.
- **Parity test written naively fails on NaN.** *Mitigation:* the NaN-aware equality rule is
  specified in the spec's equivalence class and the NaN case is mandated in the fixture set.
- **Provisional loader diverges from Item 9's protocol.** *Mitigation:* the `PackageLoader`
  seam isolates the swap to one module; evidence/evaluator contracts don't change.

## Integration Strategy

The evaluation layer sits on top of the unchanged executor/validator/router. It **adds** a
subpackage and **changes no existing runtime file** (D5 keeps the write-handler workaround local).
Item 11 imports `PreparedEvaluator` + `ModelEvidence` + `EvaluationFailed` and drives them exactly
as S6's runner drove the probe — the seam is already validated end to end (Item 0, 40/40).
Item 9 later swaps `ProvisionalPackageLoader` for its canonical loader and aligns the generated
headline vocabulary to `CANONICAL_HEADLINE` (hardening, not blocking).

## Validation Approach

Kept test suite (all in `packages/teax-simkit/simkit/tests/`, mirroring existing layout):

1. **S5's four invariants** — mapping-vs-file case-level parity (INV4); pre-execution rejection
   of an invalid typed input before any module runs (INV2); execution-context isolation across
   cases (fresh context per `evaluate`, no channel bleed); no output directory in no-persist mode
   (INV6).
2. **Parity fixture set** — canonical inputs across the three verdict classes; **the
   NaN/indeterminate case is mandatory**; compares selected outputs (NaN-aware) + verdict statuses
   (exact), excludes provenance/timestamps/digests/paths/report-encoding.
3. **Isolation test** — import-scan `evidence.py`/`entry_source.py`/`failure.py`/`projection.py`
   for any generated symbol (assert none) **and** import + construct evidence with the generated
   package absent from `sys.path` (INV1).
4. **Three-distinguishable-outcomes test** — a module exception → `module_execution` failure; an
   `entry_validation` schema rejection → failure with a different phase; an `indeterminate`
   verdict → ordinary evidence, never a failure (SC3, INV5).
5. **Non-finite reaches the verdict** — a NaN budget passes entry validation and evaluates to
   `indeterminate` (B3).

Environment: teax's own working venv is stood up as the **first implementation step** (spec
Implementation Prerequisites; the spikes borrowed the fusion-tea venv). Until then, tests run
under the licensed host venv per the Item 0 reproduction recipe.

## Next-Stage Handoff

- **Fixed:** Shape A (D1, owner gate); the four deferred decisions above; the phase→failure map;
  the parity equivalence class (from spec); the subpackage layout and isolation-scan boundary (D2).
- **Open (plan's to sequence):** venv provisioning first; exact module-by-module port order from
  the probe; the fixture files (reuse Item 0's candidate set + the sealed package).
- **De-risk first:** the isolation boundary — write INV1's kept test before porting projection,
  so the no-generated-import rule is enforced from the first commit rather than retrofitted.

---
**Next Step:** After approval → `/_my_design_review` (fresh session), then `/_my_plan`.
