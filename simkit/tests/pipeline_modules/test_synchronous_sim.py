from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from simkit.config import schema
from simkit.core.synchronous_sim import SynchronousSimModule

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "synchronous_sim"


def _load_json(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _build_price_trajectory() -> schema.PriceTrajectory:
    payload = _load_json("actual_pricing.json")
    series = payload["series"]
    timestamps = [datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")) for item in series]
    values = [float(item["value"]) for item in series]
    return schema.PriceTrajectory(
        time_index=timestamps,
        values=values,
        currency=payload["currency"],
        unit=payload["unit"],
        source=payload.get("source"),
    )


def _build_inputs(dynamic_config_name: str = "dynamic_sim_config.json") -> dict:
    time_grid = schema.SyncTimeGrid(**_load_json("time_grid.json"))
    initial_state = schema.BatteryState(**_load_json("initial_state.json"))
    price_trajectory = _build_price_trajectory()
    forecast_config = schema.MockForecastConfig(**_load_json("forecast_config.json"))
    guidance_config = schema.GuidanceConfig(**_load_json("guidance_config.json"))
    dynamics_config = schema.DynamicSimConfig(**_load_json(dynamic_config_name))
    return {
        "time_grid": time_grid,
        "initial_state": initial_state,
        "price_trajectory": price_trajectory,
        "forecast_config": forecast_config,
        "guidance_config": guidance_config,
        "dynamics_config": dynamics_config,
    }


def test_module_loop_happy_path():
    module = SynchronousSimModule()
    inputs = _build_inputs()
    result = module.run(**inputs)

    outputs = result.data
    bundle = outputs["synchronous_sim"]
    assert isinstance(bundle, schema.SyncSimOutputs)
    assert len(outputs["telemetry"].frames) == len(inputs["time_grid"].outer_steps)
    assert outputs["guidances"].series[0].setpoint_kw == pytest.approx(0.0)
    assert outputs["forecasts"].series[0].metadata.currency == "USD"
    assert outputs["telemetry"].frames[0].inner_times[0].tzinfo is not None


def test_module_annotates_failures():
    module = SynchronousSimModule()

    with pytest.raises(ValueError) as exc:
        module.run(**_build_inputs("dynamic_sim_config_failure.json"))

    message = str(exc.value)
    assert "[component=dynamics]" in message
    assert "outer_index=2" in message
