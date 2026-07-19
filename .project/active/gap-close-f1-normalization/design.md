# Design: GAP-CLOSE F1 TEAx Normalization

**Identifier:** GAP-CLOSE-F1-TEAX-NORMALIZATION
**Status:** Ready for Planning (Revision 3)
**Owner:** Reid W
**Created:** 2026-07-18
**Updated:** 2026-07-18
**Branch:** constraint-exec-epic
**Base commit:** 927a9e1

---

## Overview

Record the exact failed pipeline module key in the per-run execution context while re-raising the
original exception unchanged, then normalize both evaluator routes through one function. The
correction preserves the original arithmetic exception as `EvaluationFailed.__cause__` and leaves
arithmetic, verdicts, failure taxonomy, retry policy, persistence timing, and unrelated executor
behavior unchanged.

This stage needs technical design because the correction crosses executor ownership, two evaluator
backends, Python exception chaining, and sealed generated-package fixtures. Product design was
skipped because there is no consumer-facing interaction, API shape choice, or presentation surface;
the reviewed failure record is already the complete observable contract.

## Related Artifacts

- **Reviewed contract:** [spec.md](spec.md)
- **Spec review:** [spec-review.md](spec-review.md)
- **Current project context:** [../../CURRENT_WORK.md](../../CURRENT_WORK.md)
- **Completed evaluator spec:** [../../completed/20260713_model-evaluator/spec.md](../../completed/20260713_model-evaluator/spec.md)
- **Completed evaluator design:** [../../completed/20260713_model-evaluator/design.md](../../completed/20260713_model-evaluator/design.md)
- **Completed evaluator audit:** [../../completed/20260713_model-evaluator/audit.md](../../completed/20260713_model-evaluator/audit.md)
- **Runtime overview:** [../../../docs/evaluation-and-study.md](../../../docs/evaluation-and-study.md)
- **Project intent:** [../../../tea_simulation_design_doc.md](../../../tea_simulation_design_doc.md)
- **Upstream runtime contract:** `../../../../sysml-codegen/.project/active/gap-runtime-contract/spec.md`
- **Owner ruling and verification:**
  `../../../../sysml-codegen/.project/research/20260718_gap-review-verification.md`
- **Gap research:**
  `../../../../sysml-codegen/.project/research/20260718-123558_constraint-expression-final-gap-review.md`
- **Epic:** `../../../../sysml-codegen/.project/backlog/epic_gap_close.md`, Item 1

## Research Findings

- The serial run loop has the exact pipeline module key immediately before dispatching each normal
  module. It calls `_execute_module(module_key, ...)` and stops on the first exception
  (`packages/teax-simkit/simkit/core/pipeline_executor.py:125`).
- `_execute_module` covers input resolution, `module.run()`, output decomposition, channel writes,
  and module-version recording. A catch at this boundary correctly covers the existing
  `module_execution` phase, not only exceptions raised literally inside `run()`
  (`packages/teax-simkit/simkit/core/pipeline_executor.py:181`).
- Both evaluators duplicate the same run-level `except Exception` normalization and currently omit
  `module_or_channel` (`packages/teax-simkit/simkit/evaluation/evaluator.py:112` and
  `packages/teax-simkit/simkit/evaluation/evaluator.py:185`). This is the drift point to replace
  with one shared normalizer.
- The prepared backend already specializes only EntryPoint loading
  (`packages/teax-simkit/simkit/evaluation/evaluator.py:56`). Module-failure capture belongs in the
  shared run loop so the two backends cannot drift.
- The file-backed router creates its run directory only after module execution reaches output
  persistence (`packages/teax-simkit/simkit/core/pipeline_executor.py:147` and
  `packages/teax-simkit/simkit/io/output_router.py:78`). A constraint exception therefore prevents
  candidate output creation even if an earlier constraint already wrote an in-memory channel.
- `EvaluationFailure` already has the exact immutable fields required by the spec, with terminal
  retry and empty partial artifacts as defaults
  (`packages/teax-simkit/simkit/evaluation/failure.py:26`). No public failure type or schema change
  is needed.
- Existing generated-package parity tests already share session fixtures and compare successful
  evidence across both routes (`packages/teax-simkit/simkit/tests/evaluation/conftest.py:29` and
  `packages/teax-simkit/simkit/tests/evaluation/test_parity.py:40`). The current fixture has one
  constraint module, so it cannot prove causal module identity or later-module failure
  (`packages/teax-simkit/simkit/tests/evaluation/fixtures/sealed_package/package_live/pipelines/pipeline.yaml:36`).
