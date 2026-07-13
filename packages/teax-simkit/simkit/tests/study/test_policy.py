"""Phase 3: `ObjectivePolicy` — the four dispositions, the genuine
`AssessmentFailed` extraction rule, raw (non-normalized) penalty, and
non-mutation of evidence across differing assessments (INV-1).
"""
from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import BaseModel

from simkit.evaluation.evidence import EvidenceProvenance, ModelEvidence
from simkit.study.evidence_io import encode_evidence
from simkit.study.identity import canonical_bytes, mint_candidate_id
from simkit.study.policy import AssessmentFailed, ObjectivePolicy, ObjectiveSpec

from .conftest import NamedFaultEvaluator, STUDY_ID, run_study

COST = "toy_plant__demo_plant__cost_calc__cost"
AFFORDABLE = "toy_plant__demo_plant__affordable"


class _StubReport(BaseModel):
    """Evidence's `report` is opaque `Any`, read only via `model_dump` by
    `encode_evidence` — a minimal stand-in for the generated report type."""

    stub: bool = True


def _evidence(headline: str, outputs: dict, responses: dict | None = None) -> ModelEvidence:
    provenance = EvidenceProvenance(
        executable_fingerprint="fp-A", evidence_schema_version="v1",
        evaluator_version="v1", input_digest="digest-A",
    )
    resp = {"headline": headline, **(responses or {})}
    return ModelEvidence(responses=resp, outputs=outputs, provenance=provenance, report=_StubReport())


def test_reject_on_violated():
    policy = ObjectivePolicy((ObjectiveSpec(COST, "minimize"),), {})
    evidence = _evidence("violated", {COST: 5000.0})
    result = policy.assess(evidence, candidate_id="c1")
    assert result["disposition"] == "reject"
    assert result["penalty"] is None


def test_keep_for_boundary_on_indeterminate_and_not_assessed():
    policy = ObjectivePolicy((ObjectiveSpec(COST, "minimize"),), {})
    for headline in ("indeterminate", "not_assessed"):
        evidence = _evidence(headline, {COST: float("nan")})
        result = policy.assess(evidence, candidate_id="c1")
        assert result["disposition"] == "keep-for-boundary"


def test_feed_strategy_on_satisfied_within_threshold():
    policy = ObjectivePolicy((ObjectiveSpec(COST, "minimize", penalty_threshold=4000.0),), {})
    evidence = _evidence("satisfied", {COST: 3000.0})
    result = policy.assess(evidence, candidate_id="c1")
    assert result["disposition"] == "feed-strategy"
    assert result["penalty"] is None


def test_penalize_on_satisfied_beyond_threshold_carries_raw_value():
    policy = ObjectivePolicy((ObjectiveSpec(COST, "minimize", penalty_threshold=2000.0),), {})
    evidence = _evidence("satisfied", {COST: 3000.0})
    result = policy.assess(evidence, candidate_id="c1")
    assert result["disposition"] == "penalize"
    assert result["penalty"] == 3000.0  # raw modeled quantity, never normalized


def test_penalize_direction_respects_maximize_role():
    policy = ObjectivePolicy((ObjectiveSpec("yield", "maximize", penalty_threshold=10.0),), {})
    below = policy.assess(_evidence("satisfied", {"yield": 5.0}), candidate_id="c1")
    above = policy.assess(_evidence("satisfied", {"yield": 15.0}), candidate_id="c2")
    assert below["disposition"] == "penalize"
    assert above["disposition"] == "feed-strategy"


def test_assessment_failed_on_missing_objective_output():
    policy = ObjectivePolicy((ObjectiveSpec("no_such_output", "minimize"),), {})
    evidence = _evidence("satisfied", {COST: 3000.0})
    with pytest.raises(AssessmentFailed):
        policy.assess(evidence, candidate_id="c1")


def test_assessment_failed_on_unresolved_response_role():
    policy = ObjectivePolicy((), {"primary": "no_such_constraint"})
    evidence = _evidence("satisfied", {})
    with pytest.raises(AssessmentFailed):
        policy.assess(evidence, candidate_id="c1")


def test_well_formed_verdict_and_nonfinite_objective_are_not_failures():
    """Indeterminate headline + a non-finite objective value are interpreted,
    never treated as an extraction failure."""
    policy = ObjectivePolicy((ObjectiveSpec(COST, "minimize"),), {AFFORDABLE: AFFORDABLE})
    evidence = _evidence(
        "indeterminate", {COST: float("nan")}, responses={AFFORDABLE: "indeterminate"}
    )
    result = policy.assess(evidence, candidate_id="c1")
    assert result["disposition"] == "keep-for-boundary"


def test_evidence_digest_identical_across_dispositions():
    """INV-1: the policy never mutates evidence — the bytes `commit_case`
    would stage are unaffected by which policy/verdict assessed it."""
    evidence = _evidence("satisfied", {COST: 3000.0})

    def digest_of_encoded() -> str:
        return hashlib.sha256(canonical_bytes(encode_evidence(evidence))).hexdigest()

    before = digest_of_encoded()
    ObjectivePolicy((ObjectiveSpec(COST, "minimize", penalty_threshold=1.0),), {}).assess(
        evidence, candidate_id="c1"
    )  # -> penalize
    ObjectivePolicy((ObjectiveSpec(COST, "minimize"),), {}).assess(
        evidence, candidate_id="c1"
    )  # -> feed-strategy
    after = digest_of_encoded()

    assert before == after


def test_rejected_point_is_completed_case_not_assessment_failed(tmp_path, prepared):
    """INV-2: a policy-rejected point is a `completed` case whose
    `assessment_json.disposition == "reject"` — distinct from
    `assessment_failed`, which means the policy itself broke."""
    policy = ObjectivePolicy((ObjectiveSpec(COST, "minimize"),), {})
    store = run_study(tmp_path, prepared, NamedFaultEvaluator(prepared), policy)
    try:
        violated_candidate_id = mint_candidate_id(STUDY_ID, 1)  # budget=1000 < cost=3000
        row = next(c for c in store.ordered_cases() if c["candidate_id"] == violated_candidate_id)
        assert row["state"] == "completed"
        assert row["evidence_digest"] is not None
        assert json.loads(row["assessment_json"])["disposition"] == "reject"
    finally:
        store.close()
