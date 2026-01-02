"""Simple cost calculator for the demo."""
from __future__ import annotations

from typing import Dict

from simkit.config.schema import StrictBaseModel
from simkit.core.base import ModuleBase, ModuleResult

from ... import defaults, schemas

BASE_CAPEX_PER_KWH = 380.0
BASE_CAPEX_PER_KW = 160.0
INSTALLATION_FRACTION = 0.15
SOFT_COST_FRACTION = 0.1
REGIONAL_MULTIPLIERS: Dict[str, float] = {
    "US_CA": 1.18,
}


class CostInputs(StrictBaseModel):
    config: schemas.BatteryConfig
    geography: schemas.Geography


class CostCalculatorModule(ModuleBase[CostInputs, schemas.CostBreakdownOutput]):
    name = "cost_calculator"
    version = "v0.1"

    def _coerce_battery(self, config: schemas.BatteryConfig | Dict[str, object]) -> schemas.BatteryConfig:
        if isinstance(config, schemas.BatteryConfig):
            return config
        return schemas.BatteryConfig(**config)

    def _coerce_geo(self, geography: schemas.Geography | Dict[str, object]) -> schemas.Geography:
        if isinstance(geography, schemas.Geography):
            return geography
        return schemas.Geography(**geography)

    def validate_and_fill_default(
        self,
        config: schemas.BatteryConfig | Dict[str, object],
        geography: schemas.Geography | Dict[str, object],
    ) -> CostInputs:
        battery = self._coerce_battery(config)
        geo = self._coerce_geo(geography)
        if geo.country != "US":
            raise ValueError("Cost calculator demo supports US only")
        if geo.currency not in {None, "USD"}:
            raise ValueError("Demo cost calculator assumes USD currency")
        return CostInputs(config=battery, geography=geo)

    def _regional_multiplier(self, geography: schemas.Geography) -> float:
        key = f"{geography.country}_{geography.region}" if geography.region else geography.country
        return REGIONAL_MULTIPLIERS.get(key, 1.05 if geography.country == "US" else 1.0)

    def _line_item(self, name: str, basis: str, unit_cost: float, qty: float) -> schemas.CostLineItem:
        cost = round(unit_cost * qty, 2)
        return schemas.CostLineItem(
            name=name,
            basis=basis,
            unit_cost=round(unit_cost, 2),
            qty=round(qty, 2),
            cost=cost,
            currency="USD",
        )

    def _build_breakdown(self, inputs: CostInputs) -> schemas.CostBreakdown:
        multiplier = self._regional_multiplier(inputs.geography)
        battery = inputs.config

        energy_item = self._line_item(
            "Battery Modules",
            "per_kwh",
            BASE_CAPEX_PER_KWH * multiplier,
            battery.capacity_kwh,
        )
        power_item = self._line_item(
            "Inverter & PCS",
            "per_kw",
            BASE_CAPEX_PER_KW * multiplier,
            battery.power_kw,
        )
        install_item = self._line_item(
            "Installation",
            "fraction",
            INSTALLATION_FRACTION * (energy_item.unit_cost + power_item.unit_cost),
            1.0,
        )
        soft_cost_item = self._line_item(
            "Soft Costs",
            "fraction",
            SOFT_COST_FRACTION * (energy_item.unit_cost + power_item.unit_cost),
            1.0,
        )
        line_items = [energy_item, power_item, install_item, soft_cost_item]
        capex_total = round(sum(item.cost for item in line_items), 2)
        annual_om = round(capex_total * 0.02, 2)

        return schemas.CostBreakdown(
            line_items=line_items,
            capex_total=capex_total,
            annual_om_usd=annual_om,
            price_year=defaults.DEFAULT_PRICE_YEAR,
            assumptions={
                "multiplier": f"{multiplier:.2f}",
                "cost_model": "heuristic_v1",
            },
            currency="USD",
        )

    def run(
        self,
        config: schemas.BatteryConfig | Dict[str, object],
        geography: schemas.Geography | Dict[str, object],
    ) -> ModuleResult[schemas.CostBreakdownOutput]:
        inputs = self.validate_and_fill_default(config, geography)
        breakdown = self._build_breakdown(inputs)
        return ModuleResult(schemas.CostBreakdownOutput(breakdown), notes="Computed heuristic CAPEX/OPEX breakdown")
