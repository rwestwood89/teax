"""Constraint module for f1_division_check (Item 7 / D2/D3/D9).

Effective predicate: f1_arithmetic::Fixture::f1_division_check in owner instance toy_plant__fixture.
Three-valued (Kleene) semantics. A verdict against the assertion does not itself raise (INV-3).
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from f1_arithmetic_constraints.schemas.constraint_types import ConstraintEvaluation
from f1_arithmetic_constraints.modules.constraints.predicates import constraint_pred_f1_arithmetic__fixture__f1_division_check


class FixtureF1DivisionCheckConstraintInput(BaseModel):
    """Exact input schema: one field per resolved formal."""
    a: float
    b: float


class FixtureF1DivisionCheckConstraintOutput(MultiOutput):
    evaluation: ConstraintEvaluation


class FixtureF1DivisionCheckConstraintModule(ModuleBase[FixtureF1DivisionCheckConstraintInput, FixtureF1DivisionCheckConstraintOutput]):
    name: str = "f1_division_check"
    version: str = "v0.1"

    CONSTRAINT_ID = "f1_division_check"

    def run(self, a: float, b: float) -> ModuleResult[FixtureF1DivisionCheckConstraintOutput]:
        FixtureF1DivisionCheckConstraintInput(a=a, b=b)  # validate every resolved formal
        verdict = constraint_pred_f1_arithmetic__fixture__f1_division_check(a=a, b=b)
        return ModuleResult(
            data=FixtureF1DivisionCheckConstraintOutput(
                evaluation=ConstraintEvaluation(
                    constraint_id=self.CONSTRAINT_ID,
                    actual_value=verdict.actual_value,
                    status=verdict.status,
                    margin=verdict.margin,
                    observed={"a": float(a), "b": float(b)},
                )
            )
        )
