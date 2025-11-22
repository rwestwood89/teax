"""Pydantic data models for the asynchronous simulation demo.

IMPORTANT FOR MAINTAINERS:

When adding a new user-facing schema to this file (i.e., a schema that will be
used in EntryPoint artifact loading, module I/O, or ExitPoint writing), you MUST
also register it in the following locations:

1. simkit/core/pipeline_executor.py:_build_schema_type_registry()
   - Add schema to the manual enumeration dict (lines 438-457)
   - Update the test in simkit/tests/core/test_custom_schema_registration.py
   - Test: test_all_user_facing_schemas_registered()

2. simkit/io/output_router.py:create_default_router()
   - Add schema to the manual enumeration for JSON write handlers
   - Only if schema should be writable at ExitPoint

3. simkit/core/pipeline_executor.py:_BUILTIN_ENTRY_LOADERS
   - Add entry loader function if schema requires special loading
   - Most schemas use default JSON loader (no action needed)

Schemas that do NOT need registration:
- Abstract base classes (e.g., MultiOutput)
- Pipeline metadata types (e.g., Provenance, RunManifest)
- Nested field types not used as standalone artifacts (e.g., CostLineItem)
- Internal implementation types (e.g., TimeSpan, SyncOuterStep)

See test_all_user_facing_schemas_registered() for complete list of registered schemas.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    computed_field,
    field_validator,
    model_validator,
)

from . import time_utils


class StrictBaseModel(BaseModel):
    """Base model enforcing immutable, validated data."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class MultiOutput(StrictBaseModel):
    """Container base class for modules that produce multiple typed outputs.

    Use this as the OutputModel for modules that need to route different
    data types to different downstream modules. Each field in the subclass
    becomes a separate channel in the pipeline.

    Example:
        >>> class AlphaNeutronSplitOutput(MultiOutput):
        ...     p_alpha: PowerValue
        ...     p_neutron: PowerValue
        ...
        >>> class AlphaNeutronSplitModule(
        ...     ModuleBase[FusionInput, AlphaNeutronSplitOutput]
        ... ):
        ...     def run(self, ...) -> ModuleResult[AlphaNeutronSplitOutput]:
        ...         return ModuleResult(
        ...             data=AlphaNeutronSplitOutput(
        ...                 p_alpha=PowerValue(value=520.5),
        ...                 p_neutron=PowerValue(value=2079.4),
        ...             )
        ...         )

    The pipeline executor will automatically extract each field and route it
    to the appropriate channel based on the YAML output declarations.

    See Also:
        - thoughts/designs/generalized_teax_type_system_design.md (Component 2)
        - thoughts/research/input_output_asymmetry_analysis.md
    """

    def to_channel_dict(self) -> Dict[str, BaseModel]:
        """Convert multi-output fields to channel routing dict.

        Returns:
            Dictionary with field names as keys and field values as values.
            Used by executor to route outputs to separate channels.

        Example:
            >>> output = AlphaNeutronSplitOutput(p_alpha=..., p_neutron=...)
            >>> channels = output.to_channel_dict()
            >>> # {"p_alpha": PowerValue(...), "p_neutron": PowerValue(...)}
        """
        return {
            field_name: getattr(self, field_name)
            for field_name in self.__class__.model_fields.keys()
        }


class Geography(StrictBaseModel):
    country: str
    region: Optional[str]
    utility: Optional[str]
    timezone: Optional[str]
    currency: Optional[str]


class LoadProfile8760(StrictBaseModel):
    time_index: List[datetime]
    load_kwh: List[float] = Field(..., description="8760 hourly load consumption values in kWh")
    source: str
    unit: Literal["kWh"] = "kWh"

    @field_validator("load_kwh")
    @classmethod
    def validate_length(cls, values: Sequence[float]) -> List[float]:
        if len(values) != 8760:
            raise ValueError("load_kwh must contain 8760 values")
        return list(values)

    @field_validator("time_index")
    @classmethod
    def validate_time_index(cls, values: Sequence[datetime]) -> List[datetime]:
        if len(values) != 8760:
            raise ValueError("time_index must contain 8760 timestamps")
        return list(values)


