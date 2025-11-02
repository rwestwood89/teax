# Remove Scenario Demo Implementation Plan

**Document Type:** Implementation Plan
**Version:** v1.0
**Status:** Complete
**Owner:** Reid W
**Last Updated:** 2025-09-22 10:32:53 PDT
**Related Docs:** tea_simulation_design_doc.md, thoughts/specs/2025-09-22-remove-scenario-demo.md, thoughts/designs/2025-09-21-dynamic-pipeline-construction-design.md
**Current Branch Name:** dev
**Current Commit:** 0685c039b87e06d72ef9af6927ce034b1f2e6cea

## Overview
Eliminate the legacy `ScenarioDemo` configuration flow so pipeline executions source all runtime inputs and provenance metadata directly from the pipeline specification. Start by introducing a constrained `metadata` block in the golden spec, then refactor the executor context and provenance wiring, and finally align tests, fixtures, and documentation.

**Source Documents:**
- **Spec:** `thoughts/specs/2025-09-22-remove-scenario-demo.md`
- **Design:** `thoughts/designs/2025-09-21-dynamic-pipeline-construction-design.md`

## Implementation Strategy
We will stage the work across three phases. Phase 1 updates the specification schema and fixtures to contain a minimal metadata block (`run_description`, `output_folder`). Phase 2 removes `ScenarioDemo`, reworks the executor context to rely on spec metadata, and updates provenance hashing. Phase 3 cleans up fixtures/tests, ensures notebooks/CLI paths no longer consume scenario YAML, and refreshes the design document to v2.0.

## Phase 1: Introduce Minimal Spec Metadata

### Overview
Add the `metadata` block with the two supported fields to the golden pipeline spec and update loaders/tests to validate the new contract without expanding metadata scope beyond the spec requirement.

### Test Stencil
```python
# Test/usage stencil for Phase 1
def test_pipeline_spec_includes_metadata(sample_pipeline_yaml_path):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    assert spec.metadata.run_description == "Demo linear pipeline for regression coverage"
    assert spec.metadata.output_folder == "pipeline_result_bundle"
```

### Changes Required

#### 1. Golden Pipeline Spec Fixture
**File:** `simkit/tests/fixtures/pipeline_configs/demo_linear_alt.yaml`
**Changes:**
- [x] Add a top-level `metadata` block with `run_description` and `output_folder` values.
- [x] Ensure YAML comments remain accurate after the insertion.

```yaml
metadata:
  run_description: Demo linear pipeline for regression coverage
  output_folder: pipeline_result_bundle
modules:
  entry_point:
    module_type: EntryPoint
```

#### 2. Spec Schema Models
**File:** `simkit/config/pipeline_schema.py`
**Changes:**
- [x] Update `PipelineMetadata` to declare `run_description: str | None` and `output_folder: str | None` as the only supported fields.
- [x] Adjust `PipelineSpecification` validation to accept the metadata block while ensuring it defaults to `None` when the block is absent.
- [x] Add validation that `output_folder`, when provided, is non-empty.

#### 3. Spec Loader Helpers
**File:** `simkit/io/readers.py`
**Changes:**
- [x] Confirm `read_pipeline_spec` returns models with populated metadata; no behavioural change expected, but add docstring note about metadata support if needed.

#### 4. Schema Tests
**File:** `simkit/tests/pipeline/test_pipeline_schema.py`
**Changes:**
- [x] Extend `test_read_pipeline_spec_success` to assert metadata values for the golden spec.
- [x] Add a new negative test to ensure unexpected metadata keys raise a validation error.
- [x] Update fixtures/helpers (`sample_pipeline_spec`) to default-inject metadata block where appropriate.

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/pipeline/test_pipeline_schema.py`
- [x] `pytest simkit/tests/pipeline/test_pipeline_dag.py`

#### Manual Verification:
- [x] Confirm metadata fields appear in `PipelineSpecification` objects when loading the golden spec via an interactive shell.
- [x] Inspect the YAML fixture to ensure formatting remains consistent with repository standards.
- [x] Verify no other specs break by running `rg` for `metadata:` to audit usages.

## Implementation Notes - Phase 1
**Completed:** 2025-09-22 16:43:57 UTC
**Changes Made:**
- Added a metadata block with demo defaults to `simkit/tests/fixtures/pipeline_configs/demo_linear_alt.yaml`.
- Restricted `PipelineMetadata` fields and enforced non-empty output folders in `simkit/config/pipeline_schema.py`; documented metadata support in `simkit/io/readers.py`.
- Updated schema fixtures/tests in `simkit/tests/pipeline/` to assert metadata values, cover error cases, and default metadata injection in `conftest.py`.

**Issues Encountered:**
- None

**Deviations from Plan:**
- None

---

## Phase 2: Remove ScenarioDemo Dependency

### Overview
Refactor the pipeline entry/exit flow so executor state derives solely from the pipeline specification and its metadata. Remove feature flag plumbing, scenario overrides, and dependent schema structures, replacing them with spec-driven provenance.

### Test Stencil
```python
# Test/usage stencil for Phase 2
def test_execute_pipeline_uses_spec_metadata(tmp_path, demo_spec_path):
    result = execute_pipeline(demo_spec_path, tmp_path)
    assert result.provenance.notes == "Demo linear pipeline for regression coverage"
    assert result.provenance.output_folder == "pipeline_result_bundle"
