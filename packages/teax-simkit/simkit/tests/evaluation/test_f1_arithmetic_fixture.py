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
# Identity moved when this fixture was regenerated at CONSTRAINT-SEMANTICS Item 3. The ids now
# carry the owner path and occurrence hash, which is codegen's current scheme -- PRE-EXISTING
# fa0e06a-to-HEAD drift surfaced by regeneration, NOT an Item 3 change. The order is the
# projection's, not the declaration's.
#   f1_division_check -> toy_plant__fixture__f1_division_check__b973058cd670a967
#   f2_power_check    -> toy_plant__fixture__f2_power_check__b4ca916c6d129ce9
#   f3_nested_check   -> toy_plant__fixture__f3_nested_check__8b3352fdf1f62ba5
EXPECTED_CONSTRAINT_ORDER = (
    "toy_plant__fixture__f3_nested_check__8b3352fdf1f62ba5",
    "toy_plant__fixture__f1_division_check__b973058cd670a967",
    "toy_plant__fixture__f2_power_check__b4ca916c6d129ce9",
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

    evaluator = PreparedEvaluator(
        loader, PACKAGE_DIR / "pipelines" / "pipeline.yaml",
        expects_constraint_report=True,
    )
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
