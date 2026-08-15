"""Constraint module for toy_plant__fixture__f3_nested_check__8b3352fdf1f62ba5 (Item 7 / D2/D3/D9).

Effective predicate: toy_plant::'Toy Plant'::f3_nested_check in owner instance toy_plant__fixture.
Three-valued (Kleene) semantics. A verdict against the assertion does not itself raise (INV-3).
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from f1_arithmetic_constraints.schemas.constraint_types import ConstraintEvaluation
from f1_arithmetic_constraints.modules.constraints.predicates import _finalize_assertion, constraint_pred_inline_toy_plant__toy_plant__f3_nested_check


class FixtureF3NestedCheckConstraintInput(BaseModel):
    """Exact input schema: one field per resolved formal."""
    nested_a: float
    nested_b: float


class FixtureF3NestedCheckConstraintOutput(MultiOutput):
    evaluation: ConstraintEvaluation


class FixtureF3NestedCheckConstraintModule(ModuleBase[FixtureF3NestedCheckConstraintInput, FixtureF3NestedCheckConstraintOutput]):
    name: str = "toy_plant__fixture__f3_nested_check__8b3352fdf1f62ba5"
    version: str = "v0.1"

    CONSTRAINT_ID = "toy_plant__fixture__f3_nested_check__8b3352fdf1f62ba5"

    def run(self, nested_a: float, nested_b: float) -> ModuleResult[FixtureF3NestedCheckConstraintOutput]:
        FixtureF3NestedCheckConstraintInput(nested_a=nested_a, nested_b=nested_b)  # validate every resolved formal
        body = constraint_pred_inline_toy_plant__toy_plant__f3_nested_check(nested_a=nested_a, nested_b=nested_b)
        verdict = _finalize_assertion(
            body,
            is_negated=False,
            expected_value=True,
        )
        return ModuleResult(
            data=FixtureF3NestedCheckConstraintOutput(
                evaluation=ConstraintEvaluation(
                    constraint_id=self.CONSTRAINT_ID,
                    actual_value=verdict.actual_value,
                    status=verdict.status,
                    margin=verdict.margin,
                    observed={"nested_a": float(nested_a), "nested_b": float(nested_b)},
                )
            )
        )
