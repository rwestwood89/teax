"""Pytest fixtures for battery TEA tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from battery_tea import schemas
from battery_tea.defaults import default_design_prefs
from battery_tea.io import read_parquet_load_profile, read_parquet_pv_profile
from simkit.io.readers import read_json_model
from simkit.config.schema import FinancialParams

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def geography_us_ca() -> schemas.Geography:
    """Load US California PG&E geography fixture."""
    return read_json_model(FIXTURES_DIR / "geography_us_ca_pge.json", schemas.Geography)


@pytest.fixture
def rate_info_synth() -> schemas.RateInfo:
    """Load synthetic TOU rate info fixture."""
    return read_json_model(FIXTURES_DIR / "rateinfo_tou_synthetic.json", schemas.RateInfo)


@pytest.fixture
def load_profile_flat() -> schemas.LoadProfile8760:
    """Load flat 8760 load profile fixture."""
    return read_parquet_load_profile(
        FIXTURES_DIR / "load_profile_flat_8760.parquet", source="flat_fixture"
    )


@pytest.fixture
def load_profile_toy() -> schemas.LoadProfile8760:
    """Load toy 8760 load profile fixture."""
    return read_parquet_load_profile(
        FIXTURES_DIR / "load_profile_toy_8760.parquet", source="toy_fixture"
    )


@pytest.fixture
def design_prefs_default() -> schemas.DesignPrefs:
    """Return default design preferences."""
    return default_design_prefs()


@pytest.fixture
def financial_params_demo() -> FinancialParams:
    """Load demo financial parameters fixture."""
    return read_json_model(FIXTURES_DIR / "financial_params_demo.json", FinancialParams)
