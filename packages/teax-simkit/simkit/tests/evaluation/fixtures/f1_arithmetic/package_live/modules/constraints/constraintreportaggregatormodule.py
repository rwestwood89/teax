"""Constraint report aggregator (Item 7 / D5/D11) — exact schema, one required field per
eligible assertion.

Exists even for zero eligible assertions (D11): a missing result is a schema failure, never a
silent gap.
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from f1_arithmetic_constraints.schemas.constraint_types import ConstraintEvaluation, ConstraintReport

EXPECTED_IDS = ('f1_division_check', 'f2_power_check', 'f3_nested_check')


class ConstraintReportAggregatorInput(BaseModel):
    model_config = {"extra": "forbid"}

    f1_division_check: ConstraintEvaluation
    f2_power_check: ConstraintEvaluation
    f3_nested_check: ConstraintEvaluation


class ConstraintReportAggregatorOutput(MultiOutput):
    constraint_report: ConstraintReport


class ConstraintReportAggregatorModule(
    ModuleBase[ConstraintReportAggregatorInput, ConstraintReportAggregatorOutput]
):
    name: str = "constraint_report_aggregator"
    version: str = "v0.1"

    CATALOG_FINGERPRINT = "fc026ea0a166bfa5c3afb2d15e88b5f417f7a011aadf74c0d64031d2b80d65f1"

    def run(self, **evaluations) -> ModuleResult[ConstraintReportAggregatorOutput]:
        validated = ConstraintReportAggregatorInput(**evaluations)
        results = [getattr(validated, cid) for cid in EXPECTED_IDS]
        statuses = [r.status for r in results]
        if "violated" in statuses:
            headline = "violation"
        elif "indeterminate" in statuses:
            headline = "indeterminate"
        elif results:
            headline = "all_satisfied"
        else:
            headline = "not_assessed"
        return ModuleResult(
            data=ConstraintReportAggregatorOutput(
                constraint_report=ConstraintReport(
                    catalog_fingerprint=self.CATALOG_FINGERPRINT,
                    assessed_count=len(results),
                    headline=headline,
                    results=results,
                )
            )
        )
