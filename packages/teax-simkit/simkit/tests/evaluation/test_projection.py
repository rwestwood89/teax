"""Unit tests for projection.project against a fake, duck-typed report.

No generated package needed — these fakes only need to expose the same
attribute shape (.headline, .results, .constraint_id, .status) the real
generated ConstraintReport/ConstraintEvaluation expose.
"""
from __future__ import annotations

import pytest

from simkit.evaluation.evidence import EvidenceProvenance
from simkit.evaluation.projection import project


class FakeConstraintEvaluation:
    def __init__(self, constraint_id: str, status: str) -> None:
        self.constraint_id = constraint_id
        self.status = status


class FakeReport:
    def __init__(self, headline: str, results: list[FakeConstraintEvaluation]) -> None:
        self.headline = headline
        self.results = results


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
        ("all_satisfied", "satisfied"),
        ("violation", "violated"),
        ("indeterminate", "indeterminate"),
        ("not_assessed", "not_assessed"),
    ],
)
def test_headline_normalization(generated_headline, canonical):
    report = FakeReport(headline=generated_headline, results=[])
    result = FakeRunResult(outputs={})

    evidence = project(result, report, provenance=PROVENANCE)

    assert evidence.responses["headline"] == canonical


def test_per_constraint_status_pass_through():
    report = FakeReport(
        headline="all_satisfied",
        results=[
            FakeConstraintEvaluation("toy_plant__demo_plant__affordable", "satisfied"),
        ],
    )
    result = FakeRunResult(outputs={})

    evidence = project(result, report, provenance=PROVENANCE)

    assert evidence.responses["toy_plant__demo_plant__affordable"] == "satisfied"


def test_output_unwrap_and_non_scalar_exclusion():
    report = FakeReport(headline="all_satisfied", results=[])
    result = FakeRunResult(
        outputs={
            "area": FakeRootModel(12.0),
            "cost": FakeRootModel(3000.0),
            "evaluation": FakeConstraintEvaluation("x", "satisfied"),
            "constraint_report": report,
        }
    )

    evidence = project(result, report, provenance=PROVENANCE)

    assert evidence.outputs == {"area": 12.0, "cost": 3000.0}


def test_report_attached_unchanged():
    report = FakeReport(headline="all_satisfied", results=[])
    result = FakeRunResult(outputs={})

    evidence = project(result, report, provenance=PROVENANCE)

    assert evidence.report is report
