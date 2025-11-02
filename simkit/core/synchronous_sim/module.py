"""Synchronous simulation module orchestrating forecast, guidance, and dynamics."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Mapping

from ...config import schema, time_utils
from ..base import ModuleBase, ModuleResult
from .dynamics import DynamicsBridge, StubDynamicsBridge
from .forecast import MockForecastComponent
from .guidance import GuidanceComponent


@dataclass(frozen=True)
class SynchronousSimInputs:
    time_grid: schema.SyncTimeGrid
    initial_state: schema.BatteryState
    actual_pricing: schema.PriceTrajectory
    forecast_config: schema.MockForecastConfig
    guidance_config: schema.GuidanceConfig
    dynamic_sim_config: schema.DynamicSimConfig
    dynamics_bridge: DynamicsBridge


class SynchronousSimModule(
    ModuleBase[SynchronousSimInputs, Dict[str, schema.StrictBaseModel]]
):
    """Pipeline module coordinating synchronous simulation subcomponents."""

    name = "synchronous_sim"
    version = "v0.1"

    def validate_and_fill_default(
        self,
        *,
        time_grid: schema.SyncTimeGrid | Mapping[str, object],
        initial_state: schema.BatteryState | Mapping[str, object],
        price_trajectory: schema.PriceTrajectory | Mapping[str, object],
        forecast_config: schema.MockForecastConfig | Mapping[str, object],
        guidance_config: schema.GuidanceConfig | Mapping[str, object],
        dynamics_config: schema.DynamicSimConfig | Mapping[str, object],
        dynamics_override: DynamicsBridge | None = None,
    ) -> SynchronousSimInputs:
        grid = self._coerce_model(time_grid, schema.SyncTimeGrid)
        state = self._coerce_model(initial_state, schema.BatteryState)
        pricing = self._coerce_price_trajectory(price_trajectory)
        forecast = self._coerce_model(forecast_config, schema.MockForecastConfig)
        guidance = self._coerce_model(guidance_config, schema.GuidanceConfig)
        dynamics = self._coerce_model(dynamics_config, schema.DynamicSimConfig)

        inner_loop = self._get_dynamics_loop(grid)
        if inner_loop.step.delta != dynamics.integration_step.delta:
            raise ValueError(
                "Dynamics integration step must match the dynamics inner loop cadence"
            )

        bridge = dynamics_override or self._resolve_bridge(dynamics)
        return SynchronousSimInputs(
            time_grid=grid,
            initial_state=state,
            actual_pricing=pricing,
            forecast_config=forecast,
            guidance_config=guidance,
            dynamic_sim_config=dynamics,
            dynamics_bridge=bridge,
        )

    def run(
        self,
        *,
        time_grid: schema.SyncTimeGrid | Mapping[str, object],
        initial_state: schema.BatteryState | Mapping[str, object],
        price_trajectory: schema.PriceTrajectory | Mapping[str, object],
        forecast_config: schema.MockForecastConfig | Mapping[str, object],
        guidance_config: schema.GuidanceConfig | Mapping[str, object],
        dynamics_config: schema.DynamicSimConfig | Mapping[str, object],
        dynamics_override: DynamicsBridge | None = None,
    ) -> ModuleResult[Dict[str, schema.StrictBaseModel]]:
        inputs = self.validate_and_fill_default(
            time_grid=time_grid,
            initial_state=initial_state,
            price_trajectory=price_trajectory,
            forecast_config=forecast_config,
            guidance_config=guidance_config,
            dynamics_config=dynamics_config,
            dynamics_override=dynamics_override,
        )

        forecast_component = MockForecastComponent(
            inputs.forecast_config, inputs.actual_pricing
        )
        guidance_component = GuidanceComponent(inputs.guidance_config)

        forecast_component.initialize(inputs.time_grid)
        guidance_component.initialize(inputs.initial_state)

        dynamics_loop = self._get_dynamics_loop(inputs.time_grid)
        bridge = inputs.dynamics_bridge

        forecasts: list[schema.MockForecastPoint] = []
        guidances: list[schema.SyncGuidance] = []
        telemetry_frames: list[schema.SyncTelemetryFrame] = []

        current_state = inputs.initial_state
        for idx, step in enumerate(inputs.time_grid.outer_steps):
            inner_index = self._build_inner_index(step, dynamics_loop)
            if idx == 0:
                init_payload = schema.DynamicsInitInput(
                    outer_step=step,
                    state=current_state,
                    inner_index=inner_index,
                )
                self._call_with_context(
                    "dynamics",
                    step,
                    bridge.initialize,
                    inputs.dynamic_sim_config,
                    init_payload,
                )

            forecast_point = self._call_with_context(
                "forecast",
                step,
                forecast_component.step,
                step,
            )
            guidance = self._call_with_context(
                "guidance",
                step,
                guidance_component.step,
                step,
                forecast_point,
                current_state,
            )

            dynamics_payload = schema.DynamicsStepInput(
                outer_step=step,
                guidance=guidance,
                inner_index=inner_index,
            )
            telemetry = self._call_with_context(
                "dynamics",
                step,
                bridge.step,
                dynamics_payload,
            )

            forecasts.append(forecast_point)
            guidances.append(guidance)
            telemetry_frames.append(telemetry)
            current_state = bridge.current_state

        bundle = schema.SyncSimOutputs(
            forecasts=schema.MockForecastSeries(series=tuple(forecasts)),
            guidances=schema.SyncGuidanceSeries(series=tuple(guidances)),
            telemetry=schema.SyncTelemetrySeries(frames=tuple(telemetry_frames)),
        )
        result_payload: Dict[str, schema.StrictBaseModel] = {
            "synchronous_sim": bundle,
            "forecasts": bundle.forecasts,
            "guidances": bundle.guidances,
            "telemetry": bundle.telemetry,
        }
        return ModuleResult(result_payload, notes="Synchronous simulation completed")

    # ------------------------------------------------------------------
    # Helpers

    def _coerce_model(self, value, model_cls):
        if isinstance(value, model_cls):
            return value
        if isinstance(value, Mapping):
            return model_cls(**value)
        raise TypeError(f"Unsupported payload for {model_cls.__name__}: {type(value)!r}")

    def _coerce_price_trajectory(
        self, value: schema.PriceTrajectory | Mapping[str, object]
    ) -> schema.PriceTrajectory:
        if isinstance(value, schema.PriceTrajectory):
            return value
        if not isinstance(value, Mapping):
            raise TypeError(
                f"Unsupported payload for PriceTrajectory: {type(value)!r}"
            )
        payload = dict(value)
        if "series" in payload:
            series = payload["series"]
            timestamps = [self._ensure_datetime(entry["timestamp"]) for entry in series]
            values = [float(entry["value"]) for entry in series]
            currency = payload.get("currency")
            unit = payload.get("unit")
            if currency is None or unit is None:
                raise ValueError(
                    "Price trajectory series payload must include 'currency' and 'unit'"
                )
            source = payload.get("source")
            return schema.PriceTrajectory(
                time_index=timestamps,
                values=values,
                currency=currency,
                unit=unit,
                source=source,
            )
        if "time_index" in payload and "values" in payload:
            timestamps = [self._ensure_datetime(ts) for ts in payload["time_index"]]
            values = [float(val) for val in payload["values"]]
            currency = payload.get("currency")
            unit = payload.get("unit")
            if currency is None or unit is None:
                raise ValueError("Price trajectory payload requires 'currency' and 'unit'")
            source = payload.get("source")
            return schema.PriceTrajectory(
                time_index=timestamps,
                values=values,
                currency=currency,
                unit=unit,
                source=source,
            )
        raise ValueError("Price trajectory payload must include either 'series' or 'time_index'/'values'")

    def _ensure_datetime(self, value: object) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("Datetime values must be timezone-aware")
            return value
        if isinstance(value, str):
            iso = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(iso)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        raise TypeError(f"Unsupported timestamp value: {value!r}")

    def _resolve_bridge(self, config: schema.DynamicSimConfig) -> DynamicsBridge:
        if config.bridge != "stub":
            raise ValueError(
                "DynamicSimConfig.bridge must be 'stub' in the current implementation"
            )
        return StubDynamicsBridge(config)

    def _get_dynamics_loop(self, time_grid: schema.SyncTimeGrid) -> schema.InnerLoopConfig:
        for config in time_grid.inner_loops:
            if config.component.lower() == "dynamics":
                return config
        raise ValueError("SyncTimeGrid must declare a 'dynamics' inner loop")

    def _build_inner_index(
        self, outer_step: schema.SyncOuterStep, config: schema.InnerLoopConfig
    ) -> tuple[datetime, ...]:
        index = time_utils.build_inner_index(outer_step, config)
        return tuple(
            ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts  # type: ignore[attr-defined]
            for ts in index
        )

    def _call_with_context(
        self,
        component: str,
        outer_step: schema.SyncOuterStep,
        func,
        *args,
        **kwargs,
    ):
        # Simple wrapper just to standardize error messages
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised via tests
            message = self._format_error(component, outer_step, str(exc))
            raise ValueError(message) from exc

    def _format_error(self, component: str, outer_step: schema.SyncOuterStep, message: str) -> str:
        timestamp = outer_step.start.isoformat()
        return (
            f"[component={component}][outer_index={outer_step.index}]"
            f"[timestamp={timestamp}] {message}"
        )
