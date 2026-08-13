"""Constraint report aggregator (Item 7 / D5/D11) — exact schema, one required field per
eligible assertion.

Exists even for zero eligible assertions (D11): a missing result is a schema failure, never a
silent gap.
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from f1_arithmetic_constraints.schemas.constraint_types import (
    ConstraintEvaluation,
    ConstraintReport,
    CoverageAccount,
)

EXPECTED_IDS = ('toy_plant_fixture_f3_nested_check_8b3352fdf1f62ba5', 'toy_plant_fixture_f1_division_check_b973058cd670a967', 'toy_plant_fixture_f2_power_check_b4ca916c6d129ce9')

#: The coverage account, derived at generation from the sealed catalog by
#: `generation/coverage.py::coverage_account` and baked here exactly the way
#: CATALOG_FINGERPRINT and EXPECTED_IDS are. Which gates are applicable and which were
#: assessed depends on the model, never on this candidate's input values, so recomputing it
#: per evaluation would recompute a constant.
COVERAGE = {'authored_usage_total': 3, 'applicable_gate_total': 3, 'assessed_gate_count': 3, 'unassessed_gate_count': 0, 'inapplicable_gate_count': 0, 'unassessed_reasons': {}, 'coverage_state': 'complete'}


class ConstraintReportAggregatorInput(BaseModel):
    model_config = {"extra": "forbid"}

    toy_plant_fixture_f3_nested_check_8b3352fdf1f62ba5: ConstraintEvaluation
    toy_plant_fixture_f1_division_check_b973058cd670a967: ConstraintEvaluation
    toy_plant_fixture_f2_power_check_b4ca916c6d129ce9: ConstraintEvaluation


class ConstraintReportAggregatorOutput(MultiOutput):
    constraint_report: ConstraintReport


class ConstraintReportAggregatorModule(
    ModuleBase[ConstraintReportAggregatorInput, ConstraintReportAggregatorOutput]
):
    name: str = "constraint_report_aggregator"
    version: str = "v0.1"

    CATALOG_FINGERPRINT = "53cc6d2914d6fb738c85e6554b34f28506d2a0c56e956765f1ccb95069688d51"

    def run(self, **evaluations) -> ModuleResult[ConstraintReportAggregatorOutput]:
        validated = ConstraintReportAggregatorInput(**evaluations)
        results = [getattr(validated, cid) for cid in EXPECTED_IDS]
        statuses = [r.status for r in results]
        coverage = CoverageAccount(**COVERAGE)

        # Statuses decide the top two arms; the account decides the rest. The status set
        # contains only occurrences of applicable assessed gates by construction, so the
        # `violation` arm cannot fire from a gate outside the denominator: an inapplicable
        # gate is either unassessed (no entries, no results) or refused at generation.
        #
        # Result-list non-emptiness stops deciding anything. That was the whole defect —
        # `all_satisfied` meant "nothing that arrived failed", whatever fraction arrived.
        if "violated" in statuses:
            headline = "violation"
        elif "indeterminate" in statuses:
            headline = "indeterminate"
        elif coverage.unassessed_gate_count == 0 and coverage.assessed_gate_count > 0:
            headline = "full_satisfaction"
        elif coverage.applicable_gate_total > 0:
            headline = "partial_coverage"
        else:
            headline = "not_assessed"
        return ModuleResult(
            data=ConstraintReportAggregatorOutput(
                constraint_report=ConstraintReport(
                    catalog_fingerprint=self.CATALOG_FINGERPRINT,
                    assessed_entry_count=len(results),
                    headline=headline,
                    coverage=coverage,
                    results=results,
                )
            )
        )
