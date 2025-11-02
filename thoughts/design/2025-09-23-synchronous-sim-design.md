# Synchronous Simulation Module Implementation Design

**Document Type:** Implementation Design
**Version:** v1.0
**Status:** Implementation In Progress
**Owner:** Reid W
**Last Updated:** 2025-09-23 17:38:06Z
**Related Docs:** tea_simulation_design_doc.md, thoughts/tickets/synchronous-sim.md
**Current Branch Name:** synchronous_sim
**Current Commit:** dc2c35a428c2a6aa6abe9f92e26d7679f198a317

## Overview
Design and implement a pipeline-ready `SynchronousSim` module that consumes fully typed configuration, multi-resolution time grids, and actual future pricing data to orchestrate forecast, guidance, and MATLAB-backed dynamics in lockstep. Every payload exchanged among components is expressed as a `simkit.config.schema` model so units, currencies, and metadata remain explicit. The time grid captures both the outer supervisory cadence and inner-loop schedules that subcomponents require (e.g., one-minute dynamics inside an hourly loop). Components maintain their own state, and each `step(...)` call receives a schema-based payload supplying all information needed for that tick. MATLAB interactions are abstracted behind a bridge with stub implementations so tests execute without MATLAB installed.

## Spec Reference
**Source Spec:** `thoughts/specs/2025-09-23-synchronous-sim.md`
**Key Requirements Addressed:**
- Register a `SynchronousSim` module that honors the standard `validate_and_fill_default` / `run` contract used across `simkit/core`.
- Validate time grids, initial battery state, actual pricing trajectory, and subcomponent configs; fill documented defaults where optional fields are omitted.
- Execute forecast, guidance, and dynamics components in lockstep across the specified time grid, returning typed collections for forecasts, guidances, and telemetry.
- Start MATLAB Engine and execute Simulink models via a configuration-driven dynamics bridge, while allowing stub dynamics in development/test contexts.
- Propagate annotated `ValueError` messages (timestamp + component metadata) when any component fails during initialization or stepping.

## Architecture
The synchronous module plugs into the existing pipeline executor via the module registry. It validates incoming schema payloads, instantiates concrete subcomponents (mock forecast, heuristic guidance, dynamics bridge), and iterates over the outer control loop defined by `schema.SyncTimeGrid`. For each outer step, the module slices the actual pricing trajectory into the horizon required by the forecast stub, forwards the resulting mock forecast to the guidance component, and hands the produced guidance plus inner-loop schedule to the dynamics bridge. Components hold their own state (e.g., accumulated forecast history, guidance heuristics, MATLAB simulation time) and the module provides all necessary per-step context via typed `StepInput` models.

```mermaid
graph TD
    A[Pipeline Executor] -->|run(inputs)| B[SynchronousSimModule]
    B -->|MockForecastInit/StepInput| C[MockForecastComponent]
    B -->|GuidanceInit/StepInput| D[GuidanceComponent]
    B -->|DynamicsInit/StepInput| E[DynamicsBridge]
    C -->|MockForecastPoint| B
    D -->|GuidanceCommand| B
    E -->|TelemetryFrame| B
    B --> F[SyncSimOutputs]
    F --> G[Pipeline Channels & Output Router]
```

## Components and Interfaces

### SynchronousSimModule
**Purpose:** Pipeline-facing wrapper responsible for validation, component wiring, and loop orchestration.
**Key Methods:**
```python
@dataclass(frozen=True)
class SynchronousSimInputs:
    time_grid: schema.SyncTimeGrid
    initial_state: schema.BatteryState
    actual_pricing: schema.PriceTrajectory
    forecast_config: schema.MockForecastConfig
    guidance_config: schema.GuidanceConfig
    dynamic_sim_config: schema.DynamicSimConfig
    dynamics_bridge: DynamicsBridge  # resolved (MATLAB or stub)

class SynchronousSimModule(ModuleBase[SynchronousSimInputs, schema.SyncSimOutputs]):
    name = "synchronous_sim"
    version = "v0.1"

    def validate_and_fill_default(
        self,
        time_grid: schema.SyncTimeGrid | Mapping[str, object],
        initial_state: schema.BatteryState | Mapping[str, object],
        actual_pricing: schema.PriceTrajectory | Mapping[str, object],
        forecast_config: schema.MockForecastConfig | Mapping[str, object] | None = None,
        guidance_config: schema.GuidanceConfig | Mapping[str, object] | None = None,
        dynamic_sim_config: schema.DynamicSimConfig | Mapping[str, object] | None = None,
        *,
        dynamics_override: DynamicsBridge | None = None,
    ) -> SynchronousSimInputs: ...

    def run(
        self,
        time_grid: schema.SyncTimeGrid | Mapping[str, object],
        initial_state: schema.BatteryState | Mapping[str, object],
        actual_pricing: schema.PriceTrajectory | Mapping[str, object],
        **configs,
    ) -> ModuleResult[schema.SyncSimOutputs]: ...
```
**Dependencies:** `simkit/config/schema`, `simkit/config/defaults`, numpy for vectorized checks, `MockForecastComponent`, `GuidanceComponent`, `DynamicsBridge` implementations.
**Integration Points:** Registered in `PipelineModuleRegistry` with explicit schema input/output bindings; output router gains handlers for new series models.