- Sysml-codegen's kept cases pin the four native arithmetic raises and messages: division by zero,
  zero to a negative power, exponent overflow, and division beneath `and`
  (`../sysml-codegen/tests/unit/test_predicate_compiler.py:116`). Its generated wrapper regression
  proves the exception crosses `module.run()` unchanged
  (`../sysml-codegen/tests/execution/test_constraint_execution.py:444`).
- **Fixture premise conflict surfaced.** At sysml-codegen revision
  `512786c7dfab44fba7a0185d09e845b7494c702d`, no committed model, snapshot, or graph producer emits
  three independently controlled division/power/nested constraints. The committed live
  multi-constraint fixture emits three occurrences of one nonnegative predicate
  (`../sysml-codegen/tests/conformance/test_constraint_generation_live.py:76`), while the arithmetic
  execution helper is explicitly single-constraint
  (`../sysml-codegen/tests/execution/test_constraint_execution.py:326`). The CLI accepts only a
  model or extraction snapshot, not a prebuilt graph (`../sysml-codegen/src/sysml_codegen/cli/__init__.py:929`).
  Therefore this design does not call the TEAx fixture live-model-generated or snapshot-generated.
- The truthful fixture strategy is production-equivalent: a committed TEAx-owned graph producer
  supplies synthetic constraint facts to production `extend_graph_with_constraints` and
  `assemble_constraint_catalog`, then uses the production schemas/modules/pipeline/registry/entry/
  contract/seal functions. This follows the upstream production-equivalent precedent
  (`../sysml-codegen/tests/execution/test_constraint_execution.py:326`) and includes the sealing
  step that its older `_generate_full_package` helper omits
  (`../sysml-codegen/src/sysml_codegen/cli/__init__.py:1029`).

## Core Concept

The serial executor records one piece of failure context on the execution context: the exact key of
the normal module whose invocation raised. It resets that slot at the start of every run, sets it
only inside the `except Exception` immediately surrounding `_execute_module(module_key, ...)`, and
uses a bare `raise`. The original exception object and traceback therefore cross the executor
unchanged. Both evaluators then call one normalizer, which reads the slot, builds the fixed
`EvaluationFailure` record, and raises `EvaluationFailed` directly from the original exception.

This is the right boundary because module identity is captured where it is authoritative, while
evaluation policy remains where it already belongs. The core seam records context but performs no
normalization. Bare re-raise means direct users of `SerialPipelineExecutor` still catch the same
exception. Per-run reset plus failure-only assignment prevents a prior module or prior run from
leaking a stale label.

## Key Bets

- **B1.** Every target arithmetic failure crosses the generated constraint module's
  `_execute_module` invocation as the original exception. *If false → the evaluator cannot retain
  the required arithmetic class, message, and traceback.* Upstream generated-wrapper tests have
  already confirmed this boundary.
- **B2.** File-backed persistence remains entirely after successful module traversal. *If false →
  a later constraint failure could leave candidate output files even though no evidence returns.*
  The current executor and router ordering confirms the bet.
- **B3. Support boundary, not a concurrency claim.** Sequential reuse of one context is supported
  and `run()` resets its failed-module key. Separate contexts isolate the key. Concurrent reuse of
  one mutable context is unsupported. This item does not make `FileBackedEvaluator.evaluate()`
  thread-safe; its calls share one scratch entry path
  (`packages/teax-simkit/simkit/evaluation/evaluator.py:182`). Repeated prepared-evaluator calls
  prove separate-context isolation only, never same-context reset.

## Key Decisions

- **D1. Record a failure-only module key on `PipelineExecutionContext` and bare re-raise.** Reset
  the slot at `run()` entry. Set it only in the catch immediately around `_execute_module`; do not
  set an active key before dispatch. *Rejected: a contextual wrapper exception (requires an
  unwrap step, can leak as `EvaluationFailed.__cause__`, and adds a second exception without
  preserving more information); attaching attributes to arbitrary exceptions (mutates foreign
  objects and may fail on restricted exception types); callback/context-variable tracking (adds
  lifecycle or concurrency state); setting an active key (can falsely label later output errors).*
