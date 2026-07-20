"""Constraint module for toy_plant__demo_plant__affordable__c122240f4b148939 (Item 7 / D2/D3/D9).

Effective predicate: toy_plant::'Toy Plant'::affordable in owner instance toy_plant__demo_plant.
Three-valued (Kleene) semantics. A verdict against the assertion does not itself raise (INV-3).
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from wi014_s4.schemas.constraint_types import ConstraintEvaluation
from wi014_s4.modules.constraints.predicates import _finalize_assertion, constraint_pred_definition_toy_library__cost_within_budget


class DemoPlantAffordableConstraintInput(BaseModel):
    """Exact input schema: one field per resolved formal."""
    budget: float
    cost: float


class DemoPlantAffordableConstraintOutput(MultiOutput):
    evaluation: ConstraintEvaluation


class DemoPlantAffordableConstraintModule(ModuleBase[DemoPlantAffordableConstraintInput, DemoPlantAffordableConstraintOutput]):
    name: str = "toy_plant__demo_plant__affordable__c122240f4b148939"
    version: str = "v0.1"

    CONSTRAINT_ID = "toy_plant__demo_plant__affordable__c122240f4b148939"

    def run(self, budget: float, cost: float) -> ModuleResult[DemoPlantAffordableConstraintOutput]:
        DemoPlantAffordableConstraintInput(budget=budget, cost=cost)  # validate every resolved formal
        body = constraint_pred_definition_toy_library__cost_within_budget(cost=cost, budget=budget)
        verdict = _finalize_assertion(
            body,
            is_negated=False,
            expected_value=True,
        )
        return ModuleResult(
            data=DemoPlantAffordableConstraintOutput(
                evaluation=ConstraintEvaluation(
                    constraint_id=self.CONSTRAINT_ID,
                    actual_value=verdict.actual_value,
                    status=verdict.status,
                    margin=verdict.margin,
                    observed={"cost": float(cost), "budget": float(budget)},
                )
            )
        )
