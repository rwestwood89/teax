"""Constraint module for zero_plant__zeroPlant__within__6c6ab9e3b1afb20e (Item 7 / D2/D3/D9).

Effective predicate: zero_plant::'Zero Plant'::within in owner instance zero_plant__zeroPlant.
Three-valued (Kleene) semantics. A verdict against the assertion does not itself raise (INV-3).
"""

from pydantic import BaseModel
from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult

from zero_channel.schemas.constraint_types import ConstraintEvaluation
from zero_channel.modules.constraints.predicates import _finalize_assertion, constraint_pred_definition_zero_library__within_limit


class ZeroplantWithinConstraintInput(BaseModel):
    """Exact input schema: one field per resolved formal."""
    ceiling: float
    measured: float


class ZeroplantWithinConstraintOutput(MultiOutput):
    evaluation: ConstraintEvaluation


class ZeroplantWithinConstraintModule(ModuleBase[ZeroplantWithinConstraintInput, ZeroplantWithinConstraintOutput]):
    name: str = "zero_plant__zeroplant__within__6c6ab9e3b1afb20e"
    version: str = "v0.1"

    CONSTRAINT_ID = "zero_plant__zeroPlant__within__6c6ab9e3b1afb20e"

    def run(self, ceiling: float, measured: float) -> ModuleResult[ZeroplantWithinConstraintOutput]:
        ZeroplantWithinConstraintInput(ceiling=ceiling, measured=measured)  # validate every resolved formal
        body = constraint_pred_definition_zero_library__within_limit(measured=measured, ceiling=ceiling)
        verdict = _finalize_assertion(
            body,
            is_negated=False,
            expected_value=True,
        )
        return ModuleResult(
            data=ZeroplantWithinConstraintOutput(
                evaluation=ConstraintEvaluation(
                    constraint_id=self.CONSTRAINT_ID,
                    actual_value=verdict.actual_value,
                    status=verdict.status,
                    margin=verdict.margin,
                    observed={"measured": float(measured), "ceiling": float(ceiling)},
                )
            )
        )
