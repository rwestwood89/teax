"""Store-level test helpers (Phase 1) and real-evaluator fixtures (Phase 2+),
mirroring `simkit/tests/evaluation/conftest.py`.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import yaml

from simkit.evaluation.evaluator import PreparedEvaluator
from simkit.evaluation.evidence import EvidenceProvenance, ModelEvidence
from simkit.evaluation.failure import EvaluationFailed, EvaluationFailure, EvaluationPhase
from simkit.evaluation.package_load import ProvisionalPackageLoader
from simkit.study.compatibility import Compatibility
from simkit.study.definition import StudyDefinition
from simkit.study.failures import RetryableStoreError
from simkit.study.identity import digest_of
from simkit.study.runner import StudyRunner
from simkit.study.store import StudyStore
from simkit.study.strategy import PreparedListStrategy

HERE = Path(__file__).parent
FIXTURE_DIR = HERE.parent / "evaluation" / "fixtures" / "sealed_package" / "package_live"
SPEC_PATH = FIXTURE_DIR / "pipelines" / "pipeline.yaml"
ENTRY_CH = "toy_plant_params"
COST_CH = "toy_plant__demo_plant__cost_calc__cost"

# Fixed design attributes; only plant_budget varies unless a test says otherwise.
FIXED = {
    "toy_plant__Toy_Plant__plant_length": 4.0,
    "toy_plant__Toy_Plant__plant_unit_cost": 250.0,
    "toy_plant__Toy_Plant__plant_width": 3.0,
}
GRID_VAR = "toy_plant__Toy_Plant__plant_budget"


def write_grid_config(
    tmp_path: Path,
    *,
    package_dir: Path | str | None = None,
    budgets: list[float] | None = None,
    edit: str | None = None,
) -> Path:
    """Write the illustrative grid study-config YAML (design.md's schema),
    varying `toy_plant__Toy_Plant__plant_budget` over `budgets` (default
    [1000, 3000, 6000] — cost is 3000 under `FIXED`, so this spans
    violated/boundary/satisfied). `edit` perturbs exactly one
    definition-shaping field, for the fingerprint-sensitivity tests.
    """
    study_id = "toy-grid-demo"
    entry_model = "ToyPlantParams"
    domain = list(budgets) if budgets is not None else [1000.0, 3000.0, 6000.0]
    fixed = dict(FIXED)
    objectives = [{"output": COST_CH, "role": "minimize"}]
    response_roles: dict[str, str] = {}
    budget = None

    if edit == "study_id":
        study_id += "-edited"
    elif edit == "entry_model":
        entry_model = "SomeOtherModel"
    elif edit == "grid_order":
        domain = list(reversed(domain))
    elif edit == "grid_domain":
        domain = [value + 1.0 for value in domain]
    elif edit == "fixed":
        fixed["toy_plant__Toy_Plant__plant_length"] += 1.0
    elif edit == "policy":
        objectives = [{"output": COST_CH, "role": "maximize"}]
    elif edit == "budget":
        budget = 5

    config = {
        "study_id": study_id,
        "package": {
            "dir": str(package_dir if package_dir is not None else FIXTURE_DIR),
            "name": "wi014_s4",
            "spec": "pipelines/pipeline.yaml",
        },
        "entry_channel": ENTRY_CH,
        "entry_model": entry_model,
        "grid": [[GRID_VAR, domain]],
        "fixed": fixed,
        "policy": {"name": "objective/v1", "objectives": objectives, "response_roles": response_roles},
        "budget": budget,
        "retention": "keep",
    }
    path = tmp_path / f"study-{uuid.uuid4().hex}.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return path


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


# --------------------------------------------------------------------------
# Phase 3: runner fixtures over the real evaluator, plus named test
# affordances at the exact seams the deterministic fixture cannot itself
# trigger (design.md#validation-approach).
# --------------------------------------------------------------------------

STUDY_ID = "study-runner"
EXEC_FAIL_BUDGET = -999.0
ZERO_ASSERTION_BUDGET = -998.0


def _budget_only(value: float) -> dict:
    return {"toy_plant__Toy_Plant__plant_budget": value}


# Index -> proposal; candidate_id is minted from this position (positional
# identity). cost = length*width*unit_cost = 4*3*250 = 3000 under FIXED, so
# budget >= 3000 -> satisfied, budget < 3000 -> violated.
PROPOSALS: list[dict] = [
    _budget_only(6000.0),                      # 0 -> completed / satisfied
    _budget_only(1000.0),                      # 1 -> completed / violated
    _budget_only(float("nan")),                # 2 -> completed / indeterminate
    {"toy_plant__Toy_Plant__plant_budget": "not-a-number"},  # 3 -> INVALID proposal
    _budget_only(EXEC_FAIL_BUDGET),             # 4 -> execution_failed (named fault)
    _budget_only(6100.0),                       # 5 -> assessment_failed (policy rejects)
    _budget_only(ZERO_ASSERTION_BUDGET),        # 6 -> completed / not_assessed (named affordance)
    _budget_only(6200.0),                       # 7 -> replicate A
    _budget_only(6200.0),                       # 8 -> replicate B (identical inputs)
    _budget_only(6300.0),                       # 9 -> completed after a store retry
]


def validate_proposal(raw: dict) -> dict | None:
    """Malformed/missing/wrong-type only — never non-finite (spec.md#runner)."""
    value = raw.get("toy_plant__Toy_Plant__plant_budget")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return {"toy_plant__Toy_Plant__plant_budget": float(value)}


class NamedFaultEvaluator:
    """Delegates to the real `PreparedEvaluator`; two designated sentinel
    budgets trigger a named, real-shaped test affordance instead of running
    the module graph — the fixture cannot itself raise or emit zero
    assertions by input (design.md#validation-approach).
    """

    def __init__(self, prepared_evaluator: PreparedEvaluator) -> None:
        self._prepared = prepared_evaluator

    def evaluate(self, typed_inputs):
        budget = typed_inputs[ENTRY_CH].toy_plant__Toy_Plant__plant_budget
        if budget == EXEC_FAIL_BUDGET:
            raise EvaluationFailed(
                EvaluationFailure(
                    phase=EvaluationPhase.MODULE_EXECUTION,
                    cause="named fault: module raised (test affordance)",
                )
            )
        if budget == ZERO_ASSERTION_BUDGET:
            return self._zero_assertion_evidence()
        return self._prepared.evaluate(typed_inputs)

    def _zero_assertion_evidence(self) -> ModelEvidence:
        from wi014_s4.schemas.constraint_types import ConstraintReport  # test-only import

        report = ConstraintReport(
            catalog_fingerprint="zero-assertion-affordance", assessed_count=0,
            headline="not_assessed", results=[],
        )
        provenance = EvidenceProvenance(
            executable_fingerprint=self._prepared.fingerprint,
            evidence_schema_version=self._prepared.EVIDENCE_SCHEMA_VERSION,
            evaluator_version=self._prepared.EVALUATOR_VERSION,
            input_digest="zero-assertion-affordance",
        )
        return ModelEvidence(
            responses={"headline": "not_assessed"}, outputs={},
            provenance=provenance, report=report,
        )


class FlakyOnceStore(StudyStore):
    """Raises `RetryableStoreError` on the first `commit_case` for one
    designated candidate, then behaves normally (D7 retry seam)."""

    def __init__(self, db_path) -> None:
        super().__init__(db_path)
        self.fail_once_for_candidate: str | None = None
        self._already_failed: set[str] = set()

    def commit_case(self, *, candidate_id, **kwargs):
        if candidate_id == self.fail_once_for_candidate and candidate_id not in self._already_failed:
            self._already_failed.add(candidate_id)
            raise RetryableStoreError("injected transient store fault (test affordance)")
        return super().commit_case(candidate_id=candidate_id, **kwargs)


def build_definition(prepared_evaluator: PreparedEvaluator, policy) -> StudyDefinition:
    return StudyDefinition(
        study_id=STUDY_ID,
        entry_channel=ENTRY_CH,
        entry_model=prepared_evaluator.ToyPlantParams,
        strategy=PreparedListStrategy(PROPOSALS),
        validate_proposal=validate_proposal,
        policy=policy,
        executable_fingerprint=prepared_evaluator.fingerprint,
        model_contract_fingerprint="model-contract-v1",
        input_schema_version="input-v1",
        evidence_schema_version=prepared_evaluator.EVIDENCE_SCHEMA_VERSION,
        study_definition_fingerprint=digest_of(PROPOSALS),
    )


def run_study(tmp_path, prepared_evaluator, evaluator, policy, *, store_cls=StudyStore, configure_store=None):
    """Build a definition + store over `PROPOSALS`, run the study once, and
    return the (released-lease) store for assertions."""
    db = tmp_path / "study.db"
    definition = build_definition(prepared_evaluator, policy)
    store = store_cls.create_or_open(db, definition.compatibility())
    if configure_store is not None:
        configure_store(store)
    store.acquire_lease()
    StudyRunner(store, definition, evaluator).run()
    store.release_lease()
    return store
