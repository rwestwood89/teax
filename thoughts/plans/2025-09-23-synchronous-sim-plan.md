# Synchronous Simulation Module Implementation Plan

**Document Type:** Implementation Plan
**Version:** v1.0
**Status:** Complete
**Owner:** Reid W
**Last Updated:** 2025-09-23 09:55:06 PDT
**Related Docs:** `thoughts/specs/2025-09-23-synchronous-sim.md`, `thoughts/design/2025-09-23-synchronous-sim-design.md`, `tea_simulation_design_doc.md`
**Current Branch Name:** synchronous_sim
**Current Commit:** dc2c35a428c2a6aa6abe9f92e26d7679f198a317

## Overview
Plan to introduce the synchronous simulation module that bridges forecast, guidance, and MATLAB-backed dynamics inside the existing async pipeline. Work proceeds test-first by defining an end-to-end pipeline scenario with stubbed dynamics, then layering schema models, module orchestration, and integration wiring until the new module is fully registered and exercised alongside existing components.

**Source Documents:**
- **Spec:** `thoughts/specs/2025-09-23-synchronous-sim.md`
- **Design:** `thoughts/design/2025-09-23-synchronous-sim-design.md`

## Implementation Strategy
1. Lock down desired usage by authoring an integration test, pipeline spec, and supporting fixtures that describe the synchronous sim workflow.
2. Implement the shared schema surface area (time-grid, payload models) used by all subcomponents.
3. Build the synchronous module, forecast/guidance components, and dynamics bridges that satisfy the schema and test contract.
4. Register the module with the pipeline registry, extend output routing, and ensure automated coverage passes with both happy-path and failure scenarios.

## Phase 0: Define E2E Scenario (Test-First)

### Overview
Create the integration test, pipeline YAML, and fixture payloads that describe how the synchronous sim module is invoked with stubbed dynamics.

### Test Stencil
```python
# Test/usage stencil for Phase 0 - defines desired pipeline behavior
from pathlib import Path
from simkit.core.pipeline import execute_pipeline

def test_synchronous_sim_stubbed_happy_path(tmp_path, geography_us_ca):
    spec_path = Path(__file__).parent / "fixtures" / "pipeline_configs" / "synchronous_sim_stubbed.yaml"
    result = execute_pipeline(spec_path, tmp_path / "outputs")
    sync_output = result.outputs["synchronous_sim"]
    assert sync_output.telemetry.frames[0].inner_times[0].tzinfo is not None
    assert sync_output.guidances.series[0].setpoint_kw == 0.0
```

### Changes Required

#### 1. Integration Test Skeleton
**File:** `simkit/tests/test_pipeline_synchronous_sim.py`
**Changes:**
- [x] Add `test_synchronous_sim_stubbed_happy_path` asserting telemetry/guidance/forecast structures returned by the pipeline with stub dynamics.
- [x] Add `test_synchronous_sim_stubbed_failure_annotation` expecting annotated `ValueError` when stub bridge triggers a configured failure.
- [x] Mark new tests with `pytest.mark.xfail(strict=True)` until module implementation (phases 1-3) is completed.

```python
@pytest.mark.xfail(strict=True, reason="SynchronousSim module not yet implemented")
def test_synchronous_sim_stubbed_happy_path(...):
    ...
```

#### 2. Pipeline Spec & Pipeline Fixtures
**File:** `simkit/tests/fixtures/pipeline_configs/synchronous_sim_stubbed.yaml`
**Changes:**
- [x] Define EntryPoint bindings for time grid, initial state, price trajectory, and component configs stored under `fixtures/synchronous_sim/`.
- [x] Add `SynchronousSim` module block referencing new channels and route outputs to ExitPoint.
- [x] Configure ExitPoint to persist `forecasts.json`, `guidances.json`, and `telemetry.parquet` via the new channel type names.

```yaml
modules:
  Entry:
    module_type: EntryPoint
    outputs:
      time_grid:
        channel_name: synchronous.time_grid
        source: entry
        artifact_path: ../synchronous_sim/time_grid.json
  SynchronousSim:
    module_type: SynchronousSim
    inputs:
      time_grid:
        channel_name: synchronous.time_grid
        source: module
```

