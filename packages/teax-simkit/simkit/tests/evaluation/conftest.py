"""Shared fixtures for the evaluation test suite."""
from __future__ import annotations

from pathlib import Path

import pytest

from simkit.evaluation.evaluator import PreparedEvaluator
from simkit.evaluation.package_load import ProvisionalPackageLoader

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sealed_package" / "package_live"
SPEC_PATH = FIXTURE_DIR / "pipelines" / "pipeline.yaml"
ENTRY_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "entries"

# Exit-channel IDs, from the fixture package's pipeline.yaml.
AREA_CH = "toy_plant__demo_plant__area_calc__area"
COST_CH = "toy_plant__demo_plant__cost_calc__cost"
REPORT_CH = "constraint_report"
ENTRY_CH = "toy_plant_params"

# Fixed design attributes; only plant_budget/plant_length vary per fixture case.
FIXED = {
    "toy_plant__Toy_Plant__plant_length": 4.0,
    "toy_plant__Toy_Plant__plant_unit_cost": 250.0,
    "toy_plant__Toy_Plant__plant_width": 3.0,
}


@pytest.fixture(scope="session")
def prepared(tmp_path_factory) -> PreparedEvaluator:
    link_root = tmp_path_factory.mktemp("wi014_s4_pkg")
    loader = ProvisionalPackageLoader(
        package_dir=FIXTURE_DIR, package_name="wi014_s4", link_root=link_root
    )
    return PreparedEvaluator(loader, SPEC_PATH)
