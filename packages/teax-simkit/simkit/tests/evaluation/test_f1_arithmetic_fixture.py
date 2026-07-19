"""Acceptance checks for the sealed production-equivalent F1 fixture."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from simkit.evaluation.evaluator import PreparedEvaluator
from simkit.evaluation.package_load import ProvisionalPackageLoader

F1_ROOT = Path(__file__).parent / "fixtures" / "f1_arithmetic"
PACKAGE_DIR = F1_ROOT / "package_live"
PACKAGE_NAME = "f1_arithmetic_constraints"
EXPECTED_CONSTRAINT_ORDER = (
    "f1_division_check",
    "f2_power_check",
    "f3_nested_check",
)
EXPECTED_MODULE_ORDER = (
    "entry_fusion",
    *EXPECTED_CONSTRAINT_ORDER,
    "constraint_report_aggregator",
    "exit_point",
)


def test_f1_fixture_seal_name_fingerprint_and_order(tmp_path):
    loader = ProvisionalPackageLoader(
        package_dir=PACKAGE_DIR,
        package_name=PACKAGE_NAME,
        link_root=tmp_path / "links",
    )
    package, fingerprint = loader.load()
    assert package.__name__ == PACKAGE_NAME

    model_contract = json.loads(
        (PACKAGE_DIR / "contracts" / "model_contract.json").read_text(encoding="utf-8")
    )
    catalog = model_contract["constraint_catalog"]
    assert tuple(
        entry["constraint_id"] for entry in catalog["concrete_entries"]
    ) == EXPECTED_CONSTRAINT_ORDER

    pipeline = yaml.safe_load(
        (PACKAGE_DIR / "pipelines" / "pipeline.yaml").read_text(encoding="utf-8")
    )
    assert tuple(pipeline["modules"]) == EXPECTED_MODULE_ORDER
    assert (
        pipeline["modules"]["entry_fusion"]["inputs"]["toy_plant_params"].split()[1]
        == "../inputs/toy_plant_params.json"
    )

    evaluator = PreparedEvaluator(loader, PACKAGE_DIR / "pipelines" / "pipeline.yaml")
    assert tuple(evaluator._graph.topological_order) == EXPECTED_MODULE_ORDER

    generation_record = (F1_ROOT / "GENERATION.md").read_text(encoding="utf-8")
    recorded = re.search(r"Executable fingerprint: `([0-9a-f]{64})`", generation_record)
    assert recorded is not None
    assert recorded.group(1) == fingerprint

    contract = json.loads(
        (PACKAGE_DIR / "contracts" / "package_contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["package_name"] == PACKAGE_NAME
    covered = set(contract["artifact_hashes"])
    actual = {
        path.relative_to(PACKAGE_DIR).as_posix()
        for path in PACKAGE_DIR.rglob("*")
        if path.is_file()
        and path.relative_to(PACKAGE_DIR).as_posix()
        != "contracts/package_contract.json"
        and "__pycache__" not in path.parts
    }
    assert covered == actual
    assert "IMPLEMENTATION_BACKLOG.md" in covered