class PVProfile8760(StrictBaseModel):
    time_index: List[datetime]
    production_kwh: List[float]
    source: str
    unit: Literal["kWh"] = "kWh"

    @field_validator("production_kwh")
    @classmethod
    def validate_prod_length(cls, values: Sequence[float]) -> List[float]:
        if len(values) != 8760:
            raise ValueError("production_kwh must contain 8760 values")
        return list(values)

    @field_validator("time_index")
    @classmethod
    def validate_time_index(cls, values: Sequence[datetime]) -> List[datetime]:
        if len(values) != 8760:
            raise ValueError("time_index must contain 8760 timestamps")
        return list(values)


class RateInfo(StrictBaseModel):
    energy_price_usd_per_kwh: Optional[List[float]]
    tou_periods: Optional[Dict[str, float]]
    tou_mapping_hourly: Optional[List[str]]
    demand_charge_usd_per_kw: Optional[Dict[str, float]]
    fixed_monthly_fee_usd: Optional[float]
    price_year: int
    currency: str
    vintage: str
    source: str
    escalation_rules: Optional[Dict[str, float]]

    @field_validator("energy_price_usd_per_kwh")
    @classmethod
    def validate_price_length(cls, values: Optional[Sequence[float]]) -> Optional[List[float]]:
        if values is not None and len(values) != 8760:
            raise ValueError("energy_price_usd_per_kwh must contain 8760 values when provided")
        return list(values) if values is not None else None

    @field_validator("tou_mapping_hourly")
    @classmethod
    def validate_mapping_length(cls, values: Optional[Sequence[str]]) -> Optional[List[str]]:
        if values is not None and len(values) != 8760:
            raise ValueError("tou_mapping_hourly must contain 8760 entries when provided")
        return list(values) if values is not None else None


class DesignPrefs(StrictBaseModel):
    target_peak_shaving_hours: Optional[PositiveFloat]
    max_c_rate: Optional[PositiveFloat]
    min_soc: Optional[float]
    max_soc: Optional[float]
    eta_roundtrip: Optional[float]
    safety_margins: Optional[Dict[str, float]]

    @model_validator(mode="after")
    def validate_soc(self) -> "DesignPrefs":
        if self.max_soc is not None and self.min_soc is not None and self.max_soc <= self.min_soc:
            raise ValueError("max_soc must be greater than min_soc")
        return self


class BatteryConfig(StrictBaseModel):
    capacity_kwh: float
    power_kw: float
    charge_kw_max: float
    discharge_kw_max: float
    eta_roundtrip: float
    soc_min: float
    soc_max: float
    lifecycle_warranty_cycles: Optional[int]
    lifecycle_warranty_years: Optional[int]
    notes: Optional[str]
    rationale: Optional[str]
    schema_version: str = "v0.1"


class CostLineItem(StrictBaseModel):
    name: str
    basis: str
    unit_cost: float
    qty: float
    cost: float
    currency: str


class CostBreakdown(StrictBaseModel):
    line_items: List[CostLineItem]
    capex_total: float
    annual_om_usd: float
    price_year: int
    assumptions: Dict[str, str]
    currency: str
    schema_version: str = "v0.1"


class BatteryTelemetry8760(StrictBaseModel):
    charge_in_kwh: List[float]
    discharge_out_kwh: List[float]
    soc_kwh: List[float]
    constraints_hits: Dict[str, int]
    method: str
    schema_version: str = "v0.1"

    @field_validator("charge_in_kwh", "discharge_out_kwh", "soc_kwh")
    @classmethod
    def validate_array_length(cls, values: Sequence[float]) -> List[float]:
        if len(values) != 8760:
            raise ValueError("Telemetry arrays must contain 8760 values")
        return list(values)


class FinancialParams(StrictBaseModel):
    discount_rate: float
    analysis_years: int
    depreciation_method: Optional[str]
    tax_rate: Optional[float]
    escalation_energy: Optional[float]
    escalation_om: Optional[float]
    upfront_capex_usd: Optional[float]
    annual_om_usd: Optional[float]