### MockForecastComponent
**Purpose:** Deterministically derive a noisy forecast from the actual future pricing trajectory.
**Key Methods:**
```python
class MockForecastComponent:
    def __init__(self) -> None: ...

    def initialize(
        self,
        config: schema.MockForecastConfig,
        init: schema.MockForecastInitInput,
    ) -> None: ...

    def step(
        self,
        payload: schema.MockForecastStepInput,
    ) -> schema.MockForecastPoint: ...
```
- `schema.MockForecastInitInput` supplies currency, units, forecast horizon duration (as `schema.TimeSpan`), and seeded RNG configuration.
- `schema.MockForecastStepInput` contains the `schema.SyncOuterStep` metadata and a `schema.PriceTrajectoryWindow` referencing the actual prices over the look-ahead horizon, including timestamps and currency.
- Component retains internal RNG state to produce reproducible noise per step.

### GuidanceComponent
**Purpose:** Produce guidance commands based on mock forecasts and the latest battery state.
**Key Methods:**
```python
class GuidanceComponent:
    def __init__(self) -> None: ...

    def initialize(
        self,
        config: schema.GuidanceConfig,
        init: schema.GuidanceInitInput,
    ) -> None: ...

    def step(
        self,
        payload: schema.GuidanceStepInput,
    ) -> schema.SyncGuidance: ...
```
- `schema.GuidanceInitInput` bundles static battery capability (power limits, capacity bounds) and inner-loop schedule for dynamics, expressed with `schema.TimeSpan`.
- `schema.GuidanceStepInput` provides the current `schema.SyncOuterStep`, the most recent `schema.MockForecastPoint`, the realized portion of the actual price trajectory for context, and the current `schema.BatteryState` returned by dynamics after the prior step.
- Output `schema.SyncGuidance` records commanded charge/discharge power (kW), optional state targets, and rationale metadata.

### DynamicsBridge Implementations
**Purpose:** Advance the physical model (MATLAB-backed or stub) according to guidance while honoring inner-loop timing.
**Key Methods:**
```python
class DynamicsBridge(Protocol):
    def initialize(
        self,
        config: schema.DynamicSimConfig,
        init: schema.DynamicsInitInput,
    ) -> None: ...

    def step(
        self,
        payload: schema.DynamicsStepInput,
    ) -> schema.SyncTelemetryFrame:
        """Return telemetry for the outer step, including inner-loop samples."""

class MatlabDynamicsBridge(DynamicsBridge):
    ...

class StubDynamicsBridge(DynamicsBridge):
    ...
```
- `schema.DynamicsInitInput` includes the initial `schema.BatteryState`, inner-loop definition (as `schema.TimeSpan` cadence and pandas-friendly frequency code), Simulink signal identifiers, and derived pandas indices for the first outer step.
- `schema.DynamicsStepInput` carries the current `schema.SyncOuterStep`, issued `schema.SyncGuidance`, inner-loop timestamps (`pandas.DatetimeIndex` constructed via helper), and `PriceTrajectoryWindow` if the Simulink model needs price inputs.
- MATLAB bridge converts outputs into `schema.SyncTelemetryFrame` capturing inner-step telemetry aligned with inner-loop timestamps; stub bridge synthesizes equivalent data for testing.

### Loop State & Aggregation
- `SynchronousSimModule` tracks the latest `schema.BatteryState` returned by the dynamics bridge to feed into the next `GuidanceStepInput`.
- Outputs collated into `schema.SyncSimOutputs`, containing:
  - `schema.MockForecastSeries`
  - `schema.SyncGuidanceSeries`
  - `schema.SyncTelemetrySeries`
Each series retains explicit timestamps, units, and metadata consistent with the original inputs.

## Data Models
Introduce the following models under `simkit/config/schema.py` (or a dedicated `time_models.py` module if separation improves clarity):