#### 3. Scenario Fixture Payloads
**File:** `simkit/tests/fixtures/synchronous_sim/<*.json>`
**Changes:**
- [x] Create `time_grid.json` describing a 6-hour run with 1H outer steps and 5-minute inner dynamics cadence.
- [x] Create `initial_state.json` capturing battery SOC/power consistent with schema bounds.
- [x] Create `actual_pricing.json` (or `.parquet`) aligned to the outer grid with currency metadata.
- [x] Create `forecast_config.json`, `guidance_config.json`, and `dynamic_sim_config.json` referencing stub behaviors and deterministic seeds.

```json
{
  "outer_steps": [
    {"index": 0, "start": "2025-01-01T00:00:00Z", "duration": "1H"}
  ],
  "inner_loops": [
    {"component": "dynamics", "step": "5T", "samples_per_outer": 12}
  ]
}
```

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/test_pipeline_synchronous_sim.py::test_synchronous_sim_stubbed_happy_path` xfails with reason "SynchronousSim module not yet implemented".
- [x] `pytest simkit/tests/test_pipeline_synchronous_sim.py::test_synchronous_sim_stubbed_failure_annotation` xfails with the same reason.

#### Manual Verification:
- [x] Opening `simkit/tests/fixtures/pipeline_configs/synchronous_sim_stubbed.yaml` shows relative paths only and no absolute paths.
- [x] Fixture JSON/Parquet files deserialize via `Path(...).read_text()` without schema errors.
- [x] Pipeline YAML references match fixture filenames exactly.

## Implementation Notes - Phase 0
**Completed:** 2025-09-23 17:20:09Z
**Changes Made:**
- Added synchronous sim integration test skeleton with xfail guard in `simkit/tests/test_pipeline_synchronous_sim.py` covering happy-path and failure-path expectations.
- Created synchronous sim pipeline spec and stub payload fixtures under `simkit/tests/fixtures/` for time grid, pricing, configs, and telemetry routing.
- Added a dedicated `dynamic_sim_config_failure.json` fixture to support the annotated failure scenario while keeping the base spec focused on the happy path.
**Issues Encountered:**
- None.
**Deviations from Plan:**
- Introduced an explicit failure-config fixture to toggle stub dynamics errors without mutating the shared pipeline spec.
**Metadata Snapshot:**
- Current Date/Time (TZ): 2025-09-23 10:21:20 PDT
- Current Git Commit Hash: a25c9afdc0b598f8197558da980db1259b9fca60
- Current Branch Name: synchronous_sim
- Active Git Username: Reid W
- Repository Name: pyrondo2-demo
- Timestamp For Filename: 2025-09-23_10-21-20

---

## Phase 1: Schema & Time-Grid Foundations

### Overview
Implement shared schema models and helpers that validate time grids, pricing trajectories, component configs, and telemetry outputs.

### Test Stencil
```python
# Test/usage stencil for Phase 1 - schema validation examples
def test_sync_time_grid_round_trip():
    grid = schema.SyncTimeGrid(**example_payload())
    assert grid.outer_steps[0].duration.to_pandas_freq() == "1H"
    assert grid.inner_loops[0].samples_per_outer == 12

def test_price_trajectory_window_alignment(price_trajectory_stub):
    window = price_trajectory_stub.window("2H")
    assert len(window.values) == 24
```

### Changes Required

#### 1. Time Models & Utilities
**File:** `simkit/config/schema.py`
**Changes:**
- [x] Add `TimeSpan`, `SyncOuterStep`, `InnerLoopConfig`, and `SyncTimeGrid` models with validators for unit normalization and duration alignment.
- [x] Introduce `SyncOuterStep.to_timespan()` and cross-field validation ensuring contiguous outer steps.
- [x] Export new models via `__all__` for downstream imports.

```python
class TimeSpan(StrictBaseModel):
    raw: str | float | datetime.timedelta
    unit: Literal["seconds", "minutes", "hours", "days"] | None = None

    @computed_field
    def pandas_offset(self) -> pd.Timedelta:
        return _normalize_timespan(self.raw, self.unit)
