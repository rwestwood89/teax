# Implementation Plan: GAP-CLOSE F1 TEAx Normalization

**Status:** Complete
**Created:** 2026-07-18
**Last Updated:** 2026-07-18

## Source Documents

- **Reviewed spec:** [spec.md](spec.md)
- **Approved design:** [design.md](design.md), status `Ready for Planning (Revision 3)`
- **Spec review:** [spec-review.md](spec-review.md)
- **Design review:** [design-review.md](design-review.md)
- **Project context:** [../../CURRENT_WORK.md](../../CURRENT_WORK.md)

The design's Revision 3 is accepted for planning without a third design-review run. Revision 2's
only remaining finding was the unlocked fixture-generation environment. Revision 3 changes only
that workflow: it pins the two source SHAs, `uv 0.10.0`, the `uv.lock` SHA-256, managed CPython,
and the locked Jinja2/Pydantic/PyYAML versions in
[Appendix A](design.md#appendix-a-fixture-reproduction-contract). Those facts were directly
verified. The implementation architecture, observable contract, scope, and validation matrix did
not change, so another reviewer rerun would repeat already-passed judgments rather than reduce an
open design risk.

Product design remains skipped for the reason recorded in the
[design overview](design.md#overview): this is an internal failure-normalization contract with no
consumer-facing interaction or presentation decision.

## Implementation Strategy

### Phasing Rationale

The plan follows the shortest chain from authoritative failure context to public behavior. First,
prove that the executor can record the exact module key without changing the exception object or
traceback. Second, consume that marker through one evaluator normalizer and prove that adjacent
non-module boundaries remain unlabeled. Third, create and seal the reproducible production-
equivalent fixture before relying on it for acceptance tests. Fourth, run the complete arithmetic
matrix through both evaluator backends and prove ordering and filesystem atomicity. Last, preserve
all successful verdict behavior and run the repository-wide regression suite.

### Critical Path

`executor marker + bare re-raise` → `shared evaluator normalizer` → `locked fixture regeneration`
→ `cross-backend arithmetic/order/no-output proofs` → `preservation and full-suite validation`

### First Proof Point

A focused core test catches the exact sentinel exception object raised by a test module, finds that
module's `run` frame in its traceback, and reads the exact invocation key from the same execution
context. A successful second run with that context then proves the marker resets to `None`.

### Overall Validation Approach

- Every phase begins with a failing test or deterministic fixture check before production changes.
- Focused commands run after each small batch; the full suite is reserved for the preservation
  phase so early feedback stays fast.
- Generated artifacts are accepted only after source, order, contract coverage, and seal checks.
- Existing user changes are preserved. Before each phase, inspect `git status --short` and the
  relevant diff; do not overwrite or fold unrelated edits into this work.
- Do not refactor executor/evaluator code outside the seams fixed in
  [Component Overview](design.md#component-overview), and do not modify sysml-codegen or
  agentic-mbse source worktrees.

## Phase 1: Core Context Marker and Exception Identity

### Goal

Establish the policy-free executor transport seam first. This collapses the highest-risk
assumption: adding context must not wrap, replace, or damage the original arithmetic exception.
See [D1-D2](design.md#key-decisions), [I1, I3, and I8](design.md#required-invariants), and the
[implementation notes](design.md#implementation-notes).

### Assumption Under Test

The serial run loop can attach the exact failing invocation key to per-run context while a bare
re-raise preserves exception identity and traceback. Sequential context reuse resets stale state,
and a separate context remains isolated.

### Test Stencil (Write First)

```python
sentinel = SentinelError("arithmetic failed")
executor, failing_graph, success_graph, context = build_core_probe(sentinel)
with pytest.raises(SentinelError) as caught:
    executor.run(failing_graph, context, persist_outputs=False)
assert caught.value is sentinel
assert "run" in traceback_frame_names(caught.value.__traceback__)
assert context.failed_module_key == "later_constraint"
executor.run(success_graph, context, persist_outputs=False)
assert context.failed_module_key is None
```

### Changes Required

- [x] **Write tests first:** add
  `packages/teax-simkit/simkit/tests/core/test_pipeline_executor_failure_context.py` with a minimal
  real graph/registry probe covering exact exception object identity, traceback preservation, the
  exact failing module key, same-context reset after failure, and second-context isolation. Test
  `run()`, not `_execute_module()` alone, because the marker lifecycle belongs to the traversal.
- [x] **Implement the seam:** update
  `packages/teax-simkit/simkit/core/pipeline_executor.py:33-54,107-162` with one optional internal
  context marker, reset it before traversal, and set it only in `except Exception` around the
  normal-module `_execute_module(module_key, ...)` call. Use bare `raise`; do not catch
  `BaseException`, set an active key before dispatch, or introduce an evaluator import or wrapper
  exception.

### Validation

**Automated**

- [x] Run `pytest packages/teax-simkit/simkit/tests/core/test_pipeline_executor_failure_context.py -q`.
- [x] Run `pytest packages/teax-simkit/simkit/tests/core -q` to catch executor regressions.

**Manual inspection**

- [x] Inspect `git diff -- packages/teax-simkit/simkit/core/pipeline_executor.py` and confirm the
  catch covers only normal module dispatch; EntryPoint, ExitPoint, and router persistence remain
  outside it.

### Completion Criteria

- The core probe passes with `caught.value is sentinel`, the original module `run` traceback frame,
  the exact invocation key, same-context reset, and separate-context isolation.
- Direct executor callers still receive the original exception, not a transport or normalized
  exception.
- [x] Immediately mark every completed Phase 1 checkbox, then fill in
  [Phase 1 Completion](#phase-1-completion) with timestamp, actual files, test output, issues, and
  deviations before starting Phase 2.

## Phase 2: Shared Normalization and Boundary Negatives

### Goal

Replace the two duplicated per-run catches with one private normalizer and prove the module marker
does not leak onto EntryPoint, ExitPoint, or router failures. See [D3-D4](design.md#key-decisions),
[I2 and I4](design.md#required-invariants), and
[Identity-catch boundary negatives](design.md#identity-catch-boundary-negatives).

### Assumption Under Test

Both evaluator routes can construct and raise the exact same `EvaluationFailure` from the original
exception, while per-run errors outside normal module dispatch retain `module_or_channel=None` and
their existing phase behavior.

### Test Stencil (Write First)

```python
with pytest.raises(EvaluationFailed) as caught:
    normalize_run_failure(original, context)
assert caught.value.__cause__ is original
assert caught.value.failure == EvaluationFailure(
    phase=EvaluationPhase.MODULE_EXECUTION,
    module_or_channel="failed_key",
    cause="SentinelError: arithmetic failed",
)
assert boundary_failure.failure.module_or_channel is None
```

### Changes Required

- [x] **Write tests first:** add
  `packages/teax-simkit/simkit/tests/evaluation/test_failure_normalization.py` with focused tests
  for the complete immutable record, explicit direct chaining, and the three real boundary
  negatives specified by the design: malformed file EntryPoint JSON, test-context ExitPoint
  collection failure, and router setup failure against an existing regular file. Assert the
  current phases; do not repair output-write taxonomy in this item.
- [x] **Keep existing generic coverage:** extend only the assertions needed in
  `packages/teax-simkit/simkit/tests/evaluation/test_failure_taxonomy.py:28-40` so a generic module
  exception remains terminal, has exact cause text, and receives its actual module key. Preserve
  the current registry restoration guard and do not convert this session fixture into arithmetic
  acceptance coverage.
- [x] **Implement one normalizer:** update
  `packages/teax-simkit/simkit/evaluation/evaluator.py:106-123,185-199` with a private helper that
  reads the context marker, builds the fixed module-execution record, and itself performs
  `raise EvaluationFailed(...) from error`. Route both evaluator catches through it. Leave
  preparation and mapping-entry validation paths unchanged.

### Validation

**Automated**

- [x] Run `pytest packages/teax-simkit/simkit/tests/evaluation/test_failure_normalization.py packages/teax-simkit/simkit/tests/evaluation/test_failure_taxonomy.py -q`.
- [x] Re-run the Phase 1 core test to prove evaluator work did not alter transport behavior.

**Manual inspection**

- [x] Confirm there is one per-run normalization implementation and two call sites, and that the
  helper's fallback for unrelated run exceptions leaves `module_or_channel=None`.

### Completion Criteria

- Prepared and file-backed run catches share one record-and-raise path with direct original cause.
- Module failures gain the exact context key; EntryPoint, ExitPoint, and router failures do not.
- No public failure type, phase, retry rule, or partial-artifact behavior changes.
- [x] Immediately mark every completed Phase 2 checkbox, then fill in
  [Phase 2 Completion](#phase-2-completion) before starting fixture work.

## Phase 3: Reproducible Production-Equivalent Fixture and Seal

### Goal

Create the additive `f1_arithmetic_constraints` fixture using the exact locked workflow in
[D5-D6](design.md#key-decisions) and
[Appendix A](design.md#appendix-a-fixture-reproduction-contract). This phase must complete before
the arithmetic matrix is written so tests cannot harden around a hand-built approximation.

### Assumption Under Test

The committed producer can reproduce the required independent arithmetic constraints through
production sysml-codegen APIs in clean pinned worktrees, and TEAx can verify and load the final seal
with the exact required graph, YAML, and topological order.

### Test Stencil (Write First)

```python
package, fingerprint = loader_for_f1_fixture(tmp_path).load()
assert package.__name__ == "f1_arithmetic_constraints"
assert graph_constraint_order(package) == EXPECTED_CONSTRAINT_ORDER
assert yaml_module_order(package) == EXPECTED_MODULE_ORDER
assert teax_topological_order(package) == EXPECTED_MODULE_ORDER
assert generation_record_fingerprint() == fingerprint
assert verify_contract_coverage(package) == []
```

### Changes Required

- [x] **Write fixture acceptance checks first:** add fixture-loading/order/seal assertions to
  `packages/teax-simkit/simkit/tests/evaluation/conftest.py` or a new focused
  `test_f1_arithmetic_fixture.py`. Keep the existing `wi014_s4` session fixtures unchanged; use a
  unique loader link root and fresh evaluators for the new package.
- [x] **Commit the deterministic producer:** add
  `packages/teax-simkit/simkit/tests/evaluation/fixtures/f1_arithmetic/generate_fixture.py` with the
  exact preflight, source-fact construction, production API calls, refusal rules, order checks,
  overwrite scope, and final sealing behavior fixed in Appendix A. The producer may delete only
  its explicit `--output` target when `--overwrite` is supplied.
- [x] **Add external cases:** create the seven JSON inputs under
  `packages/teax-simkit/simkit/tests/evaluation/fixtures/f1_arithmetic/cases/` with the exact names
  and roles in Appendix A. Keep them outside the sealed root.
- [x] **Regenerate in isolation:** create clean detached sibling worktrees at the pinned
  sysml-codegen and agentic-mbse SHAs, verify `uv 0.10.0` and the pinned `uv.lock` SHA-256, run
  `uv sync --frozen --no-dev --python 3.12.11 --managed-python` with
  `UV_PROJECT_ENVIRONMENT` inside a new `mktemp` root, and invoke the producer from that
  interpreter. Follow Appendix A exactly; never use an ambient virtualenv or `PYTHONPATH`.
- [x] **Commit provenance and generated output:** add sibling `GENERATION.md` with every required
  source, tool, environment, distribution, producer, order, seal, and fingerprint field, plus the
  generated `package_live/` tree. The sealed root contains generated package artifacts only; do
  not place cases or notes inside it.

### Environment and Approval Gate

- Implementation may need approval before dependency/environment creation if the sandbox blocks
  managed-Python download, locked dependency installation, or sibling worktree creation. Request
  that approval at the point of need with the exact `uv sync` or `git worktree add` command. Do
  not substitute the current environment or loosen `--frozen` if approval or network access is
  unavailable.
- Use an explicit `mktemp` root. Record the worktrees so they can be removed with the corresponding
  non-destructive `git worktree remove` commands after successful generation; do not recursively
  delete unresolved paths.

### Validation

**Automated and reproducibility checks**

- [x] Run the fixture acceptance test alone and require zero seal diagnostics.
- [x] Run the producer a second time into a separate temporary output under the same locked
  environment and compare deterministic generated content plus the recorded executable
  fingerprint, excluding only explicitly documented generation-time fields.
- [x] Run `git -C <clean-sysml-worktree> status --short` and
  `git -C <clean-agentic-worktree> status --short`; both must remain empty.

**Manual inspection**

- [x] Compare the committed producer, `GENERATION.md`, cases, and sealed-root layout against every
  item in Appendix A. Confirm the recorded Jinja2 3.1.6, Pydantic 2.12.5, and PyYAML 6.0.3 versions
  came from the frozen environment.

### Completion Criteria

- The producer and seven external cases are committed beside, never inside, the sealed root.
- The production seal verifies with zero diagnostics, its declared name and executable fingerprint
  match `GENERATION.md`, and all three order observations match the fixed sequence.
- Regeneration is attributable to both pinned sources and the complete locked environment.
- [x] Immediately mark every completed Phase 3 checkbox, then fill in
  [Phase 3 Completion](#phase-3-completion) with commands, approvals, environment identity, and
  artifact fingerprints before starting acceptance coverage.

## Phase 4: Cross-Backend Arithmetic Matrix, Ordering, and No Partial Output

### Goal

Exercise every required arithmetic raise through both public evaluator routes, then separately
prove that earlier constraint work may exist only inside the failed execution context and never
escapes as evidence, an aggregate report, or persisted candidate output. See
[Generated-package matrix](design.md#generated-package-matrix) and
[Exact filesystem assertions](design.md#exact-filesystem-assertions).

### Assumption Under Test

The sealed fixture raises the native supported-runtime exceptions at three distinct generated
module keys; both backends normalize them identically; serial ordering stops before aggregation;
and file-backed failure leaves the complete candidate output tree unchanged.

### Test Stencil (Write First)

```python
@pytest.mark.parametrize("case, error_type, message, key", ARITHMETIC_CASES)
def test_both_backends_normalize(case, error_type, message, key, evaluators):
    prepared_error = capture_failure(evaluators.prepared, case)
    before = tree_manifest(evaluators.output_root)
    file_error = capture_failure(evaluators.file_backed, case)
    assert prepared_error.failure == file_error.failure == expected_failure(error_type, message, key)
    assert type(prepared_error.__cause__) is type(file_error.__cause__) is error_type
    assert tree_manifest(evaluators.output_root) == before == ("absent",)
```

### Changes Required

- [x] **Write the full matrix first:** add
  `packages/teax-simkit/simkit/tests/evaluation/test_f1_arithmetic_normalization.py` with the four
  exact rows from the design. For each prepared/file-backed pair, assert every failure field,
  direct native cause class/message, no nested transport cause, generated traceback path, no
  returned evidence/report, and equality of complete failure records.
- [x] **Add exact manifest helpers locally to the focused test or its fixture support:** represent
  absent roots, directories, file byte hashes, and symlink targets exactly as specified. Use a
  fresh absent candidate output root for every failed file-backed call; separately assert that the
  scratch tree changes only at `inputs/toy_plant_params.json` and that its bytes equal the selected
  external case.
- [x] **Prove actual execution order without registry mutation:** in the same focused test module,
  use fresh file-backed evaluator/executor/context instances and `persist_outputs=False` for the
  later-failing power and nested cases. Inspect that same context for the required earlier
  evaluation channels and absence of the failed/aggregate channels. Assert the graph's actual
  `topological_order` before interpreting channel presence.
- [x] **Keep fixture setup isolated:** extend
  `packages/teax-simkit/simkit/tests/evaluation/conftest.py` only with additive F1 constants/helper
  factories if sharing removes duplication. Do not mutate the existing session-scoped package
  registry or generated package files.

### Validation

**Automated**

- [x] Run `pytest packages/teax-simkit/simkit/tests/evaluation/test_f1_arithmetic_normalization.py -q`.
- [x] Run each parametrized case independently once (`division`, `negative power`, `overflow`,
  `nested`) to make failure diagnostics attributable and confirm at least two different reported
  keys; the complete matrix must exercise all three fixed keys.
- [x] Run `pytest packages/teax-simkit/simkit/tests/evaluation -q`.

**Manual inspection**

- [x] Inspect the focused test's before/after manifests and direct-run channel assertions. Confirm
  no assertion relies on YAML declaration order alone or merely checks known output filenames.

### Completion Criteria

- All eight public evaluator executions raise `EvaluationFailed` with pairwise-equal complete
  records, exact native direct causes, and the correct changing module key.
- The power and nested direct runs prove earlier constraints completed, while no aggregate channel,
  returned `ModelEvidence`, or candidate output appears.
- Candidate output roots remain exactly absent and scratch mutations are precisely bounded.
- [x] Immediately mark every completed Phase 4 checkbox, then fill in
  [Phase 4 Completion](#phase-4-completion) before preservation validation.

## Phase 5: Preservation Matrix and Full-Suite Validation

### Goal

Prove the narrow correction leaves successful finite verdicts, already-produced non-finite
indeterminate evidence, existing evaluator parity, generic failures, and the rest of the repository
unchanged. See [I5 and I7](design.md#required-invariants) and
[Preservation matrix](design.md#preservation-matrix).

### Assumption Under Test

Only raised exceptions from normal module execution gain a module-specific normalized failure.
Arithmetic that completes, including `inf`/`nan`, preserves existing evidence semantics across both
backends, and unrelated packages and study behavior remain green.

### Test Stencil (Write First)

```python
@pytest.mark.parametrize("case, headline", SAFE_CASES)
def test_f1_safe_cases_preserve_evidence(case, headline, f1_evaluators):
    prepared = evaluate_prepared(case)
    file_backed = evaluate_file(case)
    assert prepared.responses == file_backed.responses
    assert prepared.responses["headline"] == headline
    assert no_failure_record(prepared, file_backed)
```

### Changes Required

- [x] **Write preservation cases first:** add safe satisfied, safe violated, and already-produced
  non-finite F1 fixture assertions to
  `packages/teax-simkit/simkit/tests/evaluation/test_f1_arithmetic_normalization.py` or a focused
  companion parity file. Compare both evaluator routes and require the expected finite verdict or
  indeterminate evidence, never `EvaluationFailed`.
- [x] **Preserve existing baselines:** leave the current `satisfied`, `violated`, `F_budget`, and
  `F_output` cases in
  `packages/teax-simkit/simkit/tests/evaluation/test_parity.py:18-78` unchanged. Add assertions only
  if needed to expose a regression that the existing cases do not already catch.
- [x] **Review the final diff:** remove no unrelated code, generated fixture, test, or documentation
  change. Do not introduce arithmetic guards, public APIs, phase changes, concurrency work, output
  recovery, or sysml-codegen edits.

### Validation

**Automated**

- [x] Run `pytest packages/teax-simkit/simkit/tests/evaluation -q`.
- [x] Run `pytest packages/teax-simkit/ -q`.
- [x] Run `pytest` from the repository root; all framework and battery-demo tests must pass.

**Manual inspection**

- [x] Run `git status --short` and `git diff --check`, then inspect the complete scoped diff. Record
  pre-existing user changes separately from this item's files; do not revert or rewrite them.
- [x] Confirm no new dependency or lint command was invented: this repository defines pytest but
  no project ruff/black/mypy configuration or required lint script.

### Completion Criteria

- The new safe arithmetic cases and all existing successful parity/non-finite cases pass through
  both backends with unchanged evidence semantics.
- Focused evaluation, full framework, and full repository suites pass.
- The final diff contains only the executor marker, shared normalizer, additive fixture/provenance,
  and their tests/documentation.
- [x] Immediately mark every completed Phase 5 checkbox, fill in
  [Phase 5 Completion](#phase-5-completion), and change plan status to `Complete` only after all
  commands and criteria pass.

## Risk Management

The full risk analysis is in [Potential Risks](design.md#potential-risks). Phase-specific controls
are:

- **Phase 1:** object-identity, traceback-frame, exact-key, reset, and isolation assertions fail
  immediately if transport wraps the exception or leaks stale state.
- **Phase 2:** real boundary negatives prevent an overly broad catch or active-key design from
  labeling EntryPoint, ExitPoint, or persistence failures.
- **Phase 3:** clean pinned worktrees, frozen lock resolution, producer preflight, order checks, and
  seal verification prevent ambient-environment or hand-assembly drift.
- **Phase 4:** three distinct failed keys, complete filesystem manifests, and direct same-context
  channel inspection defeat constant labels and weak no-partial-output assertions.
- **Phase 5:** unchanged baseline cases plus full-suite execution guard the intentionally narrow
  scope.

## Implementation Notes

Fill these sections immediately after each phase. Do not defer checkbox or note updates to the end
of implementation. Record exact commands and outcomes; if a phase deviates, explain why and cite
the relevant design invariant before proceeding.

### Phase 1 Completion

**Completed:** 2026-07-18T20:22:15-07:00

**Actual Changes:**
- Added `test_pipeline_executor_failure_context.py` with a real traversal probe for exact exception
  identity, traceback retention, failed invocation key, same-context reset, and separate-context
  isolation.
- Added `PipelineExecutionContext.failed_module_key`, reset it at `run()` entry, and populated it
  only in the catch immediately around normal-module dispatch with a bare re-raise.

**Validation Evidence:**
- `.venv/bin/pytest packages/teax-simkit/simkit/tests/core/test_pipeline_executor_failure_context.py -q`
  passed: 1 test.
- `.venv/bin/pytest packages/teax-simkit/simkit/tests/core -q` passed: 87 tests.
- Scoped diff confirms EntryPoint, ExitPoint collection, and router persistence remain outside the
  identity catch.

**Issues / Resolutions:**
- Bare `pytest` was unavailable on `PATH`; the repository's existing `.venv/bin/pytest` is healthy
  and was used for all validation. `uv run` could not initialize its read-only home cache, so it
  was not used as an environment substitute.

**Deviations:** None.

### Phase 2 Completion

**Completed:** 2026-07-18T20:24:02-07:00

**Actual Changes:**
- Added `test_failure_normalization.py` covering the complete record, direct chaining, malformed
  file EntryPoint JSON, real ExitPoint collection failure, and real router setup failure.
- Extended generic module-failure coverage with the actual invocation key, exact cause, terminal
  retry, and empty partial artifacts.
- Added one private `_normalize_run_failure` record-and-raise helper and routed both evaluator run
  catches through it.

**Validation Evidence:**
- `.venv/bin/pytest packages/teax-simkit/simkit/tests/evaluation/test_failure_normalization.py packages/teax-simkit/simkit/tests/evaluation/test_failure_taxonomy.py -q`
  passed: 8 tests.
- `.venv/bin/pytest packages/teax-simkit/simkit/tests/core/test_pipeline_executor_failure_context.py -q`
  passed: 1 test.
- Source scan confirms one private normalizer and two call sites. Its unrelated-run fallback reads
  the reset `None` marker without assigning a label.

**Issues / Resolutions:** None.

**Deviations:** None.

### Phase 3 Completion

**Completed:** 2026-07-18T20:33:56-07:00

**Actual Changes:**
- Added the deterministic producer, seven external cases, locked-environment provenance record,
  sealed `package_live/`, and focused fixture acceptance test.
- The producer creates three independent production constraint modules, asserts production graph
  and emitted YAML order, enforces all Revision 3 source/environment preflights, and seals last.
- The acceptance test reads the production contract shape (`constraint_catalog` embedded in
  `contracts/model_contract.json`), verifies the seal/name/fingerprint and exact contract coverage,
  and asserts actual TEAx topological order.
- Preserved generated `IMPLEMENTATION_BACKLOG.md`: production generated it before sealing and
  `package_contract.json` hashes it. Removed only explicit transient `__pycache__` directories,
  which are excluded runtime artifacts and not fixture content.

**Validation Evidence:**
- Raw orchestration log records `/tmp/teax-f1-generation.BGv8vL`, detached SHAs
  `512786c7...` and `4ed2a072...`, `uv sync --frozen --no-dev --python 3.12.11 --managed-python`,
  and successful generation from that environment interpreter with no ambient fallback.
- `.venv/bin/pytest packages/teax-simkit/simkit/tests/evaluation/test_f1_arithmetic_fixture.py -q`
  passed: 1 test with zero seal diagnostics.
- A second locked generation at `/tmp/teax-f1-repeat.vyvOwU/package_live` was byte-identical by
  `diff -qr`; both detached worktrees remained clean.
- Provenance records uv 0.10.0, lock hash `b457136b...`, CPython 3.12.11, Jinja2 3.1.6,
  Pydantic 2.12.5, PyYAML 6.0.3, producer hash `e9b2954a...`, environment fingerprint
  `093675c5...`, and executable fingerprint `7b623bf0...`.

**Issues / Resolutions:**
- The initial acceptance stencil assumed a standalone `constraint_catalog.json`; production embeds
  the catalog in `model_contract.json`. The test was corrected to the sealed production layout.
- Resolving the managed interpreter symlink made a valid environment look ambient. Preflight now
  checks the invoked `sys.executable` path without resolving the managed-Python symlink.
- The frozen generator environment intentionally lacks TEAx's pandas dependency. Adding it would
  loosen the lock, so graph/YAML checks remain in the producer and the kept test performs the
  actual TEAx `PipelineGraph` check in the repository test environment.

**Deviations:** No observable-contract or fixture-workflow deviation. TEAx order validation is
split across the dependency-pure producer and kept acceptance test to preserve the frozen lock.

### Phase 4 Completion

**Completed:** 2026-07-18T20:36:07-07:00

**Actual Changes:**
- Added the four-row generated arithmetic matrix through fresh prepared and file-backed evaluators.
  Every row asserts the complete equal record, exact direct native cause/message, no transport
  cause, generated predicate/wrapper traceback frames, and changing authoritative module key.
- Added exact typed tree manifests for absent roots, directories, file hashes, and symlink targets.
  Candidate outputs remain exactly absent; scratch changes only by the byte-identical entry case.
- Added fresh direct executor/context proofs that power and nested failures occur after the expected
  earlier real evaluation channels and before the failed/aggregate channels.
- Excluded generated package self-tests from repository collection via the outer evaluation
  `conftest.py`; the sealed file remains untouched and hashed under its production contract.

**Validation Evidence:**
- Focused matrix passed: 6 tests (four public pairs and two direct later-failure proofs).
- Each public matrix row passed independently; reported keys span all three fixed constraint keys.
- `.venv/bin/pytest packages/teax-simkit/simkit/tests/evaluation -q` passed: 40 tests.
- Manual inspection confirms manifest assertions cover complete trees and direct proofs assert the
  actual TEAx topological order before interpreting channel presence.

**Issues / Resolutions:**
- Recursive evaluation-suite collection discovered the sealed generator's own self-test, which
  cannot import correctly outside its declared package name. The outer suite now ignores generated
  package self-tests as fixture artifacts; no sealed byte was changed.

**Deviations:** None.

### Phase 5 Completion

**Completed:** 2026-07-18T20:38:08-07:00

**Actual Changes:**
- Added cross-backend safe satisfied, safe violated, and already-produced NaN indeterminate cases
  for the new fixture with exact response dictionaries and evidence-output parity.
- Left all existing ToyPlant satisfied, violated, budget-NaN, and output-NaN parity baselines
  unchanged.
- Completed final scoped review and removed transient sealed-package cache directories.

**Validation Evidence:**
- Focused F1 file passed: 9 tests.
- Evaluation suite passed: 43 tests.
- Full teax-simkit suite passed: 277 tests.
- Full repository suite passed: 346 tests.
- `git diff --check` passed. Final source review found no arithmetic guards, public API expansion,
  phase/taxonomy changes, concurrency work, fallback behavior, or unrelated source edits.

**Issues / Resolutions:** None.

**Deviations:** None.

---

**Status progression:** Draft → In Progress → Complete
