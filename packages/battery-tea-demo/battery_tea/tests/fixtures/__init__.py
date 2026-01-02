"""Battery TEA test fixtures and sample data builders."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from battery_tea import schemas
from simkit.config import schema


def sample_rate_info() -> schemas.RateInfo:
    """Create sample rate info for testing."""
    return schemas.RateInfo(
        energy_price_usd_per_kwh=None,
        tou_periods=None,
        tou_mapping_hourly=None,
        demand_charge_usd_per_kw=None,
        fixed_monthly_fee_usd=None,
        price_year=2024,
        currency="USD",
        vintage="2024",
        source="unit-test",
        escalation_rules=None,
    )


def sample_battery_config() -> schemas.BatteryConfig:
    """Create sample battery config for testing."""
    return schemas.BatteryConfig(
        capacity_kwh=100.0,
        power_kw=50.0,
        charge_kw_max=45.0,
        discharge_kw_max=45.0,
        eta_roundtrip=0.9,
        soc_min=0.1,
        soc_max=0.9,
        lifecycle_warranty_cycles=6000,
        lifecycle_warranty_years=10,
        notes="unit-test",
        rationale="unit-test",
    )


def sample_cost_breakdown() -> schemas.CostBreakdown:
    """Create sample cost breakdown for testing."""
    line_items = [
        schemas.CostLineItem(
            name="Battery Modules",
            basis="unit",
            unit_cost=300.0,
            qty=1.0,
            cost=300.0,
            currency="USD",
        )
    ]
    return schemas.CostBreakdown(
        line_items=line_items,
        capex_total=300.0,
        annual_om_usd=15.0,
        price_year=2024,
        assumptions={"note": "unit-test"},
        currency="USD",
    )


def sample_telemetry() -> schemas.BatteryTelemetry8760:
    """Create sample telemetry for testing."""
    hours = 8760
    return schemas.BatteryTelemetry8760(
        charge_in_kwh=[0.1] * hours,
        discharge_out_kwh=[0.08] * hours,
        soc_kwh=[50.0] * hours,
        constraints_hits={"soc_min": 0, "soc_max": 0},
        method="unit-test",
    )


def sample_financial_results() -> schema.FinancialResults:
    """Create sample financial results for testing."""
    cashflow = [
        schema.CashflowEntry(year=0, net_cashflow=-50000.0, cumulative_cashflow=-50000.0),
        schema.CashflowEntry(year=1, net_cashflow=8000.0, cumulative_cashflow=-42000.0),
    ]
    ledger = [
        schema.LedgerEntry(name="Capex", amount=-50000.0, currency="USD", category="capex"),
        schema.LedgerEntry(name="Savings", amount=8000.0, currency="USD", category="savings"),
    ]
    return schema.FinancialResults(
        annual_savings=8000.0,
        cashflow=cashflow,
        npv=-10000.0,
        irr=None,
        payback_years=None,
        lcoe=None,
        lcob=None,
        ledger=ledger,
        currency="USD",
        price_year=2024,
    )


def sample_pipeline_metadata() -> Dict[str, str]:
    """Create sample pipeline metadata for testing."""
    return {
        "run_description": "Unit test pipeline",
        "output_folder": "unit-test-bundle",
    }


def sample_exit_payload() -> Dict[str, schema.StrictBaseModel]:
    """Create sample exit payload for testing."""
    return {
        "rate_info": sample_rate_info(),
        "battery_config": sample_battery_config(),
        "cost_breakdown": sample_cost_breakdown(),
        "telemetry": sample_telemetry(),
        "financial_results": sample_financial_results(),
    }


def sample_sync_outputs() -> schemas.SyncSimOutputs:
    """Create sample synchronous simulation outputs for testing."""
    outer_step = schema.SyncOuterStep(
        index=0,
        start=datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
        duration=schema.TimeSpan(raw="1H"),
    )
    metadata = schema.MockForecastMetadata(currency="USD", unit="USD_per_kWh")
    forecast_point = schema.MockForecastPoint(
        outer_index=0,
        issued_at=outer_step.start,
        timestamps=(outer_step.start,),
        values=(0.1,),
        metadata=metadata,
    )
    guidance = schema.SyncGuidance(
        outer_index=0,
        timestamp=outer_step.start,
        setpoint_kw=0.0,
    )
    telemetry_frame = schemas.SyncTelemetryFrame(
        outer_index=0,
        timestamp=outer_step.start,
        inner_times=(outer_step.start,),
        soc_kwh=(240.0,),
        charge_in_kw=(0.0,),
        discharge_in_kw=(0.0,),
    )
    return schemas.SyncSimOutputs(
        forecasts=schema.MockForecastSeries(series=(forecast_point,)),
        guidances=schema.SyncGuidanceSeries(series=(guidance,)),
        telemetry=schemas.SyncTelemetrySeries(frames=(telemetry_frame,)),
    )
