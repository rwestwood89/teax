"""Unit tests for projection.project against a fake, duck-typed report.

No generated package needed — these fakes only need to expose the same
attribute shape (.headline, .results, .constraint_id, .status) the real
generated ConstraintReport/ConstraintEvaluation expose.
"""
from __future__ import annotations

import pytest

from types import MappingProxyType

from simkit.evaluation.evidence import EvidenceProvenance
from simkit.evaluation.projection import REPORT_CHANNEL, project


def _plain(value):
    """Recursively convert a deep-frozen tree back to plain dict/list for
    by-value comparison (the sealed report is MappingProxyType/tuple)."""
    if isinstance(value, MappingProxyType):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    return value


class FakeConstraintEvaluation:
    def __init__(self, constraint_id: str, status: str) -> None:
        self.constraint_id = constraint_id
        self.status = status


class FakeReport:
    def __init__(self, headline: str, results: list[FakeConstraintEvaluation]) -> None:
        self.headline = headline
        self.results = results

    def model_dump(self, *, mode: str = "python") -> dict:
        """Mirror the generated report's `model_dump(mode="json")` — the shape
        `project` seals into `ModelEvidence.report` (D2)."""
        return {
            "headline": self.headline,
            "results": [
                {"constraint_id": r.constraint_id, "status": r.status} for r in self.results
            ],
        }


class FakeRootModel:
    def __init__(self, value: float) -> None:
        self.root = value


class FakeRunResult:
    def __init__(self, outputs: dict) -> None:
        self.outputs = outputs


PROVENANCE = EvidenceProvenance(
    executable_fingerprint="fp",
    evidence_schema_version="v1",
    evaluator_version="v1",
    input_digest="digest",
)


@pytest.mark.parametrize(
    "generated_headline,canonical",
    [
        ("full_satisfaction", "satisfied"),
        ("violation", "violated"),
        ("indeterminate", "indeterminate"),
        ("partial_coverage", "partial_coverage"),
        ("not_assessed", "not_assessed"),
    ],
)
def test_headline_normalization(generated_headline, canonical):
    report = FakeReport(headline=generated_headline, results=[])
    result = FakeRunResult(outputs={REPORT_CHANNEL: report})

    evidence = project(result, provenance=PROVENANCE, expects_report=True)

    assert evidence.responses["headline"] == canonical


def test_per_constraint_status_pass_through():
    report = FakeReport(
        headline="full_satisfaction",
        results=[
            FakeConstraintEvaluation("toy_plant__demo_plant__affordable", "satisfied"),
        ],
    )
    result = FakeRunResult(outputs={REPORT_CHANNEL: report})

    evidence = project(result, provenance=PROVENANCE, expects_report=True)

    assert evidence.responses["toy_plant__demo_plant__affordable"] == "satisfied"


def test_output_unwrap_and_non_scalar_exclusion():
    report = FakeReport(headline="full_satisfaction", results=[])
    result = FakeRunResult(
        outputs={
            "area": FakeRootModel(12.0),
            "cost": FakeRootModel(3000.0),
            "evaluation": FakeConstraintEvaluation("x", "satisfied"),
            "constraint_report": report,
        }
    )

    evidence = project(result, provenance=PROVENANCE, expects_report=True)

    assert evidence.outputs == {"area": 12.0, "cost": 3000.0}


def test_report_attached_as_faithful_frozen_copy():
    report = FakeReport(
        headline="full_satisfaction",
        results=[FakeConstraintEvaluation("c1", "satisfied")],
    )
    result = FakeRunResult(outputs={REPORT_CHANNEL: report})

    evidence = project(result, provenance=PROVENANCE, expects_report=True)

    # Attached by value (the sealed model_dump tree), not the live object.
    assert _plain(evidence.report) == report.model_dump(mode="json")
    assert evidence.report is not report


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("value", [0, -7, 2.5, float("nan"), float("inf"), float("-inf")])
def test_numeric_forms_survive_projection_and_codec(value, wrapped):
    import math

    from simkit.study.evidence_io import decode_evidence, encode_evidence

    output = FakeRootModel(value) if wrapped else value
    evidence = project(FakeRunResult({"exit_alias": output}), provenance=PROVENANCE, expects_report=False)
    decoded = decode_evidence(encode_evidence(evidence))
    assert set(evidence.outputs) == {"exit_alias"}
    actual = decoded["outputs"]["exit_alias"]
    assert isinstance(actual, float)
    assert math.isnan(actual) if math.isnan(value) else actual == float(value)


@pytest.mark.parametrize("value", [True, False, "2.5", None, [2.5], {"number": 2.5}])
@pytest.mark.parametrize("wrapped", [False, True])
def test_nonnumeric_forms_excluded(value, wrapped):
    output = FakeRootModel(value) if wrapped else value
    evidence = project(FakeRunResult({"excluded": output}), provenance=PROVENANCE, expects_report=False)
    assert evidence.outputs == {}