class CashflowEntry(StrictBaseModel):
    year: int
    net_cashflow: float
    cumulative_cashflow: float


class LedgerEntry(StrictBaseModel):
    name: str
    amount: float
    currency: str
    category: str


class FinancialResults(StrictBaseModel):
    annual_savings: float
    cashflow: List[CashflowEntry]
    npv: float
    irr: Optional[float]
    payback_years: Optional[float]
    lcoe: Optional[float]
    lcob: Optional[float]
    ledger: List[LedgerEntry]
    currency: str
    price_year: int
    schema_version: str = "v0.1"


class Provenance(StrictBaseModel):
    config_hash: str
    module_versions: Dict[str, str]
    notes: Optional[str]
    output_folder: Optional[str] = None


class PipelineRunMetadata(StrictBaseModel):
    spec_path: str
    run_description: Optional[str] = None
    output_folder: Optional[str] = None


class RunArtifactRecord(StrictBaseModel):
    channel: str
    type_name: str
    relative_path: str | None = None
    produced: bool = True


class RunManifest(StrictBaseModel):
    run_name: str
    run_directory: str
    base_output_dir: str
    short_id: str
    metadata: Dict[str, Any] | None = None
    artifacts: List[RunArtifactRecord]


# ---------------------------------------------------------------------------
# Synchronous simulation schema (Phase 1 foundations)


