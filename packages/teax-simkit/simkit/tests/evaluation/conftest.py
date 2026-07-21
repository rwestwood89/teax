"""Shared fixtures for the evaluation test suite."""
from __future__ import annotations

from pathlib import Path

import pytest

from simkit.evaluation.evaluator import FileBackedEvaluator, PreparedEvaluator
from simkit.evaluation.package_load import ProvisionalPackageLoader

# Generated package self-tests require import under the sealed declared name.
# They are package artifacts, not tests owned by this repository's evaluation suite.
collect_ignore_glob = ["fixtures/**/package_live/tests/test_*.py"]

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
def _loader(tmp_path_factory) -> ProvisionalPackageLoader:
    link_root = tmp_path_factory.mktemp("wi014_s4_pkg")
    return ProvisionalPackageLoader(
        package_dir=FIXTURE_DIR, package_name="wi014_s4", link_root=link_root
    )


@pytest.fixture(scope="session")
def prepared(_loader) -> PreparedEvaluator:
    return PreparedEvaluator(_loader, SPEC_PATH)


@pytest.fixture(scope="session")
def file_backed(_loader, tmp_path_factory) -> FileBackedEvaluator:
    work_dir = tmp_path_factory.mktemp("file_backed_work")
    output_dir = tmp_path_factory.mktemp("file_backed_output")
    return FileBackedEvaluator(_loader, FIXTURE_DIR, work_dir, output_dir)
