"""Tests for RateDataModule."""
from __future__ import annotations

import pytest

from battery_tea import schemas
from battery_tea.modules.rate_data import RateDataModule


class TestRateDataModuleValidation:
    """Tests for validate_and_fill_default."""

    def test_complete_geography_unchanged(self, geography_us_ca: schemas.Geography):
        """Complete geography passes through unchanged (except defaults filled)."""
        module = RateDataModule()
        validated = module.validate_and_fill_default(geography_us_ca)

        assert validated.geography.country == "US"
        assert validated.geography.region == "CA"
        assert validated.geography.utility == geography_us_ca.utility  # Use fixture value
        # Defaults may be filled
        assert validated.geography.timezone is not None
        assert validated.geography.currency is not None

    def test_geography_infers_timezone(self):
        """Infers timezone from country/region."""
        module = RateDataModule()
        geo = schemas.Geography(country="US", region="CA", utility="Test")
        validated = module.validate_and_fill_default(geo)

        assert validated.geography.timezone == "America/Los_Angeles"

    def test_geography_infers_currency(self):
        """Infers currency from country."""
        module = RateDataModule()
        geo = schemas.Geography(country="US", region="TX", utility="Test")
        validated = module.validate_and_fill_default(geo)

        assert validated.geography.currency == "USD"

    def test_unsupported_country_raises(self):
        """Non-US country raises ValueError."""
        module = RateDataModule()
        geo = schemas.Geography(country="FR", region=None, utility=None)

        with pytest.raises(ValueError, match="Unsupported country"):
            module.validate_and_fill_default(geo)

    def test_dict_input_coerced(self):
        """Dict input is coerced to Geography model."""
        module = RateDataModule()
        geo_dict = {"country": "US", "region": "CA", "utility": "Test"}
        validated = module.validate_and_fill_default(geo_dict)

        assert isinstance(validated.geography, schemas.Geography)
        assert validated.geography.country == "US"


class TestRateDataModuleRun:
    """Tests for run method."""

    def test_run_produces_rate_info(self, geography_us_ca: schemas.Geography):
        """Run produces RateInfo with synthetic TOU data."""
        module = RateDataModule()
        result = module.run(geography_us_ca)

        assert result.data is not None
        rate_info = result.data.root
        assert isinstance(rate_info, schemas.RateInfo)
        assert rate_info.energy_price_usd_per_kwh is not None
        assert len(rate_info.energy_price_usd_per_kwh) == 8760

    def test_run_produces_tou_periods(self, geography_us_ca: schemas.Geography):
        """Run produces TOU period definitions."""
        module = RateDataModule()
        result = module.run(geography_us_ca)

        rate_info = result.data.root
        assert rate_info.tou_periods is not None
        assert "peak" in rate_info.tou_periods
        assert "off_peak" in rate_info.tou_periods
        assert "shoulder" in rate_info.tou_periods

    def test_run_produces_tou_mapping(self, geography_us_ca: schemas.Geography):
        """Run produces hourly TOU mapping."""
        module = RateDataModule()
        result = module.run(geography_us_ca)

        rate_info = result.data.root
        assert rate_info.tou_mapping_hourly is not None
        assert len(rate_info.tou_mapping_hourly) == 8760

    def test_run_currency_from_geography(self, geography_us_ca: schemas.Geography):
        """Run uses currency from validated geography."""
        module = RateDataModule()
        result = module.run(geography_us_ca)

        rate_info = result.data.root
        assert rate_info.currency == "USD"

    def test_run_with_dict_input(self):
        """Run accepts dict input."""
        module = RateDataModule()
        result = module.run({"country": "US", "region": "CA", "utility": "Test"})

        assert result.data is not None
        assert isinstance(result.data.root, schemas.RateInfo)

    def test_run_includes_notes(self, geography_us_ca: schemas.Geography):
        """Run includes execution notes."""
        module = RateDataModule()
        result = module.run(geography_us_ca)

        assert result.notes is not None
        assert "synthetic" in result.notes.lower() or "tou" in result.notes.lower()