class TimeSpan(StrictBaseModel):
    """Flexible duration representation convertible to pandas offsets."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    raw: str | int | float | timedelta
    unit: Literal["seconds", "minutes", "hours", "days"] | None = None

    @computed_field(return_type=pd.Timedelta)
    def delta(self) -> pd.Timedelta:
        return time_utils.normalize_timespan(self.raw, self.unit)

    def to_pandas_freq(self) -> str:
        return time_utils.to_pandas_freq(self.delta)

    def total_seconds(self) -> float:
        return float(self.delta.total_seconds())


class SyncOuterStep(StrictBaseModel):
    """Outer supervisory loop step definition."""

    index: int
    start: datetime
    duration: TimeSpan

    @computed_field(return_type=datetime)
    def end(self) -> datetime:
        return self.start + self.duration.delta.to_pytimedelta()

    @model_validator(mode="after")
    def _validate_step(self) -> "SyncOuterStep":
        if self.index < 0:
            raise ValueError("SyncOuterStep index must be non-negative")
        if self.start.tzinfo is None:
            raise ValueError("SyncOuterStep.start must be timezone-aware")
        return self

    def to_timespan(self) -> TimeSpan:
        return self.duration


class InnerLoopConfig(StrictBaseModel):
    """Inner-loop configuration executed within each outer step."""

    component: str
    step: TimeSpan
    samples_per_outer: int

    @model_validator(mode="after")
    def _validate_inner(self) -> "InnerLoopConfig":
        if not self.component:
            raise ValueError("InnerLoopConfig.component must be non-empty")
        if self.samples_per_outer <= 0:
            raise ValueError("InnerLoopConfig.samples_per_outer must be positive")
        return self


class SyncTimeGrid(StrictBaseModel):
    """Composite time grid describing outer steps and nested inner loops."""

    timezone: str | None = None
    outer_steps: List[SyncOuterStep]
    inner_loops: List[InnerLoopConfig]

    @model_validator(mode="after")
    def _validate_grid(self) -> "SyncTimeGrid":
        if not self.outer_steps:
            raise ValueError("SyncTimeGrid requires at least one outer step")

        indices = [step.index for step in self.outer_steps]
        if indices != list(range(len(self.outer_steps))):
            raise ValueError("SyncTimeGrid outer step indices must be contiguous starting at 0")

        reference_duration = self.outer_steps[0].duration.delta
        for step in self.outer_steps:
            if step.start.tzinfo is None:
                raise ValueError("SyncTimeGrid outer steps require timezone-aware timestamps")
            if self.timezone is not None and str(step.start.tzinfo) != self.timezone:
                raise ValueError("SyncTimeGrid timezone mismatch between grid and outer steps")
            if step.duration.delta != reference_duration:
                raise ValueError("All SyncTimeGrid outer steps must share the same duration")

        for previous, current in zip(self.outer_steps, self.outer_steps[1:]):
            if current.start != previous.end:
                raise ValueError("SyncTimeGrid outer steps must be contiguous without gaps")

        for config in self.inner_loops:
            ratio = reference_duration / config.step.delta
            if not math.isclose(ratio, round(ratio), rel_tol=0, abs_tol=1e-9):
                raise ValueError(
                    "InnerLoopConfig.step must divide the outer step duration without remainder"
                )
            expected_samples = int(round(ratio))
            if config.samples_per_outer != expected_samples:
                raise ValueError(
                    "InnerLoopConfig.samples_per_outer must equal outer_duration / step duration"
                )
        return self

    @property
    def outer_duration(self) -> pd.Timedelta:
        return self.outer_steps[0].duration.delta


class PriceTrajectory(StrictBaseModel):
    """Time-aligned price series used for forecasting and guidance."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    time_index: List[datetime]
    values: List[float]
    currency: str
    unit: str
    source: str | None = None

    @model_validator(mode="after")
    def _validate_series(self) -> "PriceTrajectory":
        if len(self.time_index) != len(self.values):
            raise ValueError("PriceTrajectory time_index and values must be the same length")
        if len(self.time_index) == 0:
            raise ValueError("PriceTrajectory requires at least one sample")
        for ts in self.time_index:
            if ts.tzinfo is None:
                raise ValueError("PriceTrajectory timestamps must be timezone-aware")
        if len(self.time_index) > 1:
            deltas = [later - earlier for earlier, later in zip(self.time_index, self.time_index[1:])]
            first_delta = deltas[0]
            for delta in deltas[1:]:
                if delta != first_delta:
                    raise ValueError("PriceTrajectory requires uniform spacing between samples")
        return self

    def to_pandas(self) -> pd.Series:
        return pd.Series(self.values, index=pd.DatetimeIndex(self.time_index))

    @property
    def frequency(self) -> pd.Timedelta:
        if len(self.time_index) == 1:
            return pd.Timedelta(0)
        return pd.Timedelta(self.time_index[1] - self.time_index[0])

    @computed_field(return_type=datetime)
    def start(self) -> datetime:
        return self.time_index[0]

    @computed_field(return_type=datetime)
    def end(self) -> datetime:
        step = self.frequency
        if step == pd.Timedelta(0):
            return self.time_index[-1]
        return self.time_index[-1] + step.to_pytimedelta()

    @computed_field(return_type=pd.Timedelta)
    def span(self) -> pd.Timedelta:
        step = self.frequency
        if step == pd.Timedelta(0):
            return pd.Timedelta(0)
        return step * len(self.time_index)

    def slice(self, count: int) -> "PriceTrajectory":
        if count <= 0:
            raise ValueError("slice count must be positive")
        if count > len(self.time_index):
            raise ValueError("slice count exceeds available trajectory samples")
        return type(self)(
            time_index=list(self.time_index[:count]),
            values=list(self.values[:count]),
            currency=self.currency,
            unit=self.unit,
            source=self.source,
        )

    def window(self, span: str | TimeSpan) -> "PriceTrajectoryWindow":
        return PriceTrajectoryWindow.from_trajectory(self, span)


class PriceTrajectoryWindow(PriceTrajectory):
    """Price trajectory slice representing the look-ahead window for a step."""

    @model_validator(mode="after")
    def _validate_window(self) -> "PriceTrajectoryWindow":
        if self.span <= pd.Timedelta(0):
            raise ValueError("PriceTrajectoryWindow span must be positive")
        return self

    @classmethod
    def from_trajectory(
        cls,
        trajectory: "PriceTrajectory",
        span: str | TimeSpan,
    ) -> "PriceTrajectoryWindow":
        window_span = (
            span.delta
            if isinstance(span, TimeSpan)
            else time_utils.normalize_timespan(span, None)
        )
        if window_span <= pd.Timedelta(0):
            raise ValueError("PriceTrajectoryWindow span must be positive")
        if trajectory.frequency == pd.Timedelta(0):
            count = 1
        else:
            ratio = window_span / trajectory.frequency
            count = int(math.ceil(float(ratio)))
        payload = trajectory.slice(count).model_dump(exclude={"start", "end", "span"})
        return cls(**payload)

    @classmethod
    def from_series(
        cls,
        trajectory: "PriceTrajectory",
        span: str | TimeSpan,
    ) -> "PriceTrajectoryWindow":
        return cls.from_trajectory(trajectory, span)


