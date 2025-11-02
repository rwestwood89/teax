from __future__ import annotations

import pytest

from simkit.config import schema
from simkit.core.battery_config import ConfigureBatteryModule


def test_validate_rejects_non_kwh(load_profile_flat, rate_info_synth, design_prefs_default):
    module = ConfigureBatteryModule()
    bad_profile = load_profile_flat.model_copy(update={"unit": "MWh"})
    with pytest.raises(ValueError):
        module.validate_and_fill_default(bad_profile, rate_info_synth, design_prefs_default)


def test_validate_returns_inputs(load_profile_flat, rate_info_synth, design_prefs_default):
    module = ConfigureBatteryModule()
    validated = module.validate_and_fill_default(load_profile_flat, rate_info_synth, design_prefs_default)
    assert validated.load_profile == load_profile_flat
    assert validated.rate_info == rate_info_synth


def test_run_generates_reasonable_config(load_profile_flat, rate_info_synth, design_prefs_default):
    module = ConfigureBatteryModule()
    result = module.run(load_profile_flat, rate_info_synth, design_prefs_default).data
    assert isinstance(result, schema.BatteryConfig)
    assert result.capacity_kwh > 0
    assert result.soc_min < result.soc_max
    assert result.charge_kw_max <= result.power_kw
    assert result.discharge_kw_max <= result.power_kw


def test_run_rejects_invalid_inputs(load_profile_flat, rate_info_synth):
    module = ConfigureBatteryModule()
    bad_profile = load_profile_flat.model_copy(update={"unit": "MWh"})
    with pytest.raises(ValueError):
        module.run(bad_profile, rate_info_synth)
