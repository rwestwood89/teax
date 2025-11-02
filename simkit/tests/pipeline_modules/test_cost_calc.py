from __future__ import annotations

import pytest

from simkit.config import schema
from simkit.core.cost_calc import CostCalculatorModule


def test_validate_rejects_non_us(geography_us_ca, load_profile_flat, rate_info_synth, design_prefs_default):
    module = CostCalculatorModule()
    battery = schema.BatteryConfig(
        capacity_kwh=100.0,
        power_kw=50.0,
        charge_kw_max=50.0,
        discharge_kw_max=50.0,
        eta_roundtrip=0.9,
        soc_min=0.1,
        soc_max=0.9,
        lifecycle_warranty_cycles=4000,
        lifecycle_warranty_years=10,
        notes="",
        rationale="",
    )
    foreign_geo = geography_us_ca.model_copy(update={"country": "DE", "currency": "EUR"})
    with pytest.raises(ValueError):
        module.validate_and_fill_default(battery, foreign_geo)


def test_run_produces_consistent_totals(geography_us_ca):
    module = CostCalculatorModule()
    battery = schema.BatteryConfig(
        capacity_kwh=120.0,
        power_kw=60.0,
        charge_kw_max=60.0,
        discharge_kw_max=60.0,
        eta_roundtrip=0.92,
        soc_min=0.1,
        soc_max=0.9,
        lifecycle_warranty_cycles=4000,
        lifecycle_warranty_years=10,
        notes="",
        rationale="",
    )
    breakdown = module.run(battery, geography_us_ca).data
    total_line_items = sum(item.cost for item in breakdown.line_items)
    assert pytest.approx(total_line_items, rel=1e-5) == breakdown.capex_total
    assert breakdown.currency == "USD"


def test_run_rejects_invalid_geo(geography_us_ca):
    module = CostCalculatorModule()
    battery = schema.BatteryConfig(
        capacity_kwh=120.0,
        power_kw=60.0,
        charge_kw_max=60.0,
        discharge_kw_max=60.0,
        eta_roundtrip=0.92,
        soc_min=0.1,
        soc_max=0.9,
        lifecycle_warranty_cycles=4000,
        lifecycle_warranty_years=10,
        notes="",
        rationale="",
    )
    bad_geo = geography_us_ca.model_copy(update={"currency": "EUR", "country": "DE"})
    with pytest.raises(ValueError):
        module.run(battery, bad_geo)