```

#### 2. Component Payload Models
**File:** `simkit/config/schema.py`
**Changes:**
- [x] Define `BatteryState`, `MockForecastConfig`, `MockForecastPoint`, `MockForecastSeries`, `GuidanceConfig`, `SyncGuidance`, `SyncGuidanceSeries`, `DynamicSimConfig`, `DynamicsInitInput`, `DynamicsStepInput`, `SyncTelemetryFrame`, and `SyncTelemetrySeries`.
- [x] Ensure each model carries units/currency fields and `model_validator` checks for index alignment per outer step.
- [x] Add `SyncSimOutputs` bundling the three result series with a validator enforcing shared outer step indices.

```python
class SyncSimOutputs(StrictBaseModel):
    forecasts: MockForecastSeries
    guidances: SyncGuidanceSeries
    telemetry: SyncTelemetrySeries

    @model_validator(mode="after")
    def validate_alignment(self) -> "SyncSimOutputs":
        ensure_outer_indices_match(self.forecasts, self.guidances, self.telemetry)
        return self
```

#### 3. Time Helpers Module
**File:** `simkit/config/time_utils.py`
**Changes:**
- [x] Create helper functions for normalizing `TimeSpan` inputs, building pandas indices for outer/inner loops, and computing `samples_per_outer`.
- [x] Add unit tests referencing these helpers (see Phase 3).
- [x] Re-export helpers in `simkit/config/__init__.py` if public usage is required.

```python
def build_inner_index(outer_step: SyncOuterStep, config: InnerLoopConfig) -> pd.DatetimeIndex:
    start = outer_step.start
    freq = config.step.to_pandas_freq()
    periods = config.samples_per_outer
    return pd.date_range(start=start, periods=periods, freq=freq, tz=start.tzinfo)
```

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/config/test_sync_schema.py::test_timespan_normalization` passes with timezone-aware assertions.
- [x] `pytest simkit/tests/config/test_sync_schema.py::test_sync_sim_outputs_alignment` passes using stub payloads.
- [x] `pytest simkit/tests/config/test_sync_schema.py` (module) passes in under 1s locally.

#### Manual Verification:
- [x] Inspecting `simkit/config/schema.py` confirms new models are grouped under clearly commented sections (Time, Pricing, Forecast, Guidance, Dynamics, Outputs).
- [x] Generated documentation (if any) lists new models without `TODO` placeholders.
- [x] `python -m pip install -e .[dev]` followed by `python -c "from simkit.config import schema"` executes without import errors.

## Implementation Notes - Phase 1
**Completed:** 2025-09-23 17:38:06Z
**Changes Made:**
- Implemented synchronous time-grid primitives and validation helpers in `simkit/config/schema.py`, including `TimeSpan`, `SyncOuterStep`, `InnerLoopConfig`, and `SyncTimeGrid`.
- Added component payload models and alignment guardrails for forecasts, guidances, dynamics, and telemetry outputs, enabling `SyncSimOutputs` validation.
- Introduced `simkit/config/time_utils.py` with normalization and inner-index builders, re-exported via `simkit/config/__init__.py`, and created `simkit/tests/config/test_sync_schema.py` to exercise the new schema.
- Updated synchronous simulation fixtures to use structured `TimeSpan` objects so EntryPoint bindings map cleanly onto the new validators.
- Unified `PriceTrajectory` and `PriceTrajectoryWindow` handling so window slices reuse the base schema while preserving an explicit subclass for per-step spans.
**Issues Encountered:**
- Pandas frequency helpers required normalization away from deprecated uppercase tokens; handled by sanitizing input strings before conversion.
**Deviations from Plan:**
- None.
**Metadata Snapshot:**
- Current Date/Time (TZ): 2025-09-23 10:38:11 PDT
- Current Git Commit Hash: 38ab1c006e3026e8e9e5f00b4549370910a189a8
- Current Branch Name: synchronous_sim
- Active Git Username: Reid W
- Repository Name: pyrondo2-demo
- Timestamp For Filename: 2025-09-23_10-38-11

---

## Phase 2: Component Orchestration

### Overview
Implement the synchronous module plus forecast, guidance, and dynamics bridge logic that leverages the new schema.

### Test Stencil
```python
# Test/usage stencil for Phase 2 - component-level coverage
def test_synchronous_module_runs_stub_components(stub_inputs):
    module = SynchronousSimModule(dynamics_override=StubDynamicsBridge())
    result = module.run(**stub_inputs)
    assert len(result.data.telemetry.frames) == len(stub_inputs["time_grid"].outer_steps)
    assert result.data.guidances.series[0].metadata.component == "guidance"

def test_dynamics_bridge_failure_annotation(stub_inputs):
    bridge = StubDynamicsBridge(fail_at_outer_step=2)
    with pytest.raises(ValueError) as exc:
        SynchronousSimModule(dynamics_override=bridge).run(**stub_inputs)
    assert "[component=dynamics]" in str(exc.value)
```

