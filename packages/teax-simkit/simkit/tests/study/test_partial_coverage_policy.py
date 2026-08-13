"""A partially-covered candidate stays out of the steering loop unless a study says otherwise.

The conservative default is the whole point of `partial_coverage` existing as a disposition:
"every gate that ran passed" is not "this candidate is feasible", and a design search that
conflates them steers on gates nobody checked. So the default is `keep-for-boundary` — kept as
boundary evidence, excluded from the strategy's feed.

The opt-in is deliberately *only* reachable by an explicit config line, and taking it puts
`partial_coverage` on the identical path `satisfied` takes rather than a third bespoke one, so its
disposition is always explainable by the configuration. Both directions are pinned here, plus the
lineage consequence: because the whole policy block is digested into
`StudyConfig.semantic_fingerprint()`, flipping the line starts a new study lineage instead of
silently changing a running study's meaning.
"""

from __future__ import annotations

import pytest

from simkit.evaluation.evidence import EvidenceProvenance, ModelEvidence
from simkit.study.config import PolicyConfig
from simkit.study.policy import DispositionPolicy, ObjectivePolicy, ObjectiveSpec

COST = "toy_plant__demo_plant__cost_calc__cost"

#: A real partial account: one applicable gate, none assessed, and the reason it was not.
PARTIAL_COVERAGE = {
    "authored_usage_total": 2,
    "applicable_gate_total": 2,
    "assessed_gate_count": 1,
    "unassessed_gate_count": 1,
    "inapplicable_gate_count": 0,
    "unassessed_reasons": {"owner_has_no_occurrences": 1},
    "coverage_state": "partial",
}


def _partial_evidence() -> ModelEvidence:
    return ModelEvidence(
        responses={"headline": "partial_coverage"},
        outputs={COST: 3000.0},
        provenance=EvidenceProvenance(
            executable_fingerprint="fp-A",
            evidence_schema_version="v2",
            evaluator_version="v1",
            input_digest="digest-A",
        ),
        report={
            "catalog_fingerprint": "cat-fp-A",
            "assessed_entry_count": 1,
            "headline": "partial_coverage",
            "coverage": PARTIAL_COVERAGE,
            "results": [],
        },
    )


def _objective_policy(config: PolicyConfig | None) -> ObjectivePolicy:
    return ObjectivePolicy(
        (ObjectiveSpec(output=COST, role="minimize"),), {}, config
    )


# ---------------------------------------------------------------------------
# The default: out of the steering loop
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "config",
    [None, PolicyConfig(name="objective/v1"), PolicyConfig(name="objective/v1", partial_coverage="keep-for-boundary")],
    ids=["no-config", "config-without-the-line", "config-with-the-line-explicit"],
)
def test_partial_coverage_defaults_to_keep_for_boundary(config):
    """Three ways of not opting in, all reaching the same conservative disposition."""
    assessment = _objective_policy(config).assess(_partial_evidence(), candidate_id="c0")
    assert assessment["disposition"] == "keep-for-boundary"
    assert assessment["headline"] == "partial_coverage"


def test_the_opt_in_line_moves_it_into_the_steering_loop():
    """`feed-strategy` is reachable only by writing the line — nothing else flips it."""
    config = PolicyConfig(name="objective/v1", partial_coverage="feed-strategy")
    assessment = _objective_policy(config).assess(_partial_evidence(), candidate_id="c0")
    assert assessment["disposition"] == "feed-strategy"
    # It took the identical path `satisfied` takes, so the record carries objective values and
    # a penalty slot rather than a third bespoke shape nobody can explain from the config.
    assert assessment["objectives"] == {COST: 3000.0}
    assert assessment["penalty"] is None
    # And it never stops saying what it is.
    assert assessment["headline"] == "partial_coverage"


@pytest.mark.parametrize(
    "opt_in,expected",
    [("keep-for-boundary", "keep-for-boundary"), ("feed-strategy", "feed-strategy")],
)
def test_both_dispositions_persist_the_coverage_counts(opt_in, expected):
    """Whichever way it is dispositioned, the account reaches the durable case record.

    That is what lets a study query separate "kept at the boundary because two of sixty gates
    ran" from "kept at the boundary because one did" without opening evidence artifacts.
    """
    config = PolicyConfig(name="objective/v1", partial_coverage=opt_in)
    assessment = _objective_policy(config).assess(_partial_evidence(), candidate_id="c0")

    assert assessment["disposition"] == expected
    assert assessment["coverage"] == PARTIAL_COVERAGE
    assert assessment["catalog_fingerprint"] == "cat-fp-A"
    # Plain enough to serialize into the case row (the evidence copy stays frozen).
    import json

    json.dumps(assessment)


def test_the_other_dispatch_table_also_carries_the_counts():
    """`DispositionPolicy` is the extraction-independent half and must not diverge."""
    assessment = DispositionPolicy().assess(_partial_evidence(), candidate_id="c0")
    assert assessment["disposition"] == "partial_coverage"
    assert assessment["coverage"] == PARTIAL_COVERAGE


# ---------------------------------------------------------------------------
# The lineage consequence
# ---------------------------------------------------------------------------


def test_the_opt_in_starts_a_new_study_lineage():
    """Flipping the line must not silently change a running study's meaning.

    The policy block is digested whole into `semantic_fingerprint`, so the two configs are
    different study definitions and the store refuses to reopen across them.
    """
    default = PolicyConfig(name="objective/v1")
    opted_in = PolicyConfig(name="objective/v1", partial_coverage="feed-strategy")
    assert default.model_dump() != opted_in.model_dump()


def test_a_typo_in_the_opt_in_fails_closed():
    """`extra="forbid"` and the `Literal` between them leave no third spelling."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PolicyConfig(name="objective/v1", partial_coverage="feed_strategy")
    with pytest.raises(ValidationError):
        PolicyConfig(name="objective/v1", partial_covrage="feed-strategy")
