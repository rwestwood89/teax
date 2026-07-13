"""`StudyConfig`: the declarative YAML source `create`/`resume` reconstruct
a `StudyDefinition` from, and its semantic fingerprint (D2).

`semantic_fingerprint()` digests only the definition-shaping subset — study
ID, entry channel/model name, ordered grid, fixed fields, policy block,
budget, retention. Package location (`package.dir`/`spec`) is excluded:
package identity is bound separately via `executable_fingerprint` (the
seal), so moving the package tree must not start a new study lineage.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml
from pydantic import Field

from simkit.config.schema import StrictBaseModel
from simkit.evaluation.evaluator import PreparedEvaluator

from .definition import ProposalValidator, StudyDefinition
from .identity import digest_of
from .policy import POLICY_REGISTRY, ObjectiveSpec
from .strategy import GridStrategy


class PackageRef(StrictBaseModel):
    dir: str
    name: str
    spec: str


class ObjectiveConfig(StrictBaseModel):
    output: str
    role: Literal["minimize", "maximize", "penalty"]
    penalty_threshold: float | None = None


class PolicyConfig(StrictBaseModel):
    name: str
    objectives: tuple[ObjectiveConfig, ...] = ()
    response_roles: dict[str, str] = Field(default_factory=dict)


class StudyConfig(StrictBaseModel):
    study_id: str
    package: PackageRef
    entry_channel: str
    entry_model: str
    # Ordered [param_id, domain] pairs, never a dict: declared order is part
    # of the study's identity (mirrors `GridStrategy`, `identity.py`).
    grid: tuple[tuple[str, tuple[float, ...]], ...]
    fixed: dict[str, float] = Field(default_factory=dict)
    policy: PolicyConfig
    budget: int | None = None
    retention: Literal["keep", "gc_after"] = "keep"

    def semantic_fingerprint(self) -> str:
        payload: dict[str, Any] = {
            "study_id": self.study_id,
            "entry_channel": self.entry_channel,
            "entry_model": self.entry_model,
            "grid": [[name, list(domain)] for name, domain in self.grid],
            "fixed": dict(self.fixed),
            "policy": self.policy.model_dump(mode="json"),
            "budget": self.budget,
            "retention": self.retention,
        }
        return digest_of(payload)


def load_study_config(path: str | Path) -> StudyConfig:
    raw = yaml.safe_load(Path(path).read_text())
    return StudyConfig.model_validate(raw)


def _model_contract_fingerprint(config: StudyConfig) -> str:
    """A digest of the fixture catalog's bytes, standing in for a
    `ModelContract` fingerprint until Item 9 (design.md#implementation-notes).
    """
    catalog_path = Path(config.package.dir) / "contracts" / "constraint_catalog.json"
    return hashlib.sha256(catalog_path.read_bytes()).hexdigest()


def _synthesize_validator(config: StudyConfig) -> ProposalValidator:
    """Numeric-and-not-bool coerce each declared grid variable to `float`,
    then merge `fixed`; malformed/missing/wrong-type -> `None`. Mirrors
    `conftest.validate_proposal` (design.md#implementation-notes).
    """
    variable_names = [name for name, _domain in config.grid]
    fixed = dict(config.fixed)

    def validate(raw: Mapping[str, Any]) -> Mapping[str, Any] | None:
        canonical: dict[str, Any] = {}
        for name in variable_names:
            value = raw.get(name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return None
            canonical[name] = float(value)
        canonical.update(fixed)
        return canonical

    return validate


def build_definition(config: StudyConfig, evaluator: PreparedEvaluator) -> StudyDefinition:
    """The create/resume data flow: resolve the entry model from the loaded
    package, build the grid strategy and validator, build the configured
    policy, and assemble the `StudyDefinition` (design.md#architecture).
    """
    entry_model = getattr(evaluator.package, config.entry_model)
    strategy = GridStrategy([(name, list(domain)) for name, domain in config.grid])
    validator = _synthesize_validator(config)

    objectives = tuple(
        ObjectiveSpec(output=o.output, role=o.role, penalty_threshold=o.penalty_threshold)
        for o in config.policy.objectives
    )
    response_roles = dict(config.policy.response_roles)
    policy_factory = POLICY_REGISTRY[config.policy.name]
    policy = policy_factory(objectives, response_roles, config.policy)

    return StudyDefinition(
        study_id=config.study_id,
        entry_channel=config.entry_channel,
        entry_model=entry_model,
        strategy=strategy,
        validate_proposal=validator,
        policy=policy,
        executable_fingerprint=evaluator.fingerprint,
        model_contract_fingerprint=_model_contract_fingerprint(config),
        input_schema_version="input-v1",
        evidence_schema_version=evaluator.EVIDENCE_SCHEMA_VERSION,
        study_definition_fingerprint=config.semantic_fingerprint(),
        objectives=objectives,
        response_roles=response_roles,
        budget=config.budget,
        retention=config.retention,
    )
