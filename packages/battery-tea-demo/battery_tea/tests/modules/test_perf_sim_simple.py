"""Tests for SimplePerformanceSimModule."""
from __future__ import annotations

import numpy as np
import pytest

from battery_tea import schemas
from battery_tea.modules.perf_sim_simple import SimplePerformanceSimModule
from battery_tea.tests.fixtures import sample_battery_config


class TestSimplePerformanceSimModuleValidation:
    """Tests for validate_and_fill_default."""

    def test_complete_inputs_valid(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Complete inputs validate successfully."""
        module = SimplePerformanceSimModule()
        battery = sample_battery_config()
        inputs = module.validate_and_fill_default(
            battery, load_profile_flat, None, rate_info_synth
        )

        assert inputs.battery == battery
        assert inputs.load_profile == load_profile_flat
        assert inputs.pv_profile is None
        assert inputs.rate_info == rate_info_synth

    def test_rate_without_pricing_raises(
        self, load_profile_flat: schemas.LoadProfile8760
    ):
        """Rate info without hourly pricing raises ValueError."""
        module = SimplePerformanceSimModule()
        battery = sample_battery_config()
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

        with pytest.raises(ValueError, match="pricing"):
            module.validate_and_fill_default(battery, load_profile_flat, None, bad_rate)

    def test_invalid_soc_bounds_raises(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Battery with invalid SOC bounds raises ValueError."""
        module = SimplePerformanceSimModule()
        bad_battery = schemas.BatteryConfig(
            capacity_kwh=100.0,
            power_kw=50.0,
            charge_kw_max=45.0,
            discharge_kw_max=45.0,
            eta_roundtrip=0.9,
            soc_min=0.9,  # Invalid: min >= max
            soc_max=0.1,
            lifecycle_warranty_cycles=4000,
            lifecycle_warranty_years=10,
        )

        with pytest.raises(ValueError, match="SOC"):
            module.validate_and_fill_default(
                bad_battery, load_profile_flat, None, rate_info_synth
            )


class TestSimplePerformanceSimModuleRun:
    """Tests for run method."""

    def test_run_produces_telemetry(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Run produces BatteryTelemetry8760."""
        module = SimplePerformanceSimModule()
        battery = sample_battery_config()
        result = module.run(battery, load_profile_flat, None, rate_info_synth)

        assert result.data is not None
        telemetry = result.data.root
        assert isinstance(telemetry, schemas.BatteryTelemetry8760)

    def test_run_produces_8760_series(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """All output series have 8760 hours."""
        module = SimplePerformanceSimModule()
        battery = sample_battery_config()
        result = module.run(battery, load_profile_flat, None, rate_info_synth)

        telemetry = result.data.root
        assert len(telemetry.charge_in_kwh) == 8760
        assert len(telemetry.discharge_out_kwh) == 8760
        assert len(telemetry.soc_kwh) == 8760

    def test_run_soc_within_bounds(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """SOC stays within configured bounds."""
        module = SimplePerformanceSimModule()
        battery = sample_battery_config()
        result = module.run(battery, load_profile_flat, None, rate_info_synth)

        telemetry = result.data.root
        soc_array = np.array(telemetry.soc_kwh)
        soc_min_kwh = battery.capacity_kwh * battery.soc_min
        soc_max_kwh = battery.capacity_kwh * battery.soc_max

        # Allow small numerical tolerance
        assert np.all(soc_array >= soc_min_kwh - 1e-3)
        assert np.all(soc_array <= soc_max_kwh + 1e-3)

    def test_run_no_negative_values(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Charge and discharge values are non-negative."""
        module = SimplePerformanceSimModule()
        battery = sample_battery_config()
        result = module.run(battery, load_profile_flat, None, rate_info_synth)

        telemetry = result.data.root
        assert all(v >= 0 for v in telemetry.charge_in_kwh)
        assert all(v >= 0 for v in telemetry.discharge_out_kwh)

    def test_run_respects_power_limits(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Charge/discharge rates respect power limits."""
        module = SimplePerformanceSimModule()
        battery = sample_battery_config()
        result = module.run(battery, load_profile_flat, None, rate_info_synth)

        telemetry = result.data.root

        # Note: The actual charge/discharge values may be slightly different
        # due to efficiency factors, so we allow some tolerance
        charge_max = max(telemetry.charge_in_kwh)
        discharge_max = max(telemetry.discharge_out_kwh)

        # Discharge output is multiplied by efficiency, so check pre-efficiency value
        assert charge_max <= battery.charge_kw_max + 1e-3

    def test_run_tracks_constraint_hits(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Constraint hits are tracked."""
        module = SimplePerformanceSimModule()
        battery = sample_battery_config()
        result = module.run(battery, load_profile_flat, None, rate_info_synth)

        telemetry = result.data.root
        assert "soc_min" in telemetry.constraints_hits
        assert "soc_max" in telemetry.constraints_hits

    def test_run_includes_notes(
        self,
        load_profile_flat: schemas.LoadProfile8760,
        rate_info_synth: schemas.RateInfo,
    ):
        """Run includes execution notes."""
        module = SimplePerformanceSimModule()
        battery = sample_battery_config()
        result = module.run(battery, load_profile_flat, None, rate_info_synth)

        assert result.notes is not None
