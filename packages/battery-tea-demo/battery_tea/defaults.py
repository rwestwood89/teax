"""Battery-specific default values and unit constants."""
from __future__ import annotations

from . import schemas

# Battery-specific defaults
DEFAULT_ROUNDTRIP_EFFICIENCY = 0.92
DEFAULT_SOC_MIN = 0.1
DEFAULT_SOC_MAX = 0.9
DEFAULT_BATTERY_NOTES = "Heuristic sizing for demo"
DEFAULT_METHOD = "rule_based_v0"

# Rate defaults (shared with generic but battery-specific usage)
DEFAULT_RATE_SOURCE = "synthetic_tou_v0"
DEFAULT_RATE_VINTAGE = "2024"
DEFAULT_PRICE_YEAR = 2024
DEFAULT_ESCALATION_ENERGY = 0.02


def default_design_prefs() -> schemas.DesignPrefs:
    """Return default design preferences for battery sizing."""
    return schemas.DesignPrefs(
        target_peak_shaving_hours=4.0,
        max_c_rate=0.5,
        min_soc=DEFAULT_SOC_MIN,
        max_soc=DEFAULT_SOC_MAX,
        eta_roundtrip=DEFAULT_ROUNDTRIP_EFFICIENCY,
        safety_margins={"capacity": 0.1},
    )
