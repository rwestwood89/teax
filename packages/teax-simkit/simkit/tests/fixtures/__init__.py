"""Reusable object builders for tests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from simkit.config import schema


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


def sample_mock_forecast_series() -> schema.MockForecastSeries:
    """Create sample mock forecast series for testing."""
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
    return schema.MockForecastSeries(series=(forecast_point,))


def sample_sync_guidance_series() -> schema.SyncGuidanceSeries:
    """Create sample sync guidance series for testing."""
    guidance = schema.SyncGuidance(
        outer_index=0,
        timestamp=datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
        setpoint_kw=0.0,
    )
    return schema.SyncGuidanceSeries(series=(guidance,))
