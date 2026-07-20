"""Constraint report aggregator (Item 7 / D5/D11) — exact schema, one required field per
eligible assertion.

Exists even for zero eligible assertions (D11): a missing result is a schema failure, never a
silent gap.
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from zero_channel.schemas.constraint_types import ConstraintEvaluation, ConstraintReport

EXPECTED_IDS = ('zero_plant_zeroPlant_within_6c6ab9e3b1afb20e',)


class ConstraintReportAggregatorInput(BaseModel):
    model_config = {"extra": "forbid"}

    zero_plant_zeroPlant_within_6c6ab9e3b1afb20e: ConstraintEvaluation


class ConstraintReportAggregatorOutput(MultiOutput):
    constraint_report: ConstraintReport


class ConstraintReportAggregatorModule(
    ModuleBase[ConstraintReportAggregatorInput, ConstraintReportAggregatorOutput]
):
    name: str = "constraint_report_aggregator"
    version: str = "v0.1"

    CATALOG_FINGERPRINT = "ead563949377c3163ff3ac5e82eba6e5e708eb19fd79f8aedcb393466e6ad2d2"

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
