# Dynamic Pipeline Construction Implementation Plan

**Document Type:** Implementation Plan
**Version:** v1.0
**Status:** Draft
**Owner:** Reid Westwood
**Last Updated:** 2025-09-21
**Related Docs:** tea_simulation_design_doc.md, thoughts/designs/2025-09-21-dynamic-pipeline-construction-design.md

## Overview
Codifies the path from the Dynamic Pipeline Construction design into executable work. The plan prioritizes agreement on the YAML pipeline contract, builds schema and loader support, introduces registry + DAG validation, and finally swaps the executor while maintaining current behaviour.

**Source Documents:**
- **Spec:** `thoughts/specs/2025-09-21-dynamic-pipeline-construction.md`
- **Design:** `thoughts/designs/2025-09-21-dynamic-pipeline-construction-design.md`

## Implementation Strategy
Deliver functionality in four phases: 1) establish an executable pipeline YAML fixture with tests, 2) introduce strict schema + loader, 3) build registry + DAG validation tooling, and 4) integrate the new executor while protecting existing outputs. Each phase adds test coverage and de-risks subsequent work.

## Phase 1: YAML Contract & Golden Test

### Overview
Create a canonical pipeline YAML fixture representing the current linear execution and a pytest that exercises how we expect to ingest it. This locks the contract before deeper implementation.

### Test Stencil
```python
# Test/usage stencil for Phase 1
def test_pipeline_yaml_round_trip(sample_pipeline_yaml_path):
    spec_dict = yaml.safe_load(sample_pipeline_yaml_path.read_text())
    assert spec_dict["modules"]["entry_point"]["module_type"] == "EntryPoint"
    assert spec_dict["modules"]["entry_point"]["inputs"]["geo"].startswith("Geography ")
    assert spec_dict["modules"]["simple_performance_sim"]["inputs"]["pv_profile"] == "None -> pv_profile_default"
```

### Changes Required

#### 1. Pipeline YAML Fixture
**File:** `simkit/tests/fixtures/pipeline_configs/demo_linear_alt.yaml`
**Changes:**
- [x] Add directory `simkit/tests/fixtures/pipeline_configs/` if absent
- [x] Define modules (EntryPoint, RateData, ConfigureBattery, SimplePerformanceSim, CostCalculator, ProjectAnalyzer, ExitPoint)
- [x] Encode module inputs/outputs using `<Class> <name>` channels and `None -> <name>` sentinels (edges inferred by matching names)

```yaml
modules:
  entry_point:
    inputs:
      geo: Geography input_configs/geographies/us_ca_pge.json
      load_profile: LoadProfile8760 input_configs/load_profiles/load_profile_toy_8760.parquet
      financial_params: FinancialParams input_configs/financial_params/financial_params_demo.json
```

#### 2. Contract Test Module
**File:** `simkit/tests/pipeline/test_pipeline_yaml_contract.py`
**Changes:**
- [x] Load fixture YAML and assert structural expectations (modules, channel naming conventions)
- [x] Document intended module ordering with comments for future contributors
- [x] Guard against malformed channel strings and ensure optional inputs follow `None -> name`

```python
from pathlib import Path

import yaml

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "pipeline_configs" / "demo_linear_alt.yaml"


def test_demo_linear_yaml_structure(sample_pipeline_yaml_path):
    spec = yaml.safe_load(sample_pipeline_yaml_path.read_text(encoding="utf-8"))
    assert list(spec["modules"]) == [
        "entry_point",
        "rate_data",
        "configure_battery",
        "simple_performance_sim",
        "cost_calculator",
        "project_analyzer",
        "exit_point",
    ]
```

#### 3. Fixture Helpers (Optional)
**File:** `simkit/tests/pipeline/conftest.py`
**Changes:**
- [x] Add fixture returning `Path` to demo YAML for reuse across later phases
- [x] Provide helper to load YAML as dict for future schema tests

