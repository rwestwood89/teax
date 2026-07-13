"""Constraint module for toy_plant__demo_plant__affordable (S4 test-only generation).

Effective predicate: toy_library::'Cost Within Budget' in owner instance toy_plant__demo_plant.
Membership: assert; negated: False.
Three-valued (Kleene) semantics; a verdict against the assertion NEVER raises.
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from wi014_s4.schemas.constraint_types import ConstraintEvaluation


import math

def _fin(x):
    return isinstance(x, (int, float)) and math.isfinite(x)

def _cmp(op, a, b):
    """Leaf comparison: unknown (None) if either operand is non-finite."""
    if not _fin(a) or not _fin(b):
        return None
    if op == "<=": return a <= b
    if op == ">=": return a >= b
    if op == "<":  return a < b
    if op == ">":  return a > b
    if op == "==": return a == b
    if op == "!=": return a != b
    raise ValueError(f"not a comparison: {op}")

def _and(*vals):
    if any(v is False for v in vals): return False
    if any(v is None for v in vals): return None
    return True

def _or(*vals):
    if any(v is True for v in vals): return True
    if any(v is None for v in vals): return None
    return False

def _not(v):
    return None if v is None else (not v)


def _predicate(cost, budget):
    value = _cmp('<=', cost, budget)
    if value is None:
        status = "indeterminate"
    elif value == True:
        status = "satisfied"
    else:
        status = "violated"
    return {"value": value, "status": status, "margin": ((budget - cost) if (_fin(cost) and _fin(budget)) else None)}


class DemoPlantAffordableConstraintInput(BaseModel):
    """Exact input schema: one field per resolved formal."""
    cost: float
    budget: float


class DemoPlantAffordableConstraintOutput(MultiOutput):
    evaluation: ConstraintEvaluation


class DemoPlantAffordableConstraintModule(ModuleBase[DemoPlantAffordableConstraintInput, DemoPlantAffordableConstraintOutput]):
    name: str = "toy_plant__demo_plant__affordable"
    version: str = "s4-probe"

    CONSTRAINT_ID = "toy_plant__demo_plant__affordable"

    def run(self, cost: float, budget: float) -> ModuleResult[DemoPlantAffordableConstraintOutput]:
        DemoPlantAffordableConstraintInput(cost=cost, budget=budget)  # validate inside run()
        verdict = _predicate(cost=cost, budget=budget)
        return ModuleResult(
            data=DemoPlantAffordableConstraintOutput(
                evaluation=ConstraintEvaluation(
                    constraint_id=self.CONSTRAINT_ID,
                    actual_value=verdict["value"],
                    status=verdict["status"],
                    margin=verdict["margin"],
                    observed={"cost": float(cost), "budget": float(budget)},
                )
            )
        )
