from __future__ import annotations

import numpy as np
import pytest

from simkit.config import defaults, schema
from simkit.core.perf_sim_simple import SimplePerformanceSimModule


def test_validate_rejects_time_mismatch(load_profile_flat, rate_info_synth):
    module = SimplePerformanceSimModule()
    pv_profile = schema.PVProfile8760(
        time_index=defaults.default_time_index(2024, "UTC"),
        production_kwh=[0.0] * 8760,
        source="pv",
    )
    bad_pv = pv_profile.model_copy(update={"time_index": pv_profile.time_index[::-1]})
    with pytest.raises(ValueError):
        module.validate_and_fill_default(_sample_battery_config(), load_profile_flat, bad_pv, rate_info_synth)


def test_run_generates_valid_telemetry(load_profile_flat, rate_info_synth):
    module = SimplePerformanceSimModule()
    telemetry = module.run(_sample_battery_config(), load_profile_flat, None, rate_info_synth).data
    assert len(telemetry.charge_in_kwh) == 8760
    assert len(telemetry.discharge_out_kwh) == 8760
    assert len(telemetry.soc_kwh) == 8760
    soc_array = np.array(telemetry.soc_kwh)
    battery = _sample_battery_config()
    min_soc_bound = battery.capacity_kwh * battery.soc_min
    max_soc_bound = battery.capacity_kwh * battery.soc_max
    assert soc_array.min() >= min_soc_bound - 1e-3
    assert soc_array.max() <= max_soc_bound + 1e-3
    assert np.max(telemetry.charge_in_kwh) <= battery.charge_kw_max + 1e-6
    assert np.max(telemetry.discharge_out_kwh) <= battery.discharge_kw_max + 1e-6


def test_run_rejects_invalid_inputs(load_profile_flat, rate_info_synth):
    module = SimplePerformanceSimModule()
    bad_battery = _sample_battery_config().model_copy(update={"soc_min": 0.95})
    with pytest.raises(ValueError):
        module.run(bad_battery, load_profile_flat, None, rate_info_synth)


def _sample_battery_config() -> schema.BatteryConfig:
    return schema.BatteryConfig(
        capacity_kwh=120.0,
        power_kw=60.0,
        charge_kw_max=60.0,
        discharge_kw_max=60.0,
        eta_roundtrip=0.9,
        soc_min=0.1,
        soc_max=0.9,
        lifecycle_warranty_cycles=4000,
        lifecycle_warranty_years=10,
        notes="",
        rationale="",
    )