### Changes Required

#### 1. Synchronous Module Implementation
**File:** `simkit/core/synchronous_sim/module.py`
**Changes:**
- [x] Implement `SynchronousSimModule` subclassing `ModuleBase`, wiring validation, component initialization, and loop orchestration.
- [x] Provide `_build_inputs` helper that coerces mappings to schema models using Phase 1 types.
- [x] Annotate errors via `_wrap_with_context` helper adding `[component=...]` and `[timestamp=...]` metadata.

```python
class SynchronousSimModule(ModuleBase[SynchronousSimInputs, schema.SyncSimOutputs]):
    name = "synchronous_sim"

    def run(self, **kwargs) -> ModuleResult[schema.SyncSimOutputs]:
        inputs = self.validate_and_fill_default(**kwargs)
        outputs = self._execute_loop(inputs)
        return ModuleResult(outputs)
```

#### 2. Forecast & Guidance Components
**File:** `simkit/core/synchronous_sim/forecast.py`
**Changes:**
- [x] Implement `MockForecastComponent.initialize` and `step` producing deterministic noise series using `numpy.random.Generator` seeded from config.
- [x] Store history and include units/currency metadata on outputs.
- [x] Add matching guidance heuristic in `guidance.py` that respects SOC bounds and ramp constraints from config.

```python
class MockForecastComponent:
    def step(self, payload: schema.MockForecastStepInput) -> schema.MockForecastPoint:
        window = payload.price_window
        prices = np.array(window.values)
        noise = self._rng.normal(0.0, self._config.noise_std_dev, size=len(prices))
        forecast = prices + noise
        return schema.MockForecastPoint(...)
```

#### 3. Dynamics Bridges
**File:** `simkit/core/synchronous_sim/dynamics.py`
**Changes:**
- [x] Define `DynamicsBridge` protocol with `initialize` and `step` signatures.
- [ ] *(Removed)* Implement `MatlabDynamicsBridge` with lazy `matlab.engine` import, Simulink model loading, and telemetry translation.
- [x] Implement `StubDynamicsBridge` emitting deterministic telemetry and configurable failure injection for tests.

```python
class StubDynamicsBridge(DynamicsBridge):
    def step(self, payload: schema.DynamicsStepInput) -> schema.SyncTelemetryFrame:
        if self._fail_at == payload.outer_step.index:
            raise RuntimeError("stub failure")
        inner_index = build_inner_index(payload.outer_step, payload.inner_loop)
        return schema.SyncTelemetryFrame(...)
```

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/pipeline_modules/test_synchronous_sim.py::test_module_loop_happy_path` passes using stub dynamics.
- [x] `pytest simkit/tests/pipeline_modules/test_synchronous_sim.py::test_module_annotates_failures` passes recording component metadata.
- [ ] `pytest simkit/tests/test_pipeline_synchronous_sim.py::test_synchronous_sim_stubbed_happy_path` now passes (xfail removed).

#### Manual Verification:
- [ ] Running `python -m simkit.core.synchronous_sim.module --dry-run` (if CLI harness added) produces expected stub output summary.
- [x] Reviewing `simkit/core/synchronous_sim/dynamics.py` confirms only the stub bridge is active and raises informative errors if non-stub bridges are requested.
- [x] Code comments remain succinct and only describe non-obvious logic.

## Implementation Notes - Phase 2
**Completed:** 2025-09-23 22:44:27Z
**Changes Made:**
- Implemented `SynchronousSimModule` orchestration with explicit coercion helpers and contextual error reporting in `simkit/core/synchronous_sim/module.py`.
- Added forecast, guidance, and dynamics components (`forecast.py`, `guidance.py`, `dynamics.py`) plus package exports and deterministic stub bridge behaviour.
- Introduced module-level tests in `simkit/tests/pipeline_modules/test_synchronous_sim.py` covering happy-path telemetry and annotated failure handling.
**Issues Encountered:**
- None.
**Deviations from Plan:**
- Removed the `MatlabDynamicsBridge` requirement; synchronous simulation currently supports the stub bridge exclusively per updated scope agreement.
- Pipeline integration tests remain `xfail` because registry/output wiring (Phase 3 scope) is not yet implemented.
**Metadata Snapshot:**
- Current Date/Time (TZ): 2025-09-23 15:44:27 PDT
- Current Git Commit Hash: 49b0ff40a626d5a5ce41402f22c10d226d6a1253
- Current Branch Name: synchronous_sim
- Active Git Username: Reid W
- Repository Name: pyrondo2-demo
- Timestamp For Filename: 2025-09-23_15-44-27

---

## Phase 3: Pipeline Integration & Test Coverage

### Overview
Register the new module with the pipeline, extend output routing/writers, and finalize automated coverage across unit and integration layers.

### Test Stencil
```python
# Test/usage stencil for Phase 3 - pipeline & IO verification
def test_pipeline_outputs_persist(tmp_path, sync_spec, monkeypatch):
    result = execute_pipeline(sync_spec, tmp_path / "outputs")
    run_dir = Path(result.manifest.base_output_dir) / result.manifest.run_directory
    telemetry_path = run_dir / "telemetry.parquet"
    assert telemetry_path.exists()
    data = pd.read_parquet(telemetry_path)
    assert set(data.columns) >= {"soc_kwh", "charge_in_kw"}
