"""Constraint report aggregator (Item 7 / D5/D11) — exact schema, one required field per
eligible assertion.

Exists even for zero eligible assertions (D11): a missing result is a schema failure, never a
silent gap.
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from wi014_s4.schemas.constraint_types import ConstraintEvaluation, ConstraintReport

EXPECTED_IDS = ('toy_plant_demo_plant_affordable_c122240f4b148939',)


class ConstraintReportAggregatorInput(BaseModel):
    model_config = {"extra": "forbid"}

    toy_plant_demo_plant_affordable_c122240f4b148939: ConstraintEvaluation


class ConstraintReportAggregatorOutput(MultiOutput):
    constraint_report: ConstraintReport


class ConstraintReportAggregatorModule(
    ModuleBase[ConstraintReportAggregatorInput, ConstraintReportAggregatorOutput]
):
    name: str = "constraint_report_aggregator"
    version: str = "v0.1"

    CATALOG_FINGERPRINT = "4a0b47a586f39c54ff9ffc4bb22d21aeae26ce9bbde95a3f751d9af8e3525a27"

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
