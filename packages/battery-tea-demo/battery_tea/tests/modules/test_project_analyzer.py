"""Tests for ProjectAnalyzerModule."""
from __future__ import annotations

import pytest

from simkit.config import schema
from battery_tea import schemas
from battery_tea.modules.project_analyzer import ProjectAnalyzerModule
from battery_tea.tests.fixtures import (
    sample_cost_breakdown,
    sample_rate_info,
    sample_telemetry,
)


class TestProjectAnalyzerModuleValidation:
    """Tests for validate_and_fill_default."""

    def test_complete_inputs_valid(self, financial_params_demo: schema.FinancialParams):
        """Complete inputs validate successfully."""
        module = ProjectAnalyzerModule()
        rate_info = sample_rate_info()
        # Override with pricing data
        rate_info = rate_info.model_copy(update={"energy_price_usd_per_kwh": [0.15] * 8760})
        telemetry = sample_telemetry()
        cost = sample_cost_breakdown()

        inputs = module.validate_and_fill_default(
            rate_info, telemetry, financial_params_demo, cost
        )

        assert inputs.rate_info is not None
        assert inputs.telemetry == telemetry
        assert inputs.financial_params == financial_params_demo
        assert inputs.cost_breakdown == cost

    def test_fills_default_financial_params(self):
        """Fills default financial parameters when None provided."""
        module = ProjectAnalyzerModule()
        rate_info = sample_rate_info()
        rate_info = rate_info.model_copy(update={"energy_price_usd_per_kwh": [0.15] * 8760})
        telemetry = sample_telemetry()
        cost = sample_cost_breakdown()

        inputs = module.validate_and_fill_default(rate_info, telemetry, None, cost)

        assert inputs.financial_params is not None
        assert inputs.financial_params.discount_rate > 0

    def test_rate_without_pricing_raises(self):
        """Rate info without pricing data raises ValueError."""
        module = ProjectAnalyzerModule()
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
        telemetry = sample_telemetry()
        cost = sample_cost_breakdown()

        with pytest.raises(ValueError, match="pricing"):
            module.validate_and_fill_default(bad_rate, telemetry, None, cost)


class TestProjectAnalyzerModuleRun:
    """Tests for run method."""

    def test_run_produces_financial_results(
        self, financial_params_demo: schema.FinancialParams
    ):
        """Run produces FinancialResults."""
        module = ProjectAnalyzerModule()
        rate_info = sample_rate_info()
        rate_info = rate_info.model_copy(update={"energy_price_usd_per_kwh": [0.15] * 8760})
        telemetry = sample_telemetry()
        cost = sample_cost_breakdown()

        result = module.run(rate_info, telemetry, financial_params_demo, cost)

        assert result.data is not None
        assert isinstance(result.data.root, schema.FinancialResults)

    def test_run_produces_annual_savings(
        self, financial_params_demo: schema.FinancialParams
    ):
        """Run calculates annual savings."""
        module = ProjectAnalyzerModule()
        rate_info = sample_rate_info()
        rate_info = rate_info.model_copy(update={"energy_price_usd_per_kwh": [0.15] * 8760})
        telemetry = sample_telemetry()
        cost = sample_cost_breakdown()

        result = module.run(rate_info, telemetry, financial_params_demo, cost)

        # Annual savings should be calculated
        assert result.data.root.annual_savings is not None

    def test_run_produces_cashflow(
        self, financial_params_demo: schema.FinancialParams
    ):
        """Run produces cashflow entries."""
        module = ProjectAnalyzerModule()
        rate_info = sample_rate_info()
        rate_info = rate_info.model_copy(update={"energy_price_usd_per_kwh": [0.15] * 8760})
        telemetry = sample_telemetry()
        cost = sample_cost_breakdown()

        result = module.run(rate_info, telemetry, financial_params_demo, cost)

        assert result.data.root.cashflow is not None
        assert len(result.data.root.cashflow) > 0
        # First entry should be year 0 (CAPEX)
        assert result.data.root.cashflow[0].year == 0
        assert result.data.root.cashflow[0].net_cashflow < 0  # CAPEX is negative

    def test_run_produces_npv(
        self, financial_params_demo: schema.FinancialParams
    ):
        """Run calculates NPV."""
        module = ProjectAnalyzerModule()
        rate_info = sample_rate_info()
        rate_info = rate_info.model_copy(update={"energy_price_usd_per_kwh": [0.15] * 8760})
        telemetry = sample_telemetry()
        cost = sample_cost_breakdown()

        result = module.run(rate_info, telemetry, financial_params_demo, cost)

        assert result.data.root.npv is not None

    def test_run_produces_ledger(
        self, financial_params_demo: schema.FinancialParams
    ):
        """Run produces ledger entries."""
        module = ProjectAnalyzerModule()
        rate_info = sample_rate_info()
        rate_info = rate_info.model_copy(update={"energy_price_usd_per_kwh": [0.15] * 8760})
        telemetry = sample_telemetry()
        cost = sample_cost_breakdown()

        result = module.run(rate_info, telemetry, financial_params_demo, cost)

        assert result.data.root.ledger is not None
        assert len(result.data.root.ledger) > 0

        # Should have CAPEX, revenue, and O&M entries
        categories = {entry.category for entry in result.data.root.ledger}
        assert "capex" in categories

    def test_run_uses_cost_breakdown_values(
        self, financial_params_demo: schema.FinancialParams
    ):
        """Run uses CAPEX/O&M from cost breakdown when provided."""
        module = ProjectAnalyzerModule()
        rate_info = sample_rate_info()
        rate_info = rate_info.model_copy(update={"energy_price_usd_per_kwh": [0.15] * 8760})
        telemetry = sample_telemetry()

        cost = schemas.CostBreakdown(
            line_items=[],
            capex_total=50000.0,
            annual_om_usd=1000.0,
            price_year=2024,
            assumptions={},
            currency="USD",
        )

        result = module.run(rate_info, telemetry, financial_params_demo, cost)

        # Year 0 cashflow should reflect the CAPEX from cost breakdown
        year0 = result.data.root.cashflow[0]
        assert year0.net_cashflow == -50000.0

    def test_run_includes_notes(
        self, financial_params_demo: schema.FinancialParams
    ):
        """Run includes execution notes."""
        module = ProjectAnalyzerModule()
        rate_info = sample_rate_info()
        rate_info = rate_info.model_copy(update={"energy_price_usd_per_kwh": [0.15] * 8760})
        telemetry = sample_telemetry()
        cost = sample_cost_breakdown()

        result = module.run(rate_info, telemetry, financial_params_demo, cost)

        assert result.notes is not None
