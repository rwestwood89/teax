"""Assessment/policy seam: a `Policy` protocol and a minimal `DispositionPolicy`.

Just enough to produce the three case states and exercise
`assessment_failed`. The full study-policy interpretation protocol, result
queries, and CLI are Item 12 (spec.md#assessment-policy-boundary);
`ModelEvidence` is never mutated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

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
