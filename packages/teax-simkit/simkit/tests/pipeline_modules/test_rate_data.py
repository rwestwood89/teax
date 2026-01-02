from __future__ import annotations

import pytest

from simkit.config import battery_schema
from simkit.core.rate_data import RateDataModule


def test_validate_rejects_unsupported_country(geography_us_ca):
    module = RateDataModule()
    bad_geo = geography_us_ca.model_copy(update={"country": "DE"})
    with pytest.raises(ValueError):
        module.validate_and_fill_default(bad_geo)


def test_validate_fills_missing_fields():
    module = RateDataModule()
    geo = battery_schema.Geography(country="US", region="CA", utility=None, timezone=None, currency=None)
    validated = module.validate_and_fill_default(geo)
    assert validated.timezone == "America/Los_Angeles"
    assert validated.currency == "USD"


def test_run_returns_hourly_rate(geography_us_ca):
    module = RateDataModule()
    result = module.run(geography_us_ca).data
    assert isinstance(result, battery_schema.RateInfo)
    assert len(result.energy_price_usd_per_kwh) == 8760
    assert result.currency == geography_us_ca.currency


def test_run_rejects_invalid_input(geography_us_ca):
    module = RateDataModule()
    bad_geo = geography_us_ca.model_copy(update={"country": "DE"})
    with pytest.raises(ValueError):
        module.run(bad_geo)
