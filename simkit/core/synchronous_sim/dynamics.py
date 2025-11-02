"""Dynamics bridges for the synchronous simulation module."""
from __future__ import annotations

from typing import Protocol

from ...config import schema


class DynamicsBridge(Protocol):
    """Interface for pluggable synchronous dynamics implementations."""

    def initialize(self, config: schema.DynamicSimConfig, init: schema.DynamicsInitInput) -> None: ...

    def step(self, payload: schema.DynamicsStepInput) -> schema.SyncTelemetryFrame: ...

    @property
    def current_state(self) -> schema.BatteryState: ...


class StubDynamicsBridge:
    """Deterministic dynamics bridge used for tests and demos."""

    def __init__(self, config: schema.DynamicSimConfig) -> None:
        self._config = config
        self._fail_at = config.fail_at_outer_step
        self._state: schema.BatteryState | None = None

    def initialize(self, config: schema.DynamicSimConfig, init: schema.DynamicsInitInput) -> None:
        self._state = init.state

    def step(self, payload: schema.DynamicsStepInput) -> schema.SyncTelemetryFrame:
        if self._state is None:
            raise RuntimeError("StubDynamicsBridge.initialize must be called before step")
        if self._fail_at is not None and payload.outer_step.index == self._fail_at:
            raise RuntimeError("stub dynamics failure requested")

        inner_times = payload.inner_index
        if not inner_times:
            raise ValueError("Dynamics inner loop must contain at least one sample")

        setpoint = payload.guidance.setpoint_kw
        capacity = self._state.nominal_capacity_kwh
        soc = self._state.state_of_charge_kwh

        outer_hours = payload.outer_step.duration.delta.total_seconds() / 3600.0
        samples = len(inner_times)
        delta_per_sample = setpoint * (outer_hours / samples)

        soc_values: list[float] = []
        charge_series: list[float] = []
        discharge_series: list[float] = []
        for _ in inner_times:
            soc = max(0.0, min(capacity, soc + delta_per_sample))
            soc_values.append(soc)
            if setpoint >= 0:
                charge_series.append(setpoint)
                discharge_series.append(0.0)
            else:
                charge_series.append(0.0)
                discharge_series.append(abs(setpoint))

        frame = schema.SyncTelemetryFrame(
            outer_index=payload.outer_step.index,
            timestamp=payload.outer_step.start,
            inner_times=inner_times,
            soc_kwh=tuple(soc_values),
            charge_in_kw=tuple(charge_series),
            discharge_in_kw=tuple(discharge_series),
        )

        self._state = schema.BatteryState(
            timestamp=payload.outer_step.end,
            state_of_charge_kwh=soc_values[-1],
            nominal_capacity_kwh=capacity,
            available_charge_kw=max(0.0, self._state.max_charge_kw - max(setpoint, 0.0)),
            available_discharge_kw=max(0.0, self._state.max_discharge_kw - max(-setpoint, 0.0)),
            max_charge_kw=self._state.max_charge_kw,
            max_discharge_kw=self._state.max_discharge_kw,
            thermal_state_c=self._state.thermal_state_c,
        )
        return frame

    @property
    def current_state(self) -> schema.BatteryState:
        if self._state is None:
            raise RuntimeError("StubDynamicsBridge has not been initialized")
        return self._state
