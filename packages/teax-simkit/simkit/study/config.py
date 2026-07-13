"""`StudyConfig`: the declarative YAML source `create`/`resume` reconstruct
a `StudyDefinition` from, and its semantic fingerprint (D2).

`semantic_fingerprint()` digests only the definition-shaping subset — study
ID, entry channel/model name, ordered grid, fixed fields, policy block,
budget, retention. Package location (`package.dir`/`spec`) is excluded:
package identity is bound separately via `executable_fingerprint` (the
seal), so moving the package tree must not start a new study lineage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field

from simkit.config.schema import StrictBaseModel

from .identity import digest_of


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
