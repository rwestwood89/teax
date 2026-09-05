"""Real mixed-output execution through evidence, persistence, reopen, and query.

The loader supplies maintained toy modules; generated-package seals are covered
separately. Everything from graph validation through study query is production code.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from pydantic import RootModel

from simkit.core.registry_builder import create_registry
from simkit.evaluation.evaluator import FileBackedEvaluator, PreparedEvaluator
from simkit.study.definition import StudyDefinition
from simkit.study.policy import ObjectivePolicy
from simkit.study.query import StudyQuery
from simkit.study.runner import StudyRunner
from simkit.study.store import StudyStore
from simkit.study.strategy import PreparedListStrategy
from simkit.tests.core.toy_modules import ToyDoublerModule, ToyInput
from simkit.tests.core.toy_scalar_module import ToyScalarOutputModule


class ToyLoader:
    def load(self):
        package = ModuleType("numeric_toy")
        package.CUSTOM_SCHEMA_TYPES = [ToyInput, RootModel[float]]
        package.create_numeric_toy_registry = lambda: create_registry(
            [ToyScalarOutputModule, ToyDoublerModule]
        )
        return package, "numeric-toy-fingerprint"


@pytest.fixture
def toy_package(tmp_path):
    fixture = Path(__file__).parents[1] / "fixtures/pipeline_configs/toy_scalar_outputs.yaml"
    spec = yaml.safe_load(fixture.read_text())
    # Producer field and public channel deliberately differ. YAML ExitPoint keys
    # select channel names; destination filenames do not rename evidence keys.
    spec["modules"]["scalars"]["outputs"]["floating"] = "float public_fraction"
    spec["modules"]["exit"]["outputs"].pop("floating")
    spec["modules"]["exit"]["outputs"]["public_fraction"] = "float internal_fraction.json"
    package_dir = tmp_path / "package"
    (package_dir / "pipelines").mkdir(parents=True)
    (package_dir / "pipelines/pipeline.yaml").write_text(yaml.safe_dump(spec))
    (package_dir / "contracts").mkdir()
    (package_dir / "contracts/model_contract.json").write_text(json.dumps({
        "catalog_schema_version": "3.0.0",
        "semantic_fingerprint": "toy-contract",
        "constraint_catalog": {"concrete_entries": [], "usage_records": []},
    }))
    return package_dir


def test_mixed_outputs_survive_both_evaluators_and_reopened_store(tmp_path, toy_package):
    prepared = PreparedEvaluator(
        ToyLoader(), toy_package / "pipelines/pipeline.yaml", expects_constraint_report=False
    )
    file_backed = FileBackedEvaluator(
        ToyLoader(), toy_package, tmp_path / "work", tmp_path / "outputs",
        expects_constraint_report=False,
    )
    expected_cases = [
        {"public_fraction": 2.5, "integer": 10.0, "wrapped": 20.0},
        {"public_fraction": 3.0, "integer": 12.0, "wrapped": 24.0},
    ]
    for value, expected in zip((10.0, 12.0), expected_cases):
        evidence = prepared.evaluate({"input_value": ToyInput(value=value)})
        entry = tmp_path / "entry.json"
        entry.write_text(json.dumps({"value": value}))
        audit = file_backed.evaluate(entry)
        for result in (evidence, audit):
            assert result.outputs == expected
            assert result.provenance.evidence_schema_version == "v3"
            assert result.responses == {}
            assert result.report is None

    definition = StudyDefinition(
        study_id="numeric-publication",
        entry_models=prepared.entry_models,
        strategy=PreparedListStrategy([{"value": 10.0}, {"value": 12.0}]),
        validate_proposal=dict,
        policy=ObjectivePolicy((), {}),
        executable_fingerprint=prepared.fingerprint,
        model_contract_fingerprint="toy-contract",
        input_schema_version="v1",
        evidence_schema_version=prepared.EVIDENCE_SCHEMA_VERSION,
        study_definition_fingerprint="two-values",
    )
    db = tmp_path / "study.db"
    store = StudyStore.create_or_open(db, definition.compatibility())
    try:
        store.acquire_lease()
        StudyRunner(store, definition, prepared).run()
        store.release_lease()
    finally:
        store.close()
    reopened = StudyStore.create_or_open(db, definition.compatibility())
    try:
        cases = StudyQuery(reopened, toy_package).cases()
        assert len(cases) == 2
        for case in cases:
            assert case.state == "completed"
            expected = expected_cases[0 if case.inputs["value"] == 10.0 else 1]
            assert case.outputs == expected
    finally:
        reopened.close()