```

### Changes Required

#### 1. Entry Point Validation
**File:** `simkit/core/pipeline.py`
**Changes:**
- [x] Replace `entry_point_validate` to return a normalized spec path and optional metadata without constructing `ScenarioDemo`.
- [x] Remove geography/load validation that depended on scenario YAML; rely on entry module artifacts instead.
- [x] Delete feature flag merging and override handling logic.

#### 2. Execution Context
**File:** `simkit/core/pipeline_executor.py`
**Changes:**
- [x] Update `PipelineExecutionContext` to store spec metadata and channel cache only; drop `scenario`, overrides, and flag references.
- [x] Simplify entry execution to seed channels from spec artifacts without applying overrides.
- [x] Ensure module factories are invoked without flag arguments.

#### 3. Pipeline Result Composition
**File:** `simkit/core/pipeline.py`
**Changes:**
- [x] Update `exit_point_compose` to use spec metadata for provenance (e.g., notes from `run_description`).
- [x] Recompute config hash from the pipeline spec (and metadata) rather than scenario YAML.
- [x] Adjust `PipelineResult` to drop `scenario` field and replace with explicit metadata references.

#### 4. Schema Revisions
**File:** `simkit/config/schema.py`
**Changes:**
- [x] Remove the `ScenarioDemo` model and adapt `PipelineResult`/`Provenance` to reference spec metadata fields instead.
- [x] Introduce any new lightweight metadata dataclass required for provenance.
- [x] Update defaults where feature flags were previously required.

#### 5. Registry & Module Constructors
**File:** `simkit/core/pipeline_registry.py`
**Changes:**
- [x] Adjust `ModuleFactory` signatures to omit feature flag dictionaries.
- [x] Update module factory lambdas and module constructors as needed.

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/test_pipeline.py`
- [x] `pytest simkit/tests/pipeline/test_pipeline_schema.py`
- [x] `pytest simkit/tests/pipeline/test_pipeline_dag.py`

#### Manual Verification:
- [x] Run an interactive execution (CLI or shell) pointing at the spec to confirm outputs match baseline expectations.
- [x] Inspect generated provenance JSON to verify metadata fields populate correctly.
- [x] Review diff to ensure all references to `ScenarioDemo` and feature flags are removed.

## Implementation Notes - Phase 2
**Completed:** 2025-09-22 17:12:11 UTC
**Changes Made:**
- Reworked `simkit/core/pipeline.py` to load specifications directly, compose provenance from spec metadata, and emit pipeline metadata snapshots in results.
- Simplified `PipelineExecutionContext`, removed override plumbing, and updated module factories plus constructors to drop feature flag arguments.
- Revised schema models (`simkit/config/schema.py`) and executor tests (`simkit/tests/test_pipeline.py`, `simkit/tests/pipeline/test_pipeline_dag.py`) to exercise metadata-driven provenance.

**Issues Encountered:**
- None

**Deviations from Plan:**
- None

---

## Phase 3: Tests, Fixtures, and Design Alignment

### Overview
Clean up remaining fixtures/tests/notebooks to reflect the new spec-only configuration path and formalize the design doc update capturing these changes.

### Test Stencil
```python
# Test/usage stencil for Phase 3
def test_fixture_loads_direct_spec(tmp_path, golden_spec_path):
    result = execute_pipeline(golden_spec_path, tmp_path)
    assert tmp_path.joinpath("pipeline_result.json").exists()
```

