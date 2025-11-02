from __future__ import annotations

import pytest

from simkit.config import defaults, schema
from simkit.core.project_analyzer import ProjectAnalyzerModule


def _sample_cost_breakdown() -> schema.CostBreakdown:
    line_items = [
        schema.CostLineItem(
            name="Battery Modules",
            basis="per_kwh",
            unit_cost=350.0,
            qty=100.0,
            cost=35000.0,
            currency="USD",
        )
    ]
    return schema.CostBreakdown(
        line_items=line_items,
        capex_total=35000.0,
        annual_om_usd=500.0,
        price_year=2024,
        assumptions={"note": "test"},
        currency="USD",
    )


def _sample_telemetry() -> schema.BatteryTelemetry8760:
    charge = [0.5] * 8760
    discharge = [0.45] * 8760
    soc = [50.0] * 8760
    return schema.BatteryTelemetry8760(
        charge_in_kwh=charge,
        discharge_out_kwh=discharge,
        soc_kwh=soc,
        constraints_hits={"soc_min": 0, "soc_max": 0},
        method=defaults.DEFAULT_METHOD,
    )


def test_validate_rejects_missing_pricing(financial_params_demo):
    module = ProjectAnalyzerModule()
    telemetry = _sample_telemetry()
    bad_rate = schema.RateInfo(
        energy_price_usd_per_kwh=None,
        tou_periods=None,
        tou_mapping_hourly=None,
        demand_charge_usd_per_kw=None,
        fixed_monthly_fee_usd=None,
        price_year=2024,
        currency="USD",
        vintage="2024",
        source="",
        escalation_rules=None,
    )
    with pytest.raises(ValueError):
        module.validate_and_fill_default(bad_rate, telemetry, financial_params_demo, _sample_cost_breakdown())


def test_run_generates_financial_results(rate_info_synth, financial_params_demo):
    module = ProjectAnalyzerModule()
    telemetry = _sample_telemetry()
    results = module.run(rate_info_synth, telemetry, financial_params_demo, _sample_cost_breakdown()).data
    assert isinstance(results, schema.FinancialResults)
    assert results.annual_savings < 0
    ledger_total = sum(entry.amount for entry in results.ledger)
    assert pytest.approx(ledger_total, rel=1e-5) == results.annual_savings - 500.0 - 35000.0


def test_run_requires_cost_inputs(rate_info_synth):
    module = ProjectAnalyzerModule()
    telemetry = _sample_telemetry()
    params = defaults.default_financial_params()
    with pytest.raises(ValueError):
        module.run(rate_info_synth, telemetry, params, None)
