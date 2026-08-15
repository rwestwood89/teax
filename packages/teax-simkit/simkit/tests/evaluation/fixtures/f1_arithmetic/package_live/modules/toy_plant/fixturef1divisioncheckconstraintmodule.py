"""Constraint module for toy_plant__fixture__f1_division_check__b973058cd670a967 (Item 7 / D2/D3/D9).

Effective predicate: toy_plant::'Toy Plant'::f1_division_check in owner instance toy_plant__fixture.
Three-valued (Kleene) semantics. A verdict against the assertion does not itself raise (INV-3).
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from f1_arithmetic_constraints.schemas.constraint_types import ConstraintEvaluation
from f1_arithmetic_constraints.modules.constraints.predicates import _finalize_assertion, constraint_pred_inline_toy_plant__toy_plant__f1_division_check


class FixtureF1DivisionCheckConstraintInput(BaseModel):
    """Exact input schema: one field per resolved formal."""
    division_b: float
    division_a: float


class FixtureF1DivisionCheckConstraintOutput(MultiOutput):
    evaluation: ConstraintEvaluation


class FixtureF1DivisionCheckConstraintModule(ModuleBase[FixtureF1DivisionCheckConstraintInput, FixtureF1DivisionCheckConstraintOutput]):
    name: str = "toy_plant__fixture__f1_division_check__b973058cd670a967"
    version: str = "v0.1"

    CONSTRAINT_ID = "toy_plant__fixture__f1_division_check__b973058cd670a967"

    def run(self, division_b: float, division_a: float) -> ModuleResult[FixtureF1DivisionCheckConstraintOutput]:
        FixtureF1DivisionCheckConstraintInput(division_b=division_b, division_a=division_a)  # validate every resolved formal
        body = constraint_pred_inline_toy_plant__toy_plant__f1_division_check(division_a=division_a, division_b=division_b)
        verdict = _finalize_assertion(
            body,
            is_negated=False,
            expected_value=True,
        )
        return ModuleResult(
            data=FixtureF1DivisionCheckConstraintOutput(
                evaluation=ConstraintEvaluation(
                    constraint_id=self.CONSTRAINT_ID,
                    actual_value=verdict.actual_value,
                    status=verdict.status,
                    margin=verdict.margin,
                    observed={"division_a": float(division_a), "division_b": float(division_b)},
                )
            )
        )
