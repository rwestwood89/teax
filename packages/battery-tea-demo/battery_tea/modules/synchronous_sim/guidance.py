"""Guidance component for the synchronous simulation module."""
from __future__ import annotations

from dataclasses import dataclass

from simkit.config import schema

from ... import schemas


@dataclass
class GuidanceComponent:
    """Simple heuristic guidance component obeying SOC bounds and ramp limits."""

    config: schemas.GuidanceConfig

    def __post_init__(self) -> None:
        self._capacity_kwh: float | None = None
        self._previous_setpoint: float = 0.0

    def initialize(self, initial_state: schemas.BatteryState) -> None:
        self._capacity_kwh = initial_state.nominal_capacity_kwh
        self._previous_setpoint = 0.0

    def step(
        self,
        outer_step: schema.SyncOuterStep,
        forecast_point: schema.MockForecastPoint,
        current_state: schemas.BatteryState,
    ) -> schema.SyncGuidance:
        if self._capacity_kwh is None:
            raise RuntimeError("GuidanceComponent.initialize must be invoked before step")

        target_min = self.config.target_soc_min * self._capacity_kwh
        target_max = self.config.target_soc_max * self._capacity_kwh
        soc = current_state.state_of_charge_kwh

        desired = self._previous_setpoint
        if self.config.strategy == "hold_zero":
            desired = 0.0
        elif soc < target_min:
            desired = self._previous_setpoint + self.config.setpoint_increment_kw
        elif soc > target_max:
            desired = self._previous_setpoint - self.config.setpoint_increment_kw
        else:
            desired = 0.0

        ramp_limit = self.config.ramp_limit_kw_per_step
        delta = desired - self._previous_setpoint
        if delta > ramp_limit:
            desired = self._previous_setpoint + ramp_limit
        elif delta < -ramp_limit:
            desired = self._previous_setpoint - ramp_limit

        self._previous_setpoint = desired
        return schema.SyncGuidance(
            outer_index=outer_step.index,
            timestamp=outer_step.start,
            setpoint_kw=float(desired),
        )
