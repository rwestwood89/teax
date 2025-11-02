"""Rate data normalization module."""
from __future__ import annotations

from typing import Dict

import numpy as np

from ...config import defaults, schema
from ..base import ModuleBase, ModuleResult


class RateDataModule(ModuleBase[schema.Geography, schema.RateInfo]):
    name = "rate_data"
    version = "v0.1"

    def _coerce(self, geography: schema.Geography | Dict[str, object]) -> schema.Geography:
        if isinstance(geography, schema.Geography):
            return geography
        return schema.Geography(**geography)

    def validate_and_fill_default(self, geography: schema.Geography | Dict[str, object]) -> schema.Geography:
        geo = self._coerce(geography)
        if geo.country not in {"US"}:
            raise ValueError("Unsupported country for demo")
        timezone = geo.timezone or defaults.infer_timezone(geo.country, geo.region)
        currency = geo.currency or defaults.infer_currency(geo.country)
        return schema.Geography(
            country=geo.country,
            region=geo.region,
            utility=geo.utility,
            timezone=timezone,
            currency=currency,
        )

    def _synthetic_prices(self, timezone: str) -> schema.RateInfo:
        base_rate = 0.15
        peak_rate = 0.27
        shoulder_rate = 0.19
        hours = np.arange(8760)
        hour_of_day = hours % 24

        price_array = np.full(8760, base_rate)
        peak_mask = (hour_of_day >= 17) & (hour_of_day < 21)
        shoulder_mask = (hour_of_day >= 6) & (hour_of_day < 17)
        price_array[shoulder_mask] = shoulder_rate
        price_array[peak_mask] = peak_rate

        tou_periods = {
            "off_peak": base_rate,
            "shoulder": shoulder_rate,
            "peak": peak_rate,
        }
        tou_mapping = np.where(peak_mask, "peak", np.where(shoulder_mask, "shoulder", "off_peak"))

        return schema.RateInfo(
            energy_price_usd_per_kwh=price_array.tolist(),
            tou_periods=tou_periods,
            tou_mapping_hourly=tou_mapping.tolist(),
            demand_charge_usd_per_kw=None,
            fixed_monthly_fee_usd=12.0,
            price_year=defaults.DEFAULT_PRICE_YEAR,
            currency="USD",
            vintage=defaults.DEFAULT_RATE_VINTAGE,
            source=defaults.DEFAULT_RATE_SOURCE,
            escalation_rules={"energy": defaults.DEFAULT_ESCALATION_ENERGY},
        )

    def run(self, geography: schema.Geography | Dict[str, object]) -> ModuleResult[schema.RateInfo]:
        geo_validated = self.validate_and_fill_default(geography)
        rate_info = self._synthetic_prices(geo_validated.timezone or "UTC")
        rate_info = rate_info.model_copy(update={"currency": geo_validated.currency})
        return ModuleResult(rate_info, notes="Generated synthetic TOU rate curve")