```

### Changes Required

#### 1. Pipeline Registry & Executor Wiring
**File:** `simkit/core/pipeline_registry.py`
**Changes:**
- [x] Register `SynchronousSim` descriptor with required inputs (`SyncTimeGrid`, `BatteryState`, `PriceTrajectory`, configs) and outputs (bundle plus fan-out channels).
- [x] Update registry tests to assert descriptor presence and version propagation.
- [x] Ensure module factory returns `SynchronousSimModule` with the stub bridge default for tests.

```python
registry.register(
    "SynchronousSim",
    ModuleDescriptor(
        module_type="SynchronousSim",
        factory=_factory(SynchronousSimModule),
        required_inputs={"time_grid": schema.SyncTimeGrid, ...},
        outputs={"synchronous_sim": schema.SyncSimOutputs},
        version=SynchronousSimModule.version,
    ),
)
```

#### 2. Output Router & Writers
**File:** `simkit/io/output_router.py`
**Changes:**
- [x] Register writers for `MockForecastSeries`, `SyncGuidanceSeries`, and `SyncTelemetrySeries`.
- [x] Extend `simkit/io/writers.py` with functions serializing series to JSON/Parquet, including inner-loop frames where applicable.
- [x] Update manifest generation to reflect new artifact types.

```python
handlers[schema.MockForecastSeries.__name__] = WriteHandler(
    fn=writers.write_mock_forecast_series,
    extension=".json",
)
handlers[schema.SyncTelemetrySeries.__name__] = WriteHandler(
    fn=writers.write_sync_telemetry_series,
    extension=".parquet",
)
```

#### 3. Test Suite Enhancements
**File:** `simkit/tests/io/test_output_router.py`
**Changes:**
- [x] Add coverage ensuring new handlers persist artifacts and record manifest entries.
- [x] Extend test suite to assert the registry contains the `SynchronousSim` module.
- [x] Remove `xfail` markers from Phase 0 tests and validate both happy-path and failure-path scenarios.

```python
def test_output_router_handles_sync_series(tmp_path, sync_outputs):
    router = create_default_router()
    bindings = {
        "telemetry": PipelineChannelBinding(
            type_name="SyncTelemetrySeries",
            channel_name="telemetry",
            source=ChannelSource.MODULE,
            destination_filename="telemetry.parquet",
        )
    }
    result = router.write_outputs(bindings, {"telemetry": sync_outputs.telemetry}, base_output_dir=tmp_path)
    assert any(a.type_name == "SyncTelemetrySeries" for a in result.manifest.artifacts)
```

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/test_pipeline_synchronous_sim.py::test_synchronous_sim_stubbed_happy_path` passes without xfail.
- [x] `pytest simkit/tests/test_pipeline_synchronous_sim.py::test_synchronous_sim_stubbed_failure_annotation` passes and confirms failure metadata.
- [x] `pytest` (entire suite) passes locally with new writers and registry entries.

