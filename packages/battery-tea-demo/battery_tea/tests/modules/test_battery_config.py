"""Tests for ConfigureBatteryModule."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from battery_tea import schemas
from battery_tea.defaults import default_design_prefs
from battery_tea.modules.battery_config import ConfigureBatteryModule


class TestConfigureBatteryModuleValidation:
    """Tests for validate_and_fill_default."""

    def test_complete_inputs_valid(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Complete inputs validate successfully."""
        module = ConfigureBatteryModule()
        prefs = default_design_prefs()
        inputs = module.validate_and_fill_default(load_profile_flat, rate_info_synth, prefs)

        assert inputs.load_profile == load_profile_flat
        assert inputs.rate_info == rate_info_synth
        assert inputs.design_prefs == prefs

    def test_fills_default_design_prefs(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Fills default design preferences when None provided."""
        module = ConfigureBatteryModule()
        inputs = module.validate_and_fill_default(load_profile_flat, rate_info_synth, None)

        assert inputs.design_prefs is not None
        assert inputs.design_prefs.target_peak_shaving_hours == 4.0

    def test_invalid_load_unit_raises(self):
        """Load profile with wrong unit raises ValidationError at schema level."""
        # Unit is a Literal["kWh"], so Pydantic validates this at construction
        # Generate a full year of hourly timestamps
        from datetime import timedelta
        base = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        time_index = [base + timedelta(hours=h) for h in range(8760)]

        with pytest.raises(ValidationError):
            schemas.LoadProfile8760(
                load_kwh=[100.0] * 8760,
                unit="MWh",  # Invalid: must be "kWh"
                time_index=time_index,
                source="test",
            )

    def test_rate_without_pricing_raises(
        self, load_profile_flat: schemas.LoadProfile8760
    ):
        """Rate info without pricing data raises ValueError."""
        module = ConfigureBatteryModule()
        bad_rate = schemas.RateInfo(
            energy_price_usd_per_kwh=None,
            tou_periods=None,
            tou_mapping_hourly=None,
            demand_charge_usd_per_kw=None,
            fixed_monthly_fee_usd=None,
            price_year=2024,
            currency="USD",
            vintage="2024",
            source="test",
            escalation_rules=None,
        )

        with pytest.raises(ValueError, match="energy pricing"):
            module.validate_and_fill_default(load_profile_flat, bad_rate)

    def test_invalid_soc_bounds_raises(self):
        """Design prefs with min_soc >= max_soc raises ValidationError at schema level."""
        # DesignPrefs has a model_validator that catches this
        with pytest.raises(ValidationError, match="max_soc must be greater than min_soc"):
            schemas.DesignPrefs(
                target_peak_shaving_hours=4.0,
                max_c_rate=0.5,
                min_soc=0.9,
                max_soc=0.1,  # Invalid: min >= max
            )


class TestConfigureBatteryModuleRun:
    """Tests for run method."""

    def test_run_produces_battery_config(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Run produces BatteryConfig."""
        module = ConfigureBatteryModule()
        result = module.run(load_profile_flat, rate_info_synth)

        assert result.data is not None
        config = result.data
        assert isinstance(config, schemas.BatteryConfig)

    def test_run_produces_positive_capacity(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Battery capacity is positive."""
        module = ConfigureBatteryModule()
        result = module.run(load_profile_flat, rate_info_synth)

        config = result.data
        assert config.capacity_kwh > 0

    def test_run_produces_valid_soc_bounds(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """SOC bounds are valid (0 <= min < max <= 1)."""
        module = ConfigureBatteryModule()
        result = module.run(load_profile_flat, rate_info_synth)

        config = result.data
        assert 0.0 <= config.soc_min < config.soc_max <= 1.0

    def test_run_produces_valid_efficiency(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Round-trip efficiency is in valid range."""
        module = ConfigureBatteryModule()
        result = module.run(load_profile_flat, rate_info_synth)

        config = result.data
        assert 0.0 < config.eta_roundtrip <= 1.0

    def test_run_respects_design_prefs(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Custom design preferences affect sizing."""
        module = ConfigureBatteryModule()

        prefs_small = schemas.DesignPrefs(
            target_peak_shaving_hours=2.0,
            max_c_rate=0.25,
            min_soc=0.2,
            max_soc=0.8,
        )
        prefs_large = schemas.DesignPrefs(
            target_peak_shaving_hours=8.0,
            max_c_rate=0.5,
            min_soc=0.1,
            max_soc=0.9,
        )

        result_small = module.run(load_profile_flat, rate_info_synth, prefs_small)
        result_large = module.run(load_profile_flat, rate_info_synth, prefs_large)

        # Larger peak shaving hours should result in larger capacity
        assert result_large.data.capacity_kwh > result_small.data.capacity_kwh

    def test_run_includes_notes(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Run includes execution notes."""
        module = ConfigureBatteryModule()
        result = module.run(load_profile_flat, rate_info_synth)

        assert result.notes is not None