- **Time & Duration Types**
  - `TimeSpan`: stores duration input either as ISO-8601 string, pandas offset alias (e.g., "1H", "15T"), numeric value + unit (`Literal["seconds", "minutes", "hours", "days"]`), or `datetime.timedelta`. Validators normalize to an internal `pandas.Timedelta`. Helper methods:
    ```python
    class TimeSpan(StrictBaseModel):
        raw: str | float | datetime.timedelta
        unit: Literal["seconds", "minutes", "hours", "days"] | None = None

        @computed_field
        def as_timedelta(self) -> datetime.timedelta: ...

        def to_pandas_timedelta(self) -> pd.Timedelta: ...
        def to_pandas_freq(self) -> str: ...  # e.g., "1H"
        def total_seconds(self) -> float: ...
    ```
    This satisfies unit flexibility, supports conversions, and plugs directly into pandas index creation.
  - `SyncOuterStep`: `{index: int, start: datetime, end: datetime, duration: TimeSpan}` with validators ensuring contiguous spans (the default `duration` computed from start/end if omitted).
  - `InnerLoopConfig`: `{component: Literal["forecast", "guidance", "dynamics"], step: TimeSpan, samples_per_outer: int | None}`; validation enforces that `TimeSpan` divides the outer step duration. Provides helper `build_index(outer_step: SyncOuterStep) -> pd.DatetimeIndex`.
  - `SyncTimeGrid`: `{outer_steps: List[SyncOuterStep], outer_step: TimeSpan, inner_loops: List[InnerLoopConfig]}` with cross-validators ensuring consistent durations and alignment with pricing timeline.

- **Pricing**
  - `PriceTrajectory`: `{time_index: List[datetime], values: List[float], currency: str, unit: Literal["USD/kWh", ...], source: str}`; computed helpers (`start`, `end`, `span`, `frequency`) keep the series self-describing and power the window slicing.
  - `PriceTrajectoryWindow`: subclass of `PriceTrajectory` obtained via `PriceTrajectory.window(...)`, representing the look-ahead slice for a step while reusing the same validation and metadata surface.

- **Initial Conditions & State**
  - `BatteryState`: retains SOC (kWh), charge/discharge power (kW), temperature optional, with validators for bounds.

- **Forecast Models**
  - `MockForecastConfig`: fields such as `look_ahead: TimeSpan`, `noise_std_dev`, `seed`, ensures `look_ahead` is >= outer step duration.
  - `MockForecastInitInput`: derived from config + time grid (`look_ahead_index_count`, `pricing_currency`, `unit`).
  - `MockForecastStepInput`: includes `SyncOuterStep`, `PriceTrajectoryWindow`, and optional history.
  - `MockForecastPoint`: `{forecast: List[float], timestamps: List[datetime], currency: str, unit: str, issued_at: datetime}` ensuring timestamps derived via `TimeSpan` frequency.
  - `MockForecastSeries`: wraps list of points and exposes `to_pandas()` for multi-index DataFrame.

- **Guidance Models**
  - `GuidanceConfig`: thresholds for charge/discharge behavior, SOC limits, smoothing factors, referencing `TimeSpan` where relevant (e.g., ramp durations).
  - `GuidanceInitInput`: includes battery ratings, `InnerLoopConfig` for dynamics, and `TimeSpan`-based ramp constraints.
  - `GuidanceStepInput`: contains `SyncOuterStep`, latest `MockForecastPoint`, current `BatteryState`, and `PriceTrajectoryWindow` (if price-informed decisions needed).
  - `SyncGuidance`: setpoint commands with units and metadata; `SyncGuidanceSeries` aggregates them, providing `to_pandas()` to build `DatetimeIndex` via `TimeSpan` conversions.

- **Dynamics Models**
  - `DynamicSimConfig`: model path/name, `inner_step: TimeSpan`, optional `pandas_freq_override`, signal names, `use_fast_restart`, `sim_mode`, telemetry signals, and workspace variable names.
  - `DynamicsInitInput`: captures initial `BatteryState`, resolved `pd.DatetimeIndex` for the first outer step (built from inner step `TimeSpan`), and parameter overrides.
  - `DynamicsStepInput`: `SyncOuterStep`, issued `SyncGuidance`, generated inner-loop index (`pd.DatetimeIndex` via helper), and optional `PriceTrajectoryWindow` for model inputs.
  - `SyncTelemetryFrame`: outer-step aggregate plus `inner_times: pd.DatetimeIndex` and arrays for charge/discharge, SOC, etc. `SyncTelemetrySeries` stores list of frames; validators ensure frame counts match outer step count and lengths align with inner index length computed from `TimeSpan`.

- **Outputs**
  - `SyncSimOutputs`: `{forecasts: MockForecastSeries, guidances: SyncGuidanceSeries, telemetry: SyncTelemetrySeries}` with `model_validator` enforcing consistent outer-step indices across all series via shared `TimeSpan` conversions.