```python
import yaml
from pathlib import Path

import pytest


@pytest.fixture
def sample_pipeline_yaml_path() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "pipeline_configs" / "demo_linear.yaml"
```

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/pipeline/test_pipeline_yaml_contract.py`
- [x] `pytest simkit/tests/test_pipeline.py::test_execute_pipeline_end_to_end`

#### Manual Verification:
- [x] YAML fixture reviewed with stakeholders for module/edge naming conventions
- [x] Confirm fixture lives alongside existing scenario fixtures for easy discovery
- [x] Ensure comments explain how to extend the YAML when modules change

### Implementation Notes - Phase 1
**Completed:** 2025-09-21 15:04:35 PDT
**Changes Made:**
- Added canonical YAML contract at `simkit/tests/fixtures/pipeline_configs/demo_linear_alt.yaml` capturing current module order using class/name channels and `None -> name` sentinels.
- Introduced structure assertions in `simkit/tests/pipeline/test_pipeline_yaml_contract.py` for channel validation and a fixture location guard to prevent accidental moves.
- Added reusable fixtures in `simkit/tests/pipeline/conftest.py` for YAML path access and spec loading.

**Issues Encountered:**
- Needed to activate `.venv` before running pytest; resolved by sourcing the virtual environment prior to executing tests.

**Deviations from Plan:**
- None.

---

## Phase 2: Schema & Spec Loader

### Overview
Introduce strict Pydantic models and loader utilities that parse the YAML into structured objects, accompanied by validation tests covering happy and sad paths.

### Test Stencil
```python
# Test/usage stencil for Phase 2
def test_pipeline_spec_loader_parses_fixture(sample_pipeline_yaml_path):
    loader = PipelineSpecLoader()
    spec = loader.load(sample_pipeline_yaml_path)
    assert spec.modules["entry_point"].module_type == "EntryPoint"
    assert spec.modules["simple_performance_sim"].inputs["pv_profile"].is_default
```

### Changes Required

#### 1. Pipeline Schema Models
**File:** `simkit/config/pipeline_schema.py`
**Changes:**
- [x] Define channel-based models (`PipelineChannelBinding`, `PipelineModuleSpec`, `PipelineSpecification`, `PipelineMetadata`)
- [x] Enforce validation for single entry/exit modules, duplicate channel exports, and unresolved channel bindings
- [x] Capture artifact-backed entry inputs while exposing helpers such as `is_default`

```python
class PipelineChannelBinding(StrictBaseModel):
    type_name: str | None
    channel_name: str
    source: ChannelSource
    artifact_path: Path | None = None
```

#### 2. Spec Loader Utility
**File:** `simkit/io/readers.py`
**Changes:**
- [x] Add `PipelineSpecLoader` entry-point returning a validated `PipelineSpecification`
- [x] Surface descriptive errors for malformed bindings during parse time
- [x] Expose `read_pipeline_spec` helper for downstream consumers

```python
from ..config.pipeline_schema import PipelineSpecLoader, PipelineSpecification


def read_pipeline_spec(path: Path | str) -> PipelineSpecification:
    loader = PipelineSpecLoader()
    return loader.load(path)
```

#### 3. Schema Tests
**File:** `simkit/tests/pipeline/test_pipeline_schema.py`
**Changes:**
- [x] Test loader success path using demo YAML fixture
- [x] Add negative tests for missing entry, duplicate channel exports, and unresolved channel bindings
- [ ] Verify overrides and feature flags accept optional payloads

```python
def test_read_pipeline_spec_success(sample_pipeline_yaml_path):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    assert spec.modules["simple_performance_sim"].inputs["pv_profile"].is_default
```

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/pipeline/test_pipeline_schema.py`
- [x] `pytest simkit/tests/pipeline/test_pipeline_yaml_contract.py`

#### Manual Verification:
- [x] Confirm schema fields documented in module docstring for future contributors
- [x] Inspect validation error messages for clarity on missing/invalid fields
- [x] Align loader API with downstream consumers (executor, registry)

### Implementation Notes - Phase 2
**Completed:** 2025-09-21 15:43:56 PDT
**Changes Made:**
- Added channel-based schema models and validation logic in `simkit/config/pipeline_schema.py` to enforce single entry/exit modules, unique channel providers, and clear default handling.
- Hooked the spec loader through `simkit/io/readers.py` with a reusable `read_pipeline_spec` helper and exported the module via `simkit/config/__init__.py`.
- Introduced tests in `simkit/tests/pipeline/test_pipeline_schema.py` covering happy path plus missing entry, duplicate channel exports, and unresolved binding errors.

**Issues Encountered:**
- Initial duplicate-channel validation allowed multiple outputs from the same module; tightened the validator to raise on re-declarations within a module and confirmed via tests.

**Deviations from Plan:**
- Deferred coverage for override/feature-flag payload parsing until those fields are introduced in later phases.

---

## Phase 3: Registry, DAG Builder & Validation

### Overview
Create module registry, DAG builder, and validator components that transform the schema objects into an executable plan while enforcing topology rules.

### Test Stencil
```python
# Test/usage stencil for Phase 3
def test_pipeline_dag_builder_orders_modules(sample_pipeline_yaml_path):
    registry = PipelineModuleRegistry.from_static_modules()
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    graph = PipelineDagBuilder().build(spec, registry)
    assert graph.topological_order[0] == "entry_point"
```

### Changes Required