class BatteryState(StrictBaseModel):
    """Battery operating state at a point in time."""

    timestamp: datetime
    state_of_charge_kwh: float
    nominal_capacity_kwh: float
    available_charge_kw: float
    available_discharge_kw: float
    max_charge_kw: float
    max_discharge_kw: float
    thermal_state_c: float | None = None

    @model_validator(mode="after")
    def _validate_state(self) -> "BatteryState":
        if self.timestamp.tzinfo is None:
            raise ValueError("BatteryState.timestamp must be timezone-aware")
        if self.nominal_capacity_kwh <= 0:
            raise ValueError("BatteryState nominal_capacity_kwh must be positive")
        if not 0 <= self.state_of_charge_kwh <= self.nominal_capacity_kwh:
            raise ValueError("BatteryState state_of_charge_kwh must lie within [0, capacity]")
        if self.max_charge_kw < 0 or self.max_discharge_kw < 0:
            raise ValueError("BatteryState max charge/discharge must be non-negative")
        return self


class MockForecastMetadata(StrictBaseModel):
    currency: str
    unit: str
    component: str = "forecast"


class MockForecastConfig(StrictBaseModel):
    name: str
    seed: int | None = None
    noise_std_dev: float = 0.0
    lookahead: TimeSpan
    window_span: TimeSpan

    @model_validator(mode="after")
    def _validate_config(self) -> "MockForecastConfig":
        if self.noise_std_dev < 0:
            raise ValueError("MockForecastConfig.noise_std_dev must be non-negative")
        if self.lookahead.delta <= pd.Timedelta(0):
            raise ValueError("MockForecastConfig.lookahead must be positive")
        if self.window_span.delta <= pd.Timedelta(0):
            raise ValueError("MockForecastConfig.window_span must be positive")
        return self


class MockForecastPoint(StrictBaseModel):
    outer_index: int
    issued_at: datetime
    timestamps: Tuple[datetime, ...]
    values: Tuple[float, ...]
    metadata: MockForecastMetadata

    @model_validator(mode="after")
    def _validate_point(self) -> "MockForecastPoint":
        if self.issued_at.tzinfo is None:
            raise ValueError("MockForecastPoint.issued_at must be timezone-aware")
        if len(self.timestamps) != len(self.values):
            raise ValueError("MockForecastPoint timestamps and values must be the same length")
        for ts in self.timestamps:
            if ts.tzinfo is None:
                raise ValueError("MockForecastPoint timestamps must be timezone-aware")
        return self


class MockForecastSeries(StrictBaseModel):
    series: Tuple[MockForecastPoint, ...]

    @computed_field(return_type=Tuple[int, ...])
    def outer_indices(self) -> Tuple[int, ...]:
        return tuple(point.outer_index for point in self.series)


class GuidanceMetadata(StrictBaseModel):
    component: str = "guidance"


class GuidanceConfig(StrictBaseModel):
    strategy: str
    target_soc_min: float
    target_soc_max: float
    ramp_limit_kw_per_step: float
    setpoint_increment_kw: float

    @model_validator(mode="after")
    def _validate_guidance(self) -> "GuidanceConfig":
        if not 0 <= self.target_soc_min <= 1:
            raise ValueError("GuidanceConfig.target_soc_min must be within [0, 1]")
        if not 0 < self.target_soc_max <= 1:
            raise ValueError("GuidanceConfig.target_soc_max must be within (0, 1]")
        if self.target_soc_max <= self.target_soc_min:
            raise ValueError("GuidanceConfig target SOC bounds must be ordered")
        if self.ramp_limit_kw_per_step < 0:
            raise ValueError("GuidanceConfig.ramp_limit_kw_per_step must be non-negative")
        if self.setpoint_increment_kw <= 0:
            raise ValueError("GuidanceConfig.setpoint_increment_kw must be positive")
        return self


