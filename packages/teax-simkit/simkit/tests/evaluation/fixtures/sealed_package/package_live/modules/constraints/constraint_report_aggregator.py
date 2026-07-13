"""Constraint report aggregator (S4 test-only generation).

Exact input schema: one REQUIRED field per concrete assertion — a missing
result is a schema failure, not a silent gap. Exists even for zero assertions.
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from wi014_s4.schemas.constraint_types import ConstraintEvaluation, ConstraintReport

EXPECTED_IDS = ('toy_plant__demo_plant__affordable',)


class ConstraintReportAggregatorInput(BaseModel):
    model_config = {"extra": "forbid"}

    toy_plant__demo_plant__affordable: ConstraintEvaluation


class ConstraintReportAggregatorOutput(MultiOutput):
    constraint_report: ConstraintReport


class ConstraintReportAggregatorModule(
    ModuleBase[ConstraintReportAggregatorInput, ConstraintReportAggregatorOutput]
):
    name: str = "constraint_report_aggregator"
    version: str = "s4-probe"

    CATALOG_FINGERPRINT = "659d0298caaa51ac4f4f9bee5ecde14d9ef929cf5c8ced3ca2e7857bce87d00f"

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
