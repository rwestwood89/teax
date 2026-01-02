"""Tests for CostCalculatorModule."""
from __future__ import annotations

import pytest

from battery_tea import schemas
from battery_tea.modules.cost_calc import CostCalculatorModule
from battery_tea.tests.fixtures import sample_battery_config


class TestCostCalculatorModuleValidation:
    """Tests for validate_and_fill_default."""

    def test_complete_inputs_valid(self, geography_us_ca: schemas.Geography):
        """Complete inputs validate successfully."""
        module = CostCalculatorModule()
        battery = sample_battery_config()
        inputs = module.validate_and_fill_default(battery, geography_us_ca)

        assert inputs.battery == battery
        assert inputs.geography == geography_us_ca

    def test_non_us_geography_raises(self):
        """Non-US geography raises ValueError."""
        module = CostCalculatorModule()
        battery = sample_battery_config()
        bad_geo = schemas.Geography(country="FR", region=None, utility=None)

        with pytest.raises(ValueError, match="US only"):
            module.validate_and_fill_default(battery, bad_geo)

    def test_non_usd_currency_raises(self):
        """Non-USD currency raises ValueError."""
        module = CostCalculatorModule()
        battery = sample_battery_config()
        bad_geo = schemas.Geography(country="US", region="CA", utility="Test", currency="EUR")

        with pytest.raises(ValueError, match="USD"):
            module.validate_and_fill_default(battery, bad_geo)

    def test_dict_input_coerced(self, geography_us_ca: schemas.Geography):
        """Dict inputs are coerced to models."""
        module = CostCalculatorModule()
        battery_dict = {
            "capacity_kwh": 100.0,
            "power_kw": 50.0,
            "charge_kw_max": 45.0,
            "discharge_kw_max": 45.0,
            "eta_roundtrip": 0.9,
            "soc_min": 0.1,
            "soc_max": 0.9,
            "lifecycle_warranty_cycles": 6000,
            "lifecycle_warranty_years": 10,
        }
        inputs = module.validate_and_fill_default(battery_dict, geography_us_ca)

        assert isinstance(inputs.battery, schemas.BatteryConfig)


class TestCostCalculatorModuleRun:
    """Tests for run method."""

    def test_run_produces_cost_breakdown(self, geography_us_ca: schemas.Geography):
        """Run produces CostBreakdown."""
        module = CostCalculatorModule()
        battery = sample_battery_config()
        result = module.run(battery, geography_us_ca)

        assert result.data is not None
        breakdown = result.data
        assert isinstance(breakdown, schemas.CostBreakdown)

    def test_run_produces_positive_capex(self, geography_us_ca: schemas.Geography):
        """CAPEX total is positive."""
        module = CostCalculatorModule()
        battery = sample_battery_config()
        result = module.run(battery, geography_us_ca)

        breakdown = result.data
        assert breakdown.capex_total > 0

    def test_run_produces_line_items(self, geography_us_ca: schemas.Geography):
        """Cost breakdown includes line items."""
        module = CostCalculatorModule()
        battery = sample_battery_config()
        result = module.run(battery, geography_us_ca)

        breakdown = result.data
        assert len(breakdown.line_items) > 0

        # Should include battery modules and inverter
        names = [item.name for item in breakdown.line_items]
        assert any("Battery" in name for name in names)
        assert any("Inverter" in name or "PCS" in name for name in names)

    def test_run_produces_annual_om(self, geography_us_ca: schemas.Geography):
        """Annual O&M cost is calculated."""
        module = CostCalculatorModule()
        battery = sample_battery_config()
        result = module.run(battery, geography_us_ca)

        breakdown = result.data
        assert breakdown.annual_om_usd > 0

    def test_run_scales_with_capacity(self, geography_us_ca: schemas.Geography):
        """Larger battery capacity results in higher costs."""
        module = CostCalculatorModule()

        small_battery = schemas.BatteryConfig(
            capacity_kwh=50.0,
            power_kw=25.0,
            charge_kw_max=25.0,
            discharge_kw_max=25.0,
            eta_roundtrip=0.9,
            soc_min=0.1,
            soc_max=0.9,
            lifecycle_warranty_cycles=4000,
            lifecycle_warranty_years=10,
        )
        large_battery = schemas.BatteryConfig(
            capacity_kwh=200.0,
            power_kw=100.0,
            charge_kw_max=100.0,
            discharge_kw_max=100.0,
            eta_roundtrip=0.9,
            soc_min=0.1,
            soc_max=0.9,
            lifecycle_warranty_cycles=4000,
            lifecycle_warranty_years=10,
        )

        result_small = module.run(small_battery, geography_us_ca)
        result_large = module.run(large_battery, geography_us_ca)

        assert result_large.data.capex_total > result_small.data.capex_total

    def test_run_applies_regional_multiplier(self):
        """California region applies higher regional multiplier."""
        module = CostCalculatorModule()
        battery = sample_battery_config()

        geo_ca = schemas.Geography(country="US", region="CA", utility="PG&E")
        geo_tx = schemas.Geography(country="US", region="TX", utility="Oncor")

        result_ca = module.run(battery, geo_ca)
        result_tx = module.run(battery, geo_tx)

        # CA has higher multiplier (1.18) vs TX default (~1.05)
        assert result_ca.data.capex_total > result_tx.data.capex_total

    def test_run_includes_notes(self, geography_us_ca: schemas.Geography):
        """Run includes execution notes."""
        module = CostCalculatorModule()
        battery = sample_battery_config()
        result = module.run(battery, geography_us_ca)

        assert result.notes is not None