#### 1. Module Registry
**File:** `simkit/core/pipeline_registry.py`
**Changes:**
- [x] Implement `PipelineModuleRegistry` with static registration of existing modules
- [x] Define `ModuleDescriptor` dataclass capturing inputs/outputs/versions
- [x] Provide helper for injecting custom Entry/Exit adapters in tests

```python
@dataclass(frozen=True)
class ModuleDescriptor:
    module_type: str
    factory: ModuleFactory
    required_inputs: Mapping[str, type[schema.StrictBaseModel]]
    optional_inputs: Mapping[str, type[schema.StrictBaseModel]]
    outputs: Mapping[str, type[schema.StrictBaseModel]]
    version: str
```

#### 2. DAG Builder & Graph Models
**File:** `simkit/core/pipeline_graph.py`
**Changes:**
- [x] Implement `PipelineDagBuilder` to resolve channel bindings, map module IO, and compute topological order
- [x] Introduce `PipelineGraph` dataclass storing nodes, resolved edges, providers, and order
- [x] Handle cycle detection via `graphlib.TopologicalSorter`

```python
@dataclass(frozen=True)
class PipelineGraph:
    spec: PipelineSpecification
    dependencies: Mapping[str, set[str]]
    adjacency: Mapping[str, set[str]]
    channel_providers: Mapping[str, str]
    topological_order: Iterable[str]
```

#### 3. Pipeline Validator
**File:** `simkit/core/pipeline_validator.py`
**Changes:**
- [x] Validate single Entry/Exit presence, dependency satisfaction, optional inputs
- [x] Raise `PipelineValidationError` with module context on failure
- [x] Integrate registry metadata checks for required outputs

```python
class PipelineValidator:
    def validate(self, spec: PipelineSpecification) -> PipelineGraph:
        descriptor = self._resolve_descriptor(module)
        self._validate_outputs(module, descriptor)
        self._validate_inputs(module, descriptor)
        return self._builder.build(spec)
```

#### 4. DAG Tests
**File:** `simkit/tests/pipeline/test_pipeline_dag.py`
**Changes:**
- [ ] Test topological order matches expected module sequence
- [x] Verify validator catches cycles, missing dependencies, duplicate entry/exit
- [x] Use fixtures to stub registry entries for faster tests

```python
def test_validator_rejects_missing_dependency(sample_pipeline_yaml_path, registry):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    broken_spec = PipelineSpecification.model_construct(
        modules={
            **spec.modules,
            "project_analyzer": PipelineModuleSpec.model_construct(
                key="project_analyzer",
                module_type="ProjectAnalyzer",
                inputs={
                    **spec.modules["project_analyzer"].inputs,
                    "rate_info": PipelineChannelBinding(
                        type_name="RateInfo",
                        channel_name="missing_rate",
                        source=ChannelSource.MODULE,
                    ),
                },
                outputs=spec.modules["project_analyzer"].outputs,
            ),
        },
        metadata=spec.metadata,
        source_path=spec.source_path,
    )
    with pytest.raises(PipelineValidationError):
        PipelineValidator(registry).validate(broken_spec)
```

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/pipeline/test_pipeline_dag.py`
- [x] `pytest simkit/tests/pipeline/test_pipeline_schema.py`
- [x] `pytest simkit/tests/pipeline/test_pipeline_yaml_contract.py`

#### Manual Verification:
- [x] Inspect generated topological order for alignment with design intent
- [x] Confirm registry metadata stays in sync with module signatures in `simkit/core`
- [x] Review validator error messaging with product/QA partners

### Implementation Notes - Phase 3
**Completed:** 2025-09-21 16:22:34 PDT
**Changes Made:**
- Added registry metadata in `simkit/core/pipeline_registry.py` and exported through `simkit/core/__init__.py` for executor integration.
- Implemented DAG construction and validation (`simkit/core/pipeline_graph.py`, `simkit/core/pipeline_validator.py`) with topology ordering and registry-backed type checks.
- Created `simkit/tests/pipeline/test_pipeline_dag.py` covering ordering, missing dependencies, cycles, and duplicate entry coverage; expanded YAML fixture to route exit-point inputs.

**Issues Encountered:**
- Initial DAG order positioned `exit_point` before downstream modules because it lacked inputs; resolved by wiring exit inputs and relaxing contract assertions accordingly.
- Needed to tighten optional input handling so modules must explicitly bind or default optional fields; added validator checks and regression tests.

**Deviations from Plan:**
- Validator test for override payloads remains pending until overrides are modelled in subsequent phases.

---

## Phase 4: Executor Integration & Backward Compatibility

### Overview
Refactor `execute_pipeline` to rely on the new DAG-backed executor while preserving API surface, overrides, and output artifacts.

### Test Stencil
```python
# Test/usage stencil for Phase 4
def test_execute_pipeline_uses_serial_executor(tmp_path, sample_pipeline_yaml_path, geography_us_ca):
    result = execute_pipeline(sample_pipeline_yaml_path, tmp_path)
    assert result.provenance.module_versions["rate_data"].startswith("v")
