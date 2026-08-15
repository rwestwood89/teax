"""Constraint module for toy_plant__fixture__f2_power_check__b4ca916c6d129ce9 (Item 7 / D2/D3/D9).

Effective predicate: toy_plant::'Toy Plant'::f2_power_check in owner instance toy_plant__fixture.
Three-valued (Kleene) semantics. A verdict against the assertion does not itself raise (INV-3).
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from f1_arithmetic_constraints.schemas.constraint_types import ConstraintEvaluation
from f1_arithmetic_constraints.modules.constraints.predicates import _finalize_assertion, constraint_pred_inline_toy_plant__toy_plant__f2_power_check


class FixtureF2PowerCheckConstraintInput(BaseModel):
    """Exact input schema: one field per resolved formal."""
    power_a: float
    power_b: float


class FixtureF2PowerCheckConstraintOutput(MultiOutput):
    evaluation: ConstraintEvaluation


class FixtureF2PowerCheckConstraintModule(ModuleBase[FixtureF2PowerCheckConstraintInput, FixtureF2PowerCheckConstraintOutput]):
    name: str = "toy_plant__fixture__f2_power_check__b4ca916c6d129ce9"
    version: str = "v0.1"

    CONSTRAINT_ID = "toy_plant__fixture__f2_power_check__b4ca916c6d129ce9"

    def run(self, power_a: float, power_b: float) -> ModuleResult[FixtureF2PowerCheckConstraintOutput]:
        FixtureF2PowerCheckConstraintInput(power_a=power_a, power_b=power_b)  # validate every resolved formal
        body = constraint_pred_inline_toy_plant__toy_plant__f2_power_check(power_a=power_a, power_b=power_b)
        verdict = _finalize_assertion(
            body,
            is_negated=False,
            expected_value=True,
        )
        return ModuleResult(
            data=FixtureF2PowerCheckConstraintOutput(
                evaluation=ConstraintEvaluation(
                    constraint_id=self.CONSTRAINT_ID,
                    actual_value=verdict.actual_value,
                    status=verdict.status,
                    margin=verdict.margin,
                    observed={"power_a": float(power_a), "power_b": float(power_b)},
                )
            )
        )