### Changes Required

#### 1. Test Fixtures & Helpers
**Files:** `simkit/tests/test_pipeline.py`, `simkit/tests/fixtures/`
**Changes:**
- [x] Remove scenario YAML fixtures and update tests to reference spec paths directly.
- [x] Ensure temporary output directories honor `output_folder` metadata if used.
- [x] Update shared fixtures to return spec metadata where callers previously expected `ScenarioDemo`.

#### 2. Notebooks & CLI Utilities
**Files:** `notebooks/manual_mode_demo.ipynb`, any CLI scripts referencing scenario configs
**Changes:**
- [x] Update documentation snippets to reference spec metadata instead of scenario YAML.
- [x] Validate notebook cells still execute with the new entry flow.

#### 3. Design Document Update
**File:** `thoughts/designs/2025-09-21-dynamic-pipeline-construction-design.md`
**Changes:**
- [x] Bump to Version v2.0 and document the removal of scenario YAML, overrides, and feature flag plumbing.
- [x] Add a section describing metadata-driven provenance.

#### 4. Thought Artifacts & Cleanup
**Files:** Repository-wide search
**Changes:**
- [x] Run `rg` for `ScenarioDemo`, `feature_flags`, and `pipeline_scenario.yaml` to confirm all references are retired or intentionally left.
- [x] Delete obsolete fixtures (`simkit/tests/fixtures/pipeline_scenario.yaml`).

### Success Criteria
#### Automated Verification:
- [x] `pytest`
- [x] `pytest simkit/tests/test_pipeline.py -k end_to_end`

#### Manual Verification:
- [x] Execute notebook logic via script to ensure happy-path output matches expectations.
- [x] Confirm documentation and design doc cross-reference the correct spec paths.
- [x] Validate that `git status` shows only intentional changes before PR.

## Implementation Notes - Phase 3
**Completed:** 2025-09-22 17:32:44 UTC
**Changes Made:**
- Removed scenario fixtures, updated pipeline tests to operate on spec metadata, and deleted obsolete YAML (`simkit/tests/test_pipeline.py`, `simkit/tests/fixtures`).
- Reworked the manual mode notebook to load entry artifacts directly from the spec and compose provenance without feature flags (`notebooks/manual_mode_demo.ipynb`).
- Promoted the design document to v2.0, documenting metadata-driven provenance and the absence of overrides/feature flags (`thoughts/designs/2025-09-21-dynamic-pipeline-construction-design.md`).

**Issues Encountered:**
- Notebook execution tooling (`nbformat`) was unavailable; verified notebook logic via an equivalent Python script instead.

**Deviations from Plan:**
- None

---

## Testing Strategy
### Unit Tests
- Cover `PipelineMetadata` parsing, ensuring only supported keys are accepted.
- Validate executor context behaviour without overrides or feature flags.

### Integration Tests
- Re-run end-to-end pipeline execution via spec-only inputs, asserting provenance metadata.
- Ensure DAG validation still passes with metadata present and scenario removal.

### Manual Testing Steps
1. Load the golden spec in a Python REPL to inspect metadata and channels.
2. Run pipeline execution against the golden spec and inspect output artifacts.
3. Open the updated design document to confirm narrative alignment.

## Risk Management
### Identified Risks
- **Override removal backlash**: Contributors might miss quick tweak path.
  - *Mitigation*: Document duplication workflow or plan follow-up tooling.
  - *Rollback*: Reintroduce a trimmed override mechanism using spec templating if necessary.
- **Config hash drift**: Changing hash inputs could break provenance comparisons.
  - *Mitigation*: Define normalization rules and add regression tests.
  - *Rollback*: Keep legacy hash calculation behind a flag if gaps emerge.

### Dependencies
- Decision on provenance hash inputs and formatting.
- Confirmation from stakeholders that feature flags can be removed entirely.

## References
- Original spec: `thoughts/specs/2025-09-22-remove-scenario-demo.md`
- Implementation design: `thoughts/designs/2025-09-21-dynamic-pipeline-construction-design.md`
- Related research: `tea_simulation_design_doc.md`
- Similar implementations: `simkit/tests/fixtures/pipeline_configs/demo_linear_alt.yaml`, `simkit/core/pipeline.py`
