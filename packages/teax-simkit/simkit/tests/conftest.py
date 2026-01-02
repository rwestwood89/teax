"""Pytest fixtures for generic framework tests.

Battery-specific fixtures have been moved to battery_tea package tests.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from simkit.config import defaults, schema
from simkit.io import readers

# Shared fixtures pull data from simkit/tests/fixtures
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def financial_params_demo() -> schema.FinancialParams:
    """Load demo financial parameters from fixture file."""
    return readers.read_json_model(
        FIXTURE_DIR / "financial_params_demo.json", schema.FinancialParams
    )


@pytest.fixture
def financial_params_default() -> schema.FinancialParams:
    """Return default financial parameters."""
    return defaults.default_financial_params()
