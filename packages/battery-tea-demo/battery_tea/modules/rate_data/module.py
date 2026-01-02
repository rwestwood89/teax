"""Rate data normalization module."""
from __future__ import annotations

from typing import Dict

import numpy as np

from simkit.core.base import ModuleBase, ModuleResult

from ... import defaults, schemas


class RateDataModule(ModuleBase[schemas.Geography, schemas.RateInfo]):
    name = "rate_data"
    version = "v0.1"

    def _coerce(self, geography: schemas.Geography | Dict[str, object]) -> schemas.Geography:
        if isinstance(geography, schemas.Geography):
            return geography
        return schemas.Geography(**geography)

    def validate_and_fill_default(self, geography: schemas.Geography | Dict[str, object]) -> schemas.Geography:
        geo = self._coerce(geography)
        if geo.country not in {"US"}:
            raise ValueError("Unsupported country for demo")
        timezone = geo.timezone or self._infer_timezone(geo.country, geo.region)
        currency = geo.currency or self._infer_currency(geo.country)
        return schemas.Geography(
            country=geo.country,
            region=geo.region,
            utility=geo.utility,
            timezone=timezone,
            currency=currency,
        )

    def _infer_timezone(self, country: str, region: str | None) -> str:
        """Infer timezone from country and region."""
        timezone_map = {"US_CA": "America/Los_Angeles"}
        key = f"{country}_{region}" if region else country
        tz = timezone_map.get(key)
        if tz:
            return tz
        if country == "US":
            return "America/New_York"
        return "UTC"

    def _infer_currency(self, country: str) -> str:
        """Infer currency from country."""
        currency_map = {"US": "USD"}
        return currency_map.get(country, "USD")

    def _synthetic_prices(self, timezone: str) -> schemas.RateInfo:
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

        return schemas.RateInfo(
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

    def run(self, geography: schemas.Geography | Dict[str, object]) -> ModuleResult[schemas.RateInfo]:
        geo_validated = self.validate_and_fill_default(geography)
        rate_info = self._synthetic_prices(geo_validated.timezone or "UTC")
        rate_info = rate_info.model_copy(update={"currency": geo_validated.currency})
        return ModuleResult(rate_info, notes="Generated synthetic TOU rate curve")
