"""Assessment/policy seam: a `Policy` protocol and a minimal `DispositionPolicy`.

Just enough to produce the three case states and exercise
`assessment_failed`. The full study-policy interpretation protocol, result
queries, and CLI are Item 12 (spec.md#assessment-policy-boundary);
`ModelEvidence` is never mutated.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Protocol

from simkit.evaluation.evidence import ModelEvidence

ObjectiveRole = Literal["minimize", "maximize", "penalty"]


@dataclass(frozen=True)
class ObjectiveSpec:
    """One configured objective: which output to read and how to weigh it.

    `penalty_threshold` bounds the "satisfied but beyond threshold ->
    penalize" disposition (`ObjectivePolicy`, design.md#the-policy).
    """

    output: str
    role: ObjectiveRole
    penalty_threshold: float | None = None


_DISPOSITION_BY_HEADLINE = {
    "satisfied": "feasible",
    "violated": "infeasible",
    "indeterminate": "indeterminate",
    "not_assessed": "not_assessed",
}


class AssessmentFailed(Exception):
    """Policy/objective extraction failed; the runner preserves real evidence
    for this case (spec.md#runner)."""


class Policy(Protocol):
    def assess(self, evidence: ModelEvidence, *, candidate_id: str) -> dict[str, Any]: ...


class DispositionPolicy:
    """Maps evidence to a disposition using the real canonical headline
    vocabulary (`satisfied|violated|indeterminate|not_assessed`).

    `reject_candidate_ids` is an injected set this policy raises
    `AssessmentFailed` for — the seam Item 11 needs to exercise
    `assessment_failed` against real evidence, since the deterministic
    fixture cannot itself fail assessment (design.md#validation-approach).
    """

    def __init__(self, reject_candidate_ids: frozenset[str] = frozenset()) -> None:
        self.reject_candidate_ids = reject_candidate_ids

    def assess(self, evidence: ModelEvidence, *, candidate_id: str) -> dict[str, Any]:
        if candidate_id in self.reject_candidate_ids:
            raise AssessmentFailed(f"policy rejected {candidate_id}")
        headline = evidence.responses["headline"]
        return {"disposition": _DISPOSITION_BY_HEADLINE[headline], "headline": headline}


# Headline -> disposition, the extraction-independent half of the mapping
# (design.md#the-policy step 3). "satisfied" is resolved by `ObjectivePolicy`
# itself, since it also depends on the configured penalty threshold.
_HEADLINE_DISPOSITION: Mapping[str, str] = {
    "violated": "reject",
    "indeterminate": "keep-for-boundary",
    "not_assessed": "keep-for-boundary",
}


def _beyond_penalty_threshold(objective: ObjectiveSpec, value: float) -> bool:
    if objective.penalty_threshold is None or not math.isfinite(value):
        return False
    if objective.role == "maximize":
        return value < objective.penalty_threshold
    return value > objective.penalty_threshold  # minimize | penalty


class ObjectivePolicy:
    """The real study-policy interpretation: extracts configured objectives
    and response roles from immutable evidence, then maps the headline
    verdict (plus, for "satisfied", each objective's raw value against its
    configured `penalty_threshold`) to one of the four dispositions
    (design.md#the-policy).
    """

    def __init__(
        self,
        objectives: tuple[ObjectiveSpec, ...],
        response_roles: Mapping[str, str],
        config: Any = None,
    ) -> None:
        self.objectives = tuple(objectives)
        self.response_roles = dict(response_roles)

    def assess(self, evidence: ModelEvidence, *, candidate_id: str) -> dict[str, Any]:
        objective_values: dict[str, float] = {}
        for objective in self.objectives:
            if objective.output not in evidence.outputs:
                raise AssessmentFailed(
                    f"{candidate_id}: objective output {objective.output!r} "
                    "absent from evidence.outputs"
                )
            objective_values[objective.output] = evidence.outputs[objective.output]

        for role, constraint_id in self.response_roles.items():
            if constraint_id not in evidence.responses:
                raise AssessmentFailed(
                    f"{candidate_id}: response role {role!r} names constraint "
                    f"{constraint_id!r}, absent from evidence.responses"
                )

        headline = evidence.responses["headline"]
        if headline != "satisfied":
            disposition = _HEADLINE_DISPOSITION[headline]
            return {
                "disposition": disposition, "headline": headline,
                "objectives": objective_values, "penalty": None,
            }

        for objective in self.objectives:
            value = objective_values[objective.output]
            if _beyond_penalty_threshold(objective, value):
                return {
                    "disposition": "penalize", "headline": headline,
                    "objectives": objective_values, "penalty": value,
                }
        return {
            "disposition": "feed-strategy", "headline": headline,
            "objectives": objective_values, "penalty": None,
        }


PolicyFactory = Callable[[tuple[ObjectiveSpec, ...], Mapping[str, str], Any], Policy]

# name -> factory(objectives, response_roles, policy_config). `policy_config`
# is the raw `study.config.PolicyConfig` (typed loosely here to avoid a
# policy<->config import cycle; only `ObjectivePolicy` needs it, and only for
# future per-name config, not today).
POLICY_REGISTRY: dict[str, PolicyFactory] = {
    "objective/v1": ObjectivePolicy,
}