- **D2. Keep the context seam in the base serial executor but policy-free.** The core records only
  the exact key and re-raises the same object; it does not know about `EvaluationFailure` or
  generated constraints. *Rejected: evaluator-owned `_execute_module` subclasses (duplicate
  inheritance composition between mapping and file-backed executors and rely on another private
  hook); a public contextual exception hierarchy (changes unrelated callers' exception surface).*
- **D3. Share failure construction and raising through one normalizer.** The helper accepts any
  run exception and the execution context. It uses the recorded key when present; for another run
  exception, it retains existing behavior with `module_or_channel=None`.
  *Rejected: two evaluator-local normalizers (current duplication caused the missing-field seam);
  normalizing inside the executor (moves evaluator policy into core orchestration).*
- **D4. Keep the context field internal and narrow.** It is diagnostic run state, not exported from
  `simkit.evaluation`, added to `EvaluationPhase`, or serialized independently. Only evaluator
  normalization reads it. *Rejected: broad execution tracing or a public error-context API (more
  surface than this correction needs).*
- **D5. Add a separate, production-equivalent sealed arithmetic fixture named
  `f1_arithmetic_constraints`.** The fixture set must commit its producer at
  `packages/teax-simkit/simkit/tests/evaluation/fixtures/f1_arithmetic/generate_fixture.py`; its
  sealed output is `f1_arithmetic/package_live/`; case JSON is external at
  `f1_arithmetic/cases/`. The producer uses exact constraint IDs `f1_division_check`,
  `f2_power_check`, and `f3_nested_check`. *Rejected: calling it production-generated (no existing
  committed model/snapshot supplies this shape, and live extraction could not be validated without
  the unavailable SysIDE license); mutating the existing ToyPlant fixture (couples failure coverage
  to successful parity baselines); hand-wiring TEAx modules (does not exercise sysml-codegen's real
  constraint extension, templates, registry, pipeline, contracts, and seal).*
- **D6. Generate in a clean environment locked by the pinned sysml-codegen repository.** Create
  detached sibling worktrees at the two pinned revisions, then use `uv 0.10.0` and the pinned
  sysml-codegen `uv.lock` to create a new environment with managed CPython 3.12.11. The lock's
  editable `../agentic-mbse` source resolves to the pinned sibling worktree. `uv sync --frozen`
  therefore substitutes that exact local source while retaining every other locked registry
  version and artifact hash. Identify the local distribution by source SHA and its actual metadata
  version `0.1.0`; the lock's editable record says `0.1.1`, so that stale local-version label is not
  treated as source authority. Record the lock and environment identity in
  `f1_arithmetic/GENERATION.md`. *Rejected: an ambient interpreter, `PYTHONPATH`, or current editable
  installs (none proves the resolved generation dependencies or isolates existing developer
  environments).*

## Architecture

```text
generated constraint module.run()
        │ raises original arithmetic exception
        ▼
SerialPipelineExecutor.run
        │ context.failed_module_key = exact module_key
        │ bare raise (same exception + traceback)
        ▼
shared evaluator normalizer
        │ reads context.failed_module_key
        │ builds one EvaluationFailure
        │ raises EvaluationFailed from original
        ▼
caller sees EvaluationFailed
  failure.module_or_channel = exact module_key
  __cause__ = original arithmetic exception + traceback
```

Both routes use the existing serial run loop, so they acquire the context marker without separate
executor variants. The prepared route retains only its typed EntryPoint specialization. Graph
construction, run arguments, router, projection, and provenance stay unchanged.

The normalizer is called only around per-case `run(...)`. Preparation and entry-validation paths
retain their existing normalization. The file-backed catch retains its current phase assignment;
this item does not redesign the pre-existing output-write taxonomy boundary.

### Execution-context support boundary

- One context may be reused by sequential `run()` calls; each call clears the diagnostic key first.
- Separate contexts share no channels, module versions, entry artifacts, or failed-module key.
- Concurrent calls with one context are unsupported because the whole context is mutable run state.
- `PreparedEvaluator` remains isolated through one fresh context per call. That does not test reset.
- `FileBackedEvaluator` thread safety remains out of scope because its scratch input path is shared,
  independently of this diagnostic field.

## Required Invariants

- **I1.** For a module failure, `EvaluationFailed.__cause__ is original`; its class, message, and
  traceback remain intact. No transport exception exists.
- **I2.** The public record is exactly: `phase=MODULE_EXECUTION`,
  `module_or_channel=module_key`, `cause=f"{type(original).__name__}: {original}"`,
  `retryable=False`, and `partial_artifacts=()`.
- **I3.** The reported key comes from the invocation that raised. It is never derived from module
  type, output channel, constraint ID reconstruction, a constant, or prior-run state.
- **I4.** Executor EntryPoint loading, ExitPoint collection, and persistence failures do not
  inherit a successful module's key. Non-module per-run failures keep their current record shape,
  phase assignment, and causal behavior. This does not change `MappingEntrySource`'s existing
  `entry_validation` channel diagnostic (`packages/teax-simkit/simkit/evaluation/entry_source.py:56`).
- **I5.** No generated predicate, arithmetic renderer, verdict model, aggregator, failure phase,
  retry rule, or projection behavior changes.
- **I6.** Failure returns no `ModelEvidence` or report. A file-backed failed call adds no candidate
  output directory or output file, including when earlier constraint channel values exist in its
  execution context.
- **I7.** Existing finite satisfied/violated results and already-produced `inf`/`nan`
  indeterminate results remain evidence and retain prepared/file-backed parity.
- **I8.** A sequential second run with the same context begins with no failed-module key; a run on
  a different context cannot observe the first context's key.

## Component Overview

- **Execution context seam —
  `packages/teax-simkit/simkit/core/pipeline_executor.py`.** Add one optional failed-module key to
  the run context. Reset it at run entry and set it only when a normal module invocation raises,
  followed by bare re-raise. No evaluator imports and no changed exception surface.
- **Shared normalization —
  `packages/teax-simkit/simkit/evaluation/evaluator.py`.** Replace duplicated module-execution
  failure construction with one helper that reads the context marker and performs explicit
  chaining from the caught original exception.
- **Generated arithmetic fixture —
  `packages/teax-simkit/simkit/tests/evaluation/fixtures/f1_arithmetic/`.** Commit the deterministic
  graph producer, `GENERATION.md`, external case JSON, and sealed `package_live/` tree described in
  D5-D6. The sealed root contains generated artifacts only. Keep its EntryPoint artifact at
  `inputs/toy_plant_params.json`; the file-backed evaluator currently owns that scratch filename
  (`packages/teax-simkit/simkit/evaluation/evaluator.py:182`), and broadening it is unrelated.
- **Normalization regressions —
  `packages/teax-simkit/simkit/tests/evaluation/`.** Add fixture construction and cross-backend
  assertions near the current failure-taxonomy/parity tests. Keep small transport-only coverage
  separate from generated-package acceptance coverage if needed for a precise traceback assertion.

## Non-Goals

- Arithmetic guards, safe operators, exception-to-value conversion, or sysml-codegen changes.
- Changes to satisfied, violated, indeterminate, aggregate headline, or margin semantics.
- A new public executor exception contract or broader execution-tracing refactor.
- New failure phases, retry behavior, partial-artifact semantics, or study-runner behavior.
- Recovering partial constraint evidence or persisting diagnostic candidate outputs after failure.
- Reworking output-write failure classification or unrelated executor exceptions.

## Implementation Notes

- Use a bare `raise` in the executor catch. `raise error` would alter the traceback; creating a new
  exception would alter both identity and chaining.
- Catch `Exception`, not `BaseException`, at the module-call seam. Process-control exceptions keep
  Python's normal behavior.
- Reset the marker before traversal, not after successful completion. Reused contexts must be clean
  even if the previous run failed.
- Do not infer identity from the generated naming convention. The executor-provided module key is
  authoritative; tests may separately assert it equals the fixture constraint ID lowercased.
- Keep the shared helper responsible for the `raise`, not only record construction. This ensures
  both evaluator call sites use identical explicit chaining.
- Preserve current evaluator catch placement around the complete `run(...)` call. Only failures
  caught around `_execute_module` gain module identity; other run failures retain the old empty
  identity.

## Potential Risks

- **A re-raise changes the traceback.** Mitigation: core transport coverage asserts the raised
  object is the sentinel original and its traceback retains the module `run` frame; implementation
  uses bare `raise`.
- **A marker survives context reuse.** Mitigation: reset at every `run()` entry and add a focused
  reused-context regression.
- **A constant/stale key passes shallow tests.** Mitigation: make at least two distinct constraint
  module keys fail across the evaluator matrix; prove stale-state reset only with sequential reuse
  of the same context in the core test.
- **File fixture persistence from earlier successful tests obscures a failed write.** Mitigation:
  use a fresh output root per failure call or snapshot its complete relative-path manifest before
  and after; assert equality after the failure.
- **The production-equivalent fixture drifts from its producer.** Mitigation: regenerate only from
  the committed producer under both pinned clean worktrees; record producer hash and executable
  fingerprint; assert graph, YAML, and TEAx topological order; verify the seal before every load.

## Integration Strategy

Land one diagnostic field and a bare-re-raise catch in the core executor, then keep all failure
policy inside the existing evaluation layer. Direct `SerialPipelineExecutor` users still receive
the identical exception object and traceback. `PreparedEvaluator`, `FileBackedEvaluator`, and
`StudyRunner` keep their public call shapes. Study persistence automatically gains the module key
because it already serializes the unchanged `EvaluationFailure` record
(`packages/teax-simkit/simkit/study/runner.py:97`).

The new production-equivalent package fixture is additive. Existing ToyPlant tests continue to
guard successful finite/non-finite behavior without being rewritten around arithmetic failures.
Run the focused evaluation suite first, then the full repository suite.

## Validation Approach

### Generated-package matrix

Use the committed `f1_arithmetic_constraints` production-equivalent fixture from D5-D6. Its
independent inputs let every non-target predicate complete safely. At fixture regeneration and at
kept-test setup, assert the actual graph/YAML/TEAx topological order is:
`entry_fusion`, `f1_division_check`, `f2_power_check`, `f3_nested_check`,
`constraint_report_aggregator`, `exit_point`. Do not infer order from YAML declaration alone.

| Case | Target shape | Native exception and message | Failed key | Ordering observation |
|---|---|---|---|---|
| division | `a / b > 0`, `b=0` | `ZeroDivisionError: float division by zero` | `f1_division_check` | fails first constraint |
| negative power | `a ** b > 0`, `a=0`, `b=-1` | `ZeroDivisionError: 0.0 cannot be raised to a negative power` | `f2_power_check` | division completes first |
| overflow | `a ** b > 0`, `a=10`, `b=400` | `OverflowError: (34, 'Numerical result out of range')` | `f2_power_check` | division completes first |
| nested | `(a / b > 0) and (a > -1)`, `b=0` | `ZeroDivisionError: float division by zero` | `f3_nested_check` | division and power complete first |

For each row, run prepared and file-backed evaluators and assert:

- both raise `EvaluationFailed`, never return `ModelEvidence`;
- their `EvaluationFailure` values are equal and match every field in I2;
- each `__cause__` has the expected native class and exact supported-runtime message;
- each native cause has no added cause of its own, proving no transport double-wrap;
- each cause traceback contains the generated predicate/wrapper path;
- no aggregate report is returned; and
- the exact candidate-output-tree manifest is unchanged, as defined below.

The two power rows reuse a key deliberately, while division and nested provide distinct keys. This
makes a constant label fail. Repeated prepared calls test multiple-key behavior and separate-context
isolation only.

Prove earlier completion in a separate, fresh direct run with no registry mutation: create a new
file-backed evaluator/context for the sealed fixture, copy the selected external case to its scratch
entry path, and call that evaluator's real serial executor with `persist_outputs=False`. Catch the
native later exception, then inspect the same context. For the power case,
`f1_division_check__evaluation` must exist. For the nested case, both earlier evaluation channels
must exist. The failed and aggregate channels must not exist. Keep this white-box execution proof
separate from the evaluator API assertions that no evidence returns and no candidate output persists.

### Identity-catch boundary negatives

These tests preserve current phases; they only assert the new identity field stays empty.

- **Executor EntryPoint:** a fresh file-backed evaluator copies malformed JSON into its expected
  scratch entry path, then its real EntryPoint loader fails during `run()`. Assert the existing
  `MODULE_EXECUTION` phase, direct original cause, and `module_or_channel is None`. Do not use
  `MappingEntrySource` wrong-model rejection; that separate `ENTRY_VALIDATION` contract already
  names its channel.
- **ExitPoint collection:** use a fresh minimal executor/graph and a test-only context whose
  `get_channel` raises an ExitPoint sentinel only for the exit-bound channel after a normal module
  completes. Assert bare exception identity and `failed_module_key is None`; pass that caught error
  and context through the shared evaluator normalizer and assert the unchanged phase plus
  `module_or_channel is None`. This induces the real ExitPoint collection path without adding a
  production test branch.
- **Router persistence:** give a fresh file-backed evaluator a base output path that is an existing
  regular file, so the real router fails while preparing its run directory after all modules
  succeed (`packages/teax-simkit/simkit/io/output_router.py:239`). Assert the evaluator's existing
  `MODULE_EXECUTION` phase, direct cause, and `module_or_channel is None`. Do not repair or rename
  the phase in this item.

### Exact filesystem assertions

For every arithmetic failure, compute a complete manifest of the candidate output root immediately
before and after `evaluate()`. The manifest records every relative path as directory, regular file
plus SHA-256 of bytes, or symlink plus target. An absent root has the exact manifest `("absent",)`.
Use a fresh absent root; assert `before == after == ("absent",)`. This catches run directories,
output JSON, and manifests, not only known filenames.

The scratch work tree is separate and permitted to change only by creation/replacement of
`inputs/toy_plant_params.json` with bytes exactly equal to the selected external case. Its copied
`pipelines/pipeline.yaml` and all other before-manifest entries must be byte-identical; no other
scratch path may appear. Case JSON and `GENERATION.md` stay outside `package_live/`, so seal
verification does not treat them as unhashed extras.

### Preservation matrix

- Keep the current `satisfied`, `violated`, budget-NaN indeterminate, and output-NaN indeterminate
  parity cases unchanged (`packages/teax-simkit/simkit/tests/evaluation/test_parity.py:18`).
- Add safe-input cases for the new arithmetic package that complete all constraint modules and
  produce finite satisfied/violated evidence. Include already-produced `inf`/`nan` operands that
  reach `_cmp` and return indeterminate without raising.
- Re-run existing module-exception taxonomy coverage to prove generic module failures remain
  terminal and retain their original cause text.
- Add a core executor test with a sentinel exception: assert object identity after `run()`, intact
  traceback, exact context key, then run a successful graph with the reused context and assert the
  key was reset to `None`.
- Add a second-context assertion proving its marker remains `None`; do not add concurrent
  same-context or file-backed thread-safety tests because those routes are explicitly unsupported.
- Run `pytest packages/teax-simkit/simkit/tests/evaluation -q`, then `pytest`.

## Next-Stage Handoff

- **Fixed:** exact module key, public record fields, direct original cause, unchanged semantics and
  policies, context-marker transport with bare re-raise, shared normalizer, additive
  production-equivalent fixture, execution-context support boundary, boundary-negative validation,
  exact filesystem manifests, and the fixture provenance/workflow in Appendix A.
- **Open to plan:** context-field/helper names and whether transport-only assertions live in the
  existing taxonomy file or a new focused test file. Fixture source, package name, IDs, revision
  pins, cases location, generation workflow, order assertions, and seal checks are not open.
- **De-risk first:** write the core object-identity/traceback transport test and the cross-backend
  cause/key test against two failing module keys before filling out the four-case arithmetic matrix.
  They expose traceback damage, stale identity, and backend drift immediately.
- **Product design:** skipped because the contract has no consumer-facing surface.
- **Review resolution:** Revision 3 objectively resolves the only Revision 2 review finding by
  replacing the ambient interpreter with the pinned lock workflow below. All Revision 2
  architecture and validation remain unchanged.
- **Next step:** run `my-plan`.

## Appendix A: Fixture Reproduction Contract

`f1_arithmetic_constraints` is not live-model-generated or snapshot-generated. Current committed
upstream inputs do not supply this exact independently controlled shape, and this design session
could not validate/capture a new live input without a SysIDE license. It is a production-equivalent
sealed fixture rendered from a committed synthetic constraint graph through production constraint
extension, catalog, template, registry, pipeline, contract, and seal APIs.

### Required committed inputs and outputs

- Producer to commit with the fixture:
  `packages/teax-simkit/simkit/tests/evaluation/fixtures/f1_arithmetic/generate_fixture.py`.
- Provenance record: sibling `GENERATION.md`, containing both Git SHAs, producer SHA-256, command,
  declared name, graph/YAML order, seal fingerprint, generation timestamp, uv version, lockfile
  SHA-256, Python identity, platform/ABI identity, source distribution versions, resolved
  generation-dependency versions, and the environment fingerprint defined below.
- Sealed output: sibling `package_live/`, declared package name `f1_arithmetic_constraints`.
- External cases: sibling `cases/`, containing `division_by_zero.json`,
  `zero_negative_power.json`, `exponent_overflow.json`, `nested_division.json`,
  `safe_satisfied.json`, `safe_violated.json`, and `nonfinite_indeterminate.json`; never copy cases
  or regeneration notes into `package_live/`.
- Constraints in producer order: `f1_division_check`, `f2_power_check`, `f3_nested_check`.
- Upstream pins: sysml-codegen `512786c7dfab44fba7a0185d09e845b7494c702d` and agentic-mbse
  `4ed2a0728ea49298666415cd389d9a6173a81a3e`.

The producer builds expression IR with committed agentic-mbse node/serialization APIs, constructs
three `ConcreteConstraint` records with independent design-attribute inputs, calls production
`extend_graph_with_constraints` and `assemble_constraint_catalog`, then mirrors `run_codegen` steps
2-9, including `_seal_package` last. It refuses another package name or dirty/unpinned imported
source, deletes only its explicit output target when `--overwrite` is given, and asserts graph and
emitted YAML module order before accepting the output.

### Regeneration workflow

The pinned sysml-codegen revision contains `uv.lock` revision 3 and declares agentic-mbse as the
editable sibling `../agentic-mbse`. Its lock SHA-256 is
`b457136b857974c655094b86496dc88809b2dc405146340aa5f02ebb8a284c05`. From the TEAx repository
root, use the following commands. `mktemp` makes a new root, and `UV_PROJECT_ENVIRONMENT` confines
the new environment to it; no existing developer environment is read or changed.

```bash
generation_root="$(mktemp -d /tmp/teax-f1-generation.XXXXXX)"
test "$(uv --version)" = "uv 0.10.0"
git -C ../sysml-codegen worktree add --detach "$generation_root/sysml-codegen" \
  512786c7dfab44fba7a0185d09e845b7494c702d
git -C ../agentic-mbse worktree add --detach "$generation_root/agentic-mbse" \
  4ed2a0728ea49298666415cd389d9a6173a81a3e
test "$(sha256sum "$generation_root/sysml-codegen/uv.lock" | cut -d ' ' -f 1)" = \
  "b457136b857974c655094b86496dc88809b2dc405146340aa5f02ebb8a284c05"
UV_PROJECT_ENVIRONMENT="$generation_root/environment" \
  uv sync --project "$generation_root/sysml-codegen" --frozen --no-dev \
  --python 3.12.11 --managed-python
"$generation_root/environment/bin/python" \
  packages/teax-simkit/simkit/tests/evaluation/fixtures/f1_arithmetic/generate_fixture.py \
  --output packages/teax-simkit/simkit/tests/evaluation/fixtures/f1_arithmetic/package_live \
  --package-name f1_arithmetic_constraints --overwrite
```

Before deleting or rendering output, the producer rejects the run unless all of these preflight
facts hold:

- the interpreter is CPython 3.12.11, and `sys.executable` is inside the fresh
  `$generation_root/environment` rather than an activated or ambient environment;
- the imported sysml-codegen and agentic-mbse modules resolve inside the two detached worktrees,
  whose `HEAD` values equal the pins above and whose tracked files are clean;
- the imported local distribution metadata is sysml-codegen 0.1.0 and agentic-mbse 0.1.0;
- the pinned lockfile hash matches the value above, and the generation dependencies resolved from
  it are Jinja2 3.1.6, Pydantic 2.12.5, and PyYAML 6.0.3; and
- no `PYTHONPATH` override is present.

`GENERATION.md` records those checked values plus `uv 0.10.0`, Python implementation/full version,
`sys.implementation.cache_tag`, `sysconfig.get_platform()`, the complete sorted installed-
distribution name/version listing, and an environment fingerprint. That fingerprint is SHA-256
over canonical JSON containing the uv version, lock hash, Python/platform/ABI fields, both source
SHAs and distribution versions, and those sorted name/version pairs. Temporary absolute paths are
not part of the fingerprint.

After generation, the producer and kept fixture setup both require:

- production graph order exactly `f1_division_check`, `f2_power_check`, `f3_nested_check`,
  `constraint_report_aggregator`;
- emitted YAML module order exactly `entry_fusion`, those four graph modules, then `exit_point`;
- TEAx `PipelineGraph.topological_order` exactly equal to that emitted six-module order;
- `contracts/package_contract.json` records package name `f1_arithmetic_constraints` and covers
  every file except itself under its stated policy; and
- `ProvisionalPackageLoader` verifies the package with zero diagnostics before import, returning
  the executable fingerprint recorded in `GENERATION.md`.
