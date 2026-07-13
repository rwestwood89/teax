"""Store-level test helpers (Phase 1) and real-evaluator fixtures (Phase 2+),
mirroring `simkit/tests/evaluation/conftest.py`.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from simkit.evaluation.evaluator import PreparedEvaluator
from simkit.evaluation.package_load import ProvisionalPackageLoader
from simkit.study.compatibility import Compatibility

HERE = Path(__file__).parent
FIXTURE_DIR = HERE.parent / "evaluation" / "fixtures" / "sealed_package" / "package_live"
SPEC_PATH = FIXTURE_DIR / "pipelines" / "pipeline.yaml"
ENTRY_CH = "toy_plant_params"

# Fixed design attributes; only plant_budget varies unless a test says otherwise.
FIXED = {
    "toy_plant__Toy_Plant__plant_length": 4.0,
    "toy_plant__Toy_Plant__plant_unit_cost": 250.0,
    "toy_plant__Toy_Plant__plant_width": 3.0,
}


@pytest.fixture(scope="session")
def _loader(tmp_path_factory) -> ProvisionalPackageLoader:
    link_root = tmp_path_factory.mktemp("wi014_s4_pkg_study")
    return ProvisionalPackageLoader(
        package_dir=FIXTURE_DIR, package_name="wi014_s4", link_root=link_root
    )


@pytest.fixture(scope="session")
def prepared(_loader) -> PreparedEvaluator:
    return PreparedEvaluator(_loader, SPEC_PATH)


def run_store_child(db: Path, crash_at: str | None = None) -> int:
    cmd = [sys.executable, "-m", "simkit.tests.study._store_child", "--db", str(db)]
    if crash_at:
        cmd += ["--crash-at", crash_at]
    result = subprocess.run(cmd)
    return result.returncode


def artifact_present_and_valid(db: Path, digest: str) -> bool:
    path = db.parent / "artifacts" / f"{digest}.json"
    if not path.exists():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == digest


def compat_with_strategy_config(strategy_config: str) -> Compatibility:
    return Compatibility(
        study_id="study-compat",
        executable_fingerprint="exe-fp-A",
        model_contract_fingerprint="contract-fp-A",
        study_definition_fingerprint="def-fp-A",
        input_schema_version="input-v1",
        evidence_schema_version="evidence-v1",
        strategy_identity="grid/v1",
        strategy_config=strategy_config,
    )
