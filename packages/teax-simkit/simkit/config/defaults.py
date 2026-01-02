"""Central place for default values and unit constants."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List
from zoneinfo import ZoneInfo

from . import battery_schema, schema

DEFAULT_TIMEZONE_BY_REGION: Dict[str, str] = {
    "US_CA": "America/Los_Angeles",
}

DEFAULT_CURRENCY_BY_COUNTRY: Dict[str, str] = {
    "US": "USD",
}

DEFAULT_RATE_SOURCE = "synthetic_tou_v0"
DEFAULT_RATE_VINTAGE = "2024"
DEFAULT_PRICE_YEAR = 2024
DEFAULT_ANALYSIS_YEARS = 15
DEFAULT_DISCOUNT_RATE = 0.08
DEFAULT_TAX_RATE = 0.26
DEFAULT_ESCALATION_ENERGY = 0.02
DEFAULT_ESCALATION_OM = 0.02
DEFAULT_ROUNDTRIP_EFFICIENCY = 0.92
DEFAULT_SOC_MIN = 0.1
DEFAULT_SOC_MAX = 0.9
DEFAULT_BATTERY_NOTES = "Heuristic sizing for demo"
DEFAULT_METHOD = "rule_based_v0"


def infer_timezone(country: str, region: str | None) -> str:
    key = f"{country}_{region}" if region else country
    tz = DEFAULT_TIMEZONE_BY_REGION.get(key)
    if tz:
        return tz
    if country == "US":
        return "America/New_York"
    return "UTC"


def infer_currency(country: str) -> str:
    return DEFAULT_CURRENCY_BY_COUNTRY.get(country, "USD")


def default_financial_params() -> schema.FinancialParams:
    return schema.FinancialParams(
        discount_rate=DEFAULT_DISCOUNT_RATE,
        analysis_years=DEFAULT_ANALYSIS_YEARS,
        depreciation_method="straight_line",
        tax_rate=DEFAULT_TAX_RATE,
        escalation_energy=DEFAULT_ESCALATION_ENERGY,
        escalation_om=DEFAULT_ESCALATION_OM,
        upfront_capex_usd=None,
        annual_om_usd=None,
    )


def default_time_index(year: int, timezone: str) -> List[datetime]:
    zone = ZoneInfo(timezone)
    start = datetime(year=year, month=1, day=1, tzinfo=zone)
    return [start + timedelta(hours=offset) for offset in range(8760)]


def default_design_prefs() -> battery_schema.DesignPrefs:
    return battery_schema.DesignPrefs(
        target_peak_shaving_hours=4.0,
        max_c_rate=0.5,
        min_soc=DEFAULT_SOC_MIN,
        max_soc=DEFAULT_SOC_MAX,
        eta_roundtrip=DEFAULT_ROUNDTRIP_EFFICIENCY,
        safety_margins={"capacity": 0.1},
    )