## Error Handling
- Wrap each `initialize` and `step` call in a helper that appends component metadata and the relevant outer-step timestamp to the error message, raising a `ValueError` such as `[step][component=dynamics][outer_index=5][timestamp=2025-01-01T05:00:00Z] failed: <message>`.
- When an exception occurs, halt the loop immediately, discard in-progress aggregation for that step, and re-raise the annotated error (`raise ValueError(...) from exc`).
- MATLAB bridge ensures `matlab.engine` sessions are closed on initialization failure and provides contextual messages when Simulink model loading or signal extraction fails.

## Testing Strategy
### Unit Tests
- `test_time_span_parses_units`: ensure `TimeSpan` accepts "1H", `60`, `datetime.timedelta(hours=1)` and produces matching pandas/numpy conversions.
- `test_sync_time_grid_alignment`: mismatched outer durations vs inner loop definitions raise ValueError with message referencing offending step index.
- `test_price_trajectory_to_pandas`: verifies currency/unit metadata preserved and pandas index aligns with `TimeSpan` frequency.
- `test_mock_forecast_generates_noise_with_units`: verifies output currency/unit match `PriceTrajectory` and noise parameters.
- `test_guidance_step_uses_schema_inputs`: ensures `GuidanceStepInput` carrying explicit metadata yields bounded `SyncGuidance` values.
- `test_dynamics_bridge_stub_respects_inner_loop`: stub bridge consumes `DynamicsStepInput` and produces `SyncTelemetryFrame` with expected inner-loop index derived from `TimeSpan`.
- `test_failure_annotation_strings`: inject faults in each component and assert raised ValueError includes component and timestamp context.

### Integration Tests
- `test_pipeline_runs_synchronous_sim_stubbed`: pipeline spec binds `SyncTimeGrid`, `PriceTrajectory`, and configs from fixtures; executes successfully with stub dynamics and validates JSON/Parquet outputs for each series, including pandas-friendly indices.
- `test_pipeline_handles_dynamics_failure`: stub bridge configured to fail at a specific outer step; pipeline raises annotated ValueError without writing outputs.

### Acceptance Tests
- Scenario script demonstrating hour-level supervisory loop with one-minute dynamics, using stub bridge and synthetic price trajectory; verifies output artifacts and metadata integrity along with pandas index creation from `TimeSpan` helpers.
- Manual MATLAB smoke test: run module with `MatlabDynamicsBridge` against a lightweight Simulink model to confirm engine startup, model loading, and telemetry extraction.

## Implementation Notes
- `TimeSpan` parsing leverages `pandas.Timedelta` to guarantee unit flexibility and direct compatibility with pandas index builders. Helper utilities live in `simkit/config/time_utils.py` (or similar) to provide shared conversions (`build_inner_index(outer_step, inner_config)`).
- Validation ensures `PriceTrajectory.to_pandas()` spans the entire horizon implied by `SyncTimeGrid` (outer steps × duration), preventing silent mismatches.
- Components maintain their own internal state, consuming schema init/step payloads that already contain any static context (no shared `SimulationContext`).
- `MockForecastComponent` seeds its RNG using `MockForecastConfig.seed`; repeated runs with identical inputs produce deterministic noise for regression testing.
- Guidance heuristics draw on percentile-based logic similar to `SimplePerformanceSimModule` but operate on explicit schema inputs.
- MATLAB bridge defers importing `matlab.engine` until initialization; `dynamic_sim_config.use_stub` or `dynamics_override` lets tests bypass MATLAB entirely.
- Output router gains handlers for `MockForecastSeries`, `SyncGuidanceSeries`, and `SyncTelemetrySeries`. Telemetry writer serializes both outer-step aggregates and optional inner-step frames, persisting pandas-friendly indices for downstream analytics.
- Registry update adds `SynchronousSim` descriptor with clear required inputs (`SyncTimeGrid`, `BatteryState`, `PriceTrajectory`, configs) and outputs (individual series or bundled outputs, depending on pipeline binding strategy).

## References
- Original spec: `thoughts/specs/2025-09-23-synchronous-sim.md`
- Related ticket: `thoughts/tickets/synchronous-sim.md`
- Base module contract: `simkit/core/base.py:13`
- Validation/run pattern example: `simkit/core/perf_sim_simple/module.py:21`
- Pipeline registry wiring: `simkit/core/pipeline_registry.py:31`
- Pipeline executor channel handling: `simkit/core/pipeline_executor.py:93`
- Output router persistence pattern: `simkit/io/output_router.py:49`
- TE simulation principles: `tea_simulation_design_doc.md`