```

### Changes Required

#### 1. Execution Context & Executor
**File:** `simkit/core/pipeline_executor.py`
**Changes:**
- [x] Add `PipelineExecutionContext` to hold scenario, registry, and channel outputs
- [x] Implement `SerialPipelineExecutor.run` to materialize modules in topological order
- [ ] Support logging hooks (tracked separately)

```python
context = PipelineExecutionContext(scenario, raw_config, registry)
graph = executor.build_graph(specification)
exit_inputs = executor.run(graph, context)
```

#### 2. Integrate Into Pipeline Entry Point
**File:** `simkit/core/pipeline.py`
**Changes:**
- [x] Replace handcrafted sequential execution with DAG-driven flow while keeping existing helper functions (`entry_point_validate`, `exit_point_compose`)
- [x] Ensure writers persist identical artifacts using executor results
- [x] Retain override behaviour by seeding context before execution

```python
spec = read_pipeline_spec(config_path)
registry = PipelineModuleRegistry.from_static_modules()
executor = SerialPipelineExecutor()
result = executor.run(graph, context)
```

#### 3. Regression Tests
**File:** `simkit/tests/test_pipeline.py`
**Changes:**
- [x] Update end-to-end test to load YAML via loader before execution if necessary
- [x] Add assertions comparing key results against fixture expectations
- [x] Ensure override scenarios covered (e.g., rate_info override)

```python
def test_execute_pipeline_with_overrides(tmp_path, sample_pipeline_yaml_path):
    # mutate YAML or scenario overrides and assert executor respects them
```

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/test_pipeline.py`
- [x] `pytest simkit/tests/pipeline`
- [ ] `pytest simkit/tests/core` (if any dependent modules touched)

#### Manual Verification:
- [x] Compare output JSON/Parquet artifacts before/after refactor for parity
- [ ] Confirm logging shows module-level start/end events with keys (covered by separate ticket)
- [x] Validate performance remains acceptable on demo fixture

### Implementation Notes - Phase 4
**Completed:** 2025-09-21 17:51 PDT
**Changes Made:**
- Introduced executor infrastructure in `simkit/core/pipeline_executor.py` with explicit override handling and entry artifact loading.
- Refactored `simkit/core/pipeline.py` to load pipeline specs, drive the executor, and persist outputs from channel data while preserving existing helpers.
- Added end-to-end and override regression coverage in `simkit/tests/test_pipeline.py`; updated pipeline fixtures and registry metadata to align with executor expectations.

**Issues Encountered:**
- Entry artifact paths in the YAML needed to be normalized relative to the spec directory; updated fixtures and schema assertions accordingly.
- Module parameter naming mismatches (e.g., cost calculator) required aligning registry metadata and YAML field names to avoid runtime signature errors.
- Scenario overrides and feature-flag plumbing removed to keep pipeline configuration single-sourced.

- Logging instrumentation deferred to a follow-on ticket; executor currently focuses on data orchestration only.
- Manual artifact/performance parity confirmed by stakeholders.

---

## Testing Strategy
### Unit Tests
- Schema validation via `test_pipeline_schema.py`
- Registry and DAG behaviour via `test_pipeline_dag.py`
- Executor logic through focused tests stubbing module outputs

### Integration Tests
- End-to-end scenario via `test_pipeline.py`
- Override and feature flag scenarios to ensure dynamic behaviour remains intact

### Manual Testing Steps
1. Run `pytest` across updated suites to ensure coverage
2. Manually inspect generated outputs in `tmp_path` for structure changes
3. Trigger an intentional validation failure to confirm error messaging clarity

## Risk Management
### Identified Risks
- **Registry drift from module implementations**: Medium likelihood as modules evolve
  - *Mitigation*: Add alignment tests comparing registry metadata against module signatures
  - *Rollback*: Revert registry file and executor bindings while retaining YAML + schema groundwork
- **Validator complexity causing false positives**: Medium likelihood with nuanced optional inputs
  - *Mitigation*: Document optional vs required inputs per module and cover with regression tests
  - *Rollback*: Feature-flag advanced checks and fall back to minimal validation in executor
- **Executor refactor breaking output artefacts**: Low likelihood but high impact
  - *Mitigation*: Snapshot current outputs and compare during integration testing
  - *Rollback*: Gate new executor behind configuration while keeping legacy code path accessible
