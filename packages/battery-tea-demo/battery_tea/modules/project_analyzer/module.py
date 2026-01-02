"""Project analyzer converting telemetry into financial metrics."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from simkit.config import schema
from simkit.config.defaults import default_financial_params
from simkit.config.schema import StrictBaseModel
from simkit.core.base import ModuleBase, ModuleResult

from ... import schemas


class AnalyzerInputs(StrictBaseModel):
    rate_info: schemas.RateInfo
    telemetry: schemas.BatteryTelemetry8760
    financial_params: schema.FinancialParams
    cost_breakdown: Optional[schemas.CostBreakdown] = None


class ProjectAnalyzerModule(ModuleBase[AnalyzerInputs, schema.FinancialResults]):
    name = "project_analyzer"
    version = "v0.1"

    def _coerce_rate(self, rate: schemas.RateInfo | Dict[str, object]) -> schemas.RateInfo:
        if isinstance(rate, schemas.RateInfo):
            return rate
        return schemas.RateInfo(**rate)

    def _coerce_telemetry(self, telemetry: schemas.BatteryTelemetry8760 | Dict[str, object]) -> schemas.BatteryTelemetry8760:
        if isinstance(telemetry, schemas.BatteryTelemetry8760):
            return telemetry
        return schemas.BatteryTelemetry8760(**telemetry)

    def _coerce_financial(self, params: schema.FinancialParams | Dict[str, object] | None) -> schema.FinancialParams:
        if params is None:
            return default_financial_params()
        if isinstance(params, schema.FinancialParams):
            return params
        return schema.FinancialParams(**params)

    def _coerce_cost(self, cost: schemas.CostBreakdown | Dict[str, object] | None) -> schemas.CostBreakdown | None:
        if cost is None or isinstance(cost, schemas.CostBreakdown):
            return cost
        return schemas.CostBreakdown(**cost)

    def validate_and_fill_default(
        self,
        rate_info: schemas.RateInfo | Dict[str, object],
        telemetry: schemas.BatteryTelemetry8760 | Dict[str, object],
        financial_params: schema.FinancialParams | Dict[str, object] | None = None,
        cost_breakdown: schemas.CostBreakdown | Dict[str, object] | None = None,
    ) -> AnalyzerInputs:
        rate = self._coerce_rate(rate_info)
        telem = self._coerce_telemetry(telemetry)
        params = self._coerce_financial(financial_params)
        cost = self._coerce_cost(cost_breakdown)

        if rate.energy_price_usd_per_kwh is None and rate.tou_periods is None:
            raise ValueError("Rate info must include pricing data")
        return AnalyzerInputs(rate, telem, params, cost)

    def _hourly_prices(self, rate_info: schemas.RateInfo) -> np.ndarray:
        if rate_info.energy_price_usd_per_kwh is not None:
            return np.array(rate_info.energy_price_usd_per_kwh)
        assert rate_info.tou_periods is not None and rate_info.tou_mapping_hourly is not None
        return np.array([rate_info.tou_periods[label] for label in rate_info.tou_mapping_hourly])

    def _annual_savings(self, inputs: AnalyzerInputs) -> float:
        prices = self._hourly_prices(inputs.rate_info)
        charge = np.array(inputs.telemetry.charge_in_kwh)
        discharge = np.array(inputs.telemetry.discharge_out_kwh)
        revenue = float(np.dot(discharge, prices))
        charge_cost = float(np.dot(charge, prices))
        return revenue - charge_cost

    def _cashflows(
        self, params: schema.FinancialParams, annual_savings: float, annual_om: float, capex: float
    ) -> List[schema.CashflowEntry]:
        cashflows = []
        cumulative = -capex
        cashflows.append(
            schema.CashflowEntry(year=0, net_cashflow=-capex, cumulative_cashflow=cumulative)
        )
        savings = annual_savings
        om = annual_om
        for year in range(1, params.analysis_years + 1):
            net = savings - om
            cumulative += net
            cashflows.append(
                schema.CashflowEntry(year=year, net_cashflow=round(net, 2), cumulative_cashflow=round(cumulative, 2))
            )
            savings *= 1 + (params.escalation_energy or 0.0)
            om *= 1 + (params.escalation_om or 0.0)
        return cashflows

    def _npv(self, params: schema.FinancialParams, cashflows: List[schema.CashflowEntry]) -> float:
        discount = params.discount_rate
        total = 0.0
        for entry in cashflows:
            total += entry.net_cashflow / ((1 + discount) ** entry.year)
        return round(total, 2)

    def _irr(self, cashflows: List[schema.CashflowEntry]) -> float | None:
        values = np.array([entry.net_cashflow for entry in cashflows], dtype=float)
        if (values > 0).all() or (values < 0).all():
            return None

        def npv(rate: float) -> float:
            return float(np.sum(values / (1 + rate) ** np.arange(len(values))))

        low, high = -0.9, 1.0
        for _ in range(100):
            mid = (low + high) / 2
            val = npv(mid)
            if abs(val) < 1e-6:
                return round(mid, 4)
            if val > 0:
                low = mid
            else:
                high = mid
        return round(mid, 4)

    def _payback(self, cashflows: List[schema.CashflowEntry]) -> float | None:
        for entry in cashflows:
            if entry.year == 0:
                continue
            prev = cashflows[entry.year - 1]
            if prev.cumulative_cashflow < 0 <= entry.cumulative_cashflow:
                deficit = -prev.cumulative_cashflow
                span = entry.net_cashflow
                if span == 0:
                    return float(entry.year)
                fraction = deficit / span
                return round(prev.year + fraction, 2)
        return None

    def _ledger(
        self,
        annual_savings: float,
        annual_om: float,
        capex: float,
        currency: str,
    ) -> List[schema.LedgerEntry]:
        return [
            schema.LedgerEntry(
                name="Upfront CAPEX",
                amount=-capex,
                currency=currency,
                category="capex",
            ),
            schema.LedgerEntry(
                name="Annual Energy Arbitrage",
                amount=annual_savings,
                currency=currency,
                category="revenue",
            ),
            schema.LedgerEntry(
                name="Annual O&M",
                amount=-annual_om,
                currency=currency,
                category="opex",
            ),
        ]

    def run(
        self,
        rate_info: schemas.RateInfo | Dict[str, object],
        telemetry: schemas.BatteryTelemetry8760 | Dict[str, object],
        financial_params: schema.FinancialParams | Dict[str, object] | None = None,
        cost_breakdown: schemas.CostBreakdown | Dict[str, object] | None = None,
    ) -> ModuleResult[schema.FinancialResults]:
        inputs = self.validate_and_fill_default(rate_info, telemetry, financial_params, cost_breakdown)
        params = inputs.financial_params
        annual_savings = self._annual_savings(inputs)
        capex = params.upfront_capex_usd
        annual_om = params.annual_om_usd
        if inputs.cost_breakdown:
            capex = inputs.cost_breakdown.capex_total
            annual_om = inputs.cost_breakdown.annual_om_usd
        if capex is None or annual_om is None:
            raise ValueError("Project analyzer requires capex and annual O&M inputs")

        cashflows = self._cashflows(params, annual_savings, annual_om, capex)
        npv = self._npv(params, cashflows)
        irr = self._irr(cashflows)
        payback = self._payback(cashflows)
        ledger = self._ledger(annual_savings, annual_om, capex, inputs.rate_info.currency)

        results = schema.FinancialResults(
            annual_savings=round(annual_savings, 2),
            cashflow=cashflows,
            npv=npv,
            irr=irr,
            payback_years=payback,
            lcoe=None,
            lcob=None,
            ledger=ledger,
            currency=inputs.rate_info.currency,
            price_year=inputs.rate_info.price_year,
        )
        return ModuleResult(results, notes="Computed financial summary")
