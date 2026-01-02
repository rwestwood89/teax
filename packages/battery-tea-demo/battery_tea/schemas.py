"""Battery TEA schema types.

This module contains battery domain-specific schemas for the battery TEA demo.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import (
    Field,
    PositiveFloat,
    field_validator,
    model_validator,
)

from simkit.config.schema import (
    GuidanceMetadata,
    MockForecastSeries,
    MultiOutput,
    StrictBaseModel,
    SyncGuidance,
    SyncGuidanceSeries,
    SyncOuterStep,
)


class Geography(StrictBaseModel):
    country: str
    region: Optional[str] = None
    utility: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None


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
    target_peak_shaving_hours: Optional[PositiveFloat] = None
    max_c_rate: Optional[PositiveFloat] = None
    min_soc: Optional[float] = None
    max_soc: Optional[float] = None
    eta_roundtrip: Optional[float] = None
    safety_margins: Optional[Dict[str, float]] = None

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
    lifecycle_warranty_cycles: Optional[int] = None
    lifecycle_warranty_years: Optional[int] = None
    notes: Optional[str] = None
    rationale: Optional[str] = None
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


class DynamicsInitInput(StrictBaseModel):
    outer_step: SyncOuterStep
    state: BatteryState
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

    @property
    def outer_indices(self) -> Tuple[int, ...]:
        return tuple(frame.outer_index for frame in self.frames)


class SyncSimOutputs(MultiOutput):
    """Synchronous simulation output container with alignment validation."""

    forecasts: MockForecastSeries
    guidances: SyncGuidanceSeries
    telemetry: SyncTelemetrySeries

    @model_validator(mode="after")
    def validate_alignment(self) -> "SyncSimOutputs":
        expected = self.forecasts.outer_indices
        if self.guidances.outer_indices != expected or self.telemetry.outer_indices != expected:
            raise ValueError("Synchronous simulation series must share identical outer indices")
        return self
