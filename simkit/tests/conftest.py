from __future__ import annotations

from pathlib import Path

import pytest

from simkit.config import defaults, schema
from simkit.io import readers

# Shared fixtures pull data from simkit/tests/fixtures
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def geography_us_ca() -> schema.Geography:
    return readers.read_json_model(FIXTURE_DIR / "geography_us_ca_pge.json", schema.Geography)


@pytest.fixture
def rate_info_synth() -> schema.RateInfo:
    return readers.read_json_model(FIXTURE_DIR / "rateinfo_tou_synthetic.json", schema.RateInfo)


@pytest.fixture
def load_profile_flat() -> schema.LoadProfile8760:
    return readers.read_parquet_load_profile(
        FIXTURE_DIR / "load_profile_flat_8760.parquet", source="flat_fixture"
    )


@pytest.fixture
def load_profile_toy() -> schema.LoadProfile8760:
    return readers.read_parquet_load_profile(
        FIXTURE_DIR / "load_profile_toy_8760.parquet", source="toy_fixture"
    )


@pytest.fixture
def design_prefs_default() -> schema.DesignPrefs:
    return defaults.default_design_prefs()


@pytest.fixture
def financial_params_demo() -> schema.FinancialParams:
    return readers.read_json_model(
        FIXTURE_DIR / "financial_params_demo.json", schema.FinancialParams
    )