#### Manual Verification:
- [ ] Running the new pipeline spec via `python -m simkit.core.pipeline simkit/tests/fixtures/pipeline_configs/synchronous_sim_stubbed.yaml --output tmp/run` generates manifest with synchronous artifacts.
- [x] Inspecting persisted telemetry parquet confirms expected columns, units, and row counts.
- [ ] README or docs mention availability of synchronous sim scenario (if required by product guidance).

## Implementation Notes - Phase 3
**Completed:** 2025-09-24 00:48:00Z
**Changes Made:**
- Registered `SynchronousSim` in `simkit/core/pipeline_registry.py` with bundle plus per-channel outputs and extended `PipelineModuleRegistry` exports.
- Faned out synchronous simulation channels in `simkit/core/synchronous_sim/module.py`, updated pipeline fixtures, and added entry loaders for new schema types in `simkit/core/pipeline_executor.py`.
- Added synchronous writers/handlers in `simkit/io/writers.py` and `simkit/io/output_router.py`, with new sync output fixtures and coverage in `simkit/tests/io/test_output_router.py`.
- Removed `xfail` marks and expanded pipeline tests (`simkit/tests/test_pipeline_synchronous_sim.py`, `simkit/tests/pipeline/test_pipeline_dag.py`) to assert registry wiring and artifact persistence.
- Ran `pytest` to exercise the updated synchronous simulation pathway end-to-end.
**Issues Encountered:**
- Relative paths in the failure-spec clone required mirroring the fixtures directory; resolved by copying `synchronous_sim` fixtures into the temporary pipeline bundle during tests.
**Deviations from Plan:**
- The module now emits individual forecast/guidance/telemetry channels alongside the bundled payload to simplify ExitPoint routing; future MATLAB integration remains stub-only per updated scope.
**Metadata Snapshot:**
- Current Date/Time (TZ): 2025-09-23 17:48:00 PDT
- Current Git Commit Hash: b8876a998e7fe936bec6d801f7582450aa0a623d
- Current Branch Name: synchronous_sim
- Active Git Username: Reid W
- Repository Name: pyrondo2-demo
- Timestamp For Filename: 2025-09-23_17-48-00

---

## Testing Strategy
### Unit Tests
- Schema validators covering TimeSpan normalization, outer/inner alignment, and SyncSimOutputs aggregation.
- Component-level tests for forecast/guidance logic and dynamics bridges (stub + MATLAB failure mocking).

### Integration Tests
- Pipeline scenario using stub dynamics (happy path) ensuring artifacts and manifest entries are created.
- Failure-path integration test verifying annotated error propagation halts pipeline as designed.

### Manual Testing Steps
1. Execute the synchronous pipeline spec against stub dynamics and inspect persisted outputs.
2. (Optional) Swap in MATLAB bridge with lightweight Simulink model to verify engine startup on developer machine.
3. Review manifest JSON to confirm new artifact types and metadata fields are populated.

## Risk Management
### Identified Risks
- **Schema complexity blow-up**: High number of new models may become unwieldy.
  - *Mitigation*: Group related models and consider secondary module (e.g., `schema_sync.py`) re-exported from `schema.py`.
  - *Rollback*: Revert schema splitting to single file while retaining validators if fragmentation proves confusing.
- **MATLAB dependency instability**: Engine imports may break CI or local runs without MATLAB.
  - *Mitigation*: Default to `StubDynamicsBridge` unless explicit MATLAB config provided; guard imports and provide clear errors.
  - *Rollback*: Feature flag the MATLAB bridge so it ships disabled by default.
- **Output serialization performance**: Writing inner-loop telemetry could create large files.
  - *Mitigation*: Compress parquet outputs and allow fixture-driven truncation for tests.
  - *Rollback*: Reduce telemetry detail (aggregate-only) until streaming approach is optimized.

### Dependencies
- Python 3.10+, pandas, numpy, pyarrow already available via `pyproject.toml`.
- Optional MATLAB Engine for runtime validation (not required for CI due to stub).
- Existing pipeline execution framework in `simkit/core/pipeline.py` and registry infrastructure.

## References
- Original spec: `thoughts/specs/2025-09-23-synchronous-sim.md`
- Implementation design: `thoughts/design/2025-09-23-synchronous-sim-design.md`
- TE simulation principles: `tea_simulation_design_doc.md`
- Pipeline registry example: `simkit/core/pipeline_registry.py`
- Output routing patterns: `simkit/io/output_router.py`