class SyncGuidance(StrictBaseModel):
    outer_index: int
    timestamp: datetime
    setpoint_kw: float
    metadata: GuidanceMetadata = GuidanceMetadata()

    @model_validator(mode="after")
    def _validate_guidance(self) -> "SyncGuidance":
        if self.timestamp.tzinfo is None:
            raise ValueError("SyncGuidance.timestamp must be timezone-aware")
        return self


class SyncGuidanceSeries(StrictBaseModel):
    series: Tuple[SyncGuidance, ...]

    @computed_field(return_type=Tuple[int, ...])
    def outer_indices(self) -> Tuple[int, ...]:
        return tuple(item.outer_index for item in self.series)


class DynamicSimConfig(StrictBaseModel):
    bridge: Literal["stub", "matlab"]
    fail_at_outer_step: int | None = None
    integration_step: TimeSpan
    telemetry_fields: Tuple[str, ...]

    @model_validator(mode="after")
    def _validate_config(self) -> "DynamicSimConfig":
        if self.integration_step.delta <= pd.Timedelta(0):
            raise ValueError("DynamicSimConfig.integration_step must be positive")
        if not self.telemetry_fields:
            raise ValueError("DynamicSimConfig.telemetry_fields must not be empty")
        return self


class DynamicsInitInput(StrictBaseModel):
    outer_step: SyncOuterStep
    state: BatteryState
    inner_index: Tuple[datetime, ...]


class DynamicsStepInput(StrictBaseModel):
    outer_step: SyncOuterStep
    guidance: SyncGuidance
    inner_index: Tuple[datetime, ...]


class SyncTelemetryFrame(StrictBaseModel):
    outer_index: int
    timestamp: datetime
    inner_times: Tuple[datetime, ...]
    soc_kwh: Tuple[float, ...]
    charge_in_kw: Tuple[float, ...]
    discharge_in_kw: Tuple[float, ...]

    @model_validator(mode="after")
    def _validate_frame(self) -> "SyncTelemetryFrame":
        if self.timestamp.tzinfo is None:
            raise ValueError("SyncTelemetryFrame.timestamp must be timezone-aware")
        if not (
            len(self.inner_times)
            == len(self.soc_kwh)
            == len(self.charge_in_kw)
            == len(self.discharge_in_kw)
        ):
            raise ValueError("SyncTelemetryFrame inner arrays must be identical lengths")
        for ts in self.inner_times:
            if ts.tzinfo is None:
                raise ValueError("SyncTelemetryFrame inner_times must be timezone-aware")
        return self


class SyncTelemetrySeries(StrictBaseModel):
    frames: Tuple[SyncTelemetryFrame, ...]

    @computed_field(return_type=Tuple[int, ...])
    def outer_indices(self) -> Tuple[int, ...]:
        return tuple(frame.outer_index for frame in self.frames)


def ensure_outer_indices_match(
    forecasts: MockForecastSeries,
    guidances: SyncGuidanceSeries,
    telemetry: SyncTelemetrySeries,
) -> None:
    """Ensure outer indices align across all synchronous simulation payloads."""

    expected = forecasts.outer_indices
    if guidances.outer_indices != expected or telemetry.outer_indices != expected:
        raise ValueError("Synchronous simulation series must share identical outer indices")


class SyncSimOutputs(StrictBaseModel):
    forecasts: MockForecastSeries
    guidances: SyncGuidanceSeries
    telemetry: SyncTelemetrySeries

    @model_validator(mode="after")
    def validate_alignment(self) -> "SyncSimOutputs":
        ensure_outer_indices_match(self.forecasts, self.guidances, self.telemetry)
        return self
