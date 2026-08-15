"""Panel_CostModule Module Wrapper

TEAx module for Panel_Cost calculation.

Toy cost calc: cost = area * unit_cost. Second stage of the
chain — its `area` input is bound to `'Panel Area'.area` at
the usage level inside the part def.

*Source**: work/backlog/epic-pipeline-derisk-demo.md (Item 2)
*Ref**: WI-009 design.md "Structure ↔ behavior binding"
*Basis**: Synthetic validation fixture — no domain content

Inputs:
    - unit_cost: unit_cost parameter
    - area: area parameter

Outputs:
    - cost: cost result

SysML Source: models/toy_library.sysml:26

SysML Source: models/toy_library.sysml:26

GAP: Code generator does NOT implement calc logic - only wrapper structure.
Handwritten implementation required in handwritten/toy_library/panel_cost_impl.py
"""

from pydantic import BaseModel, Field, RootModel
from simkit.core.base import ModuleBase, ModuleResult

from wi014_s4.primitives import Float


class Panel_CostInput(BaseModel):
    """Input model for Panel_CostModule.

    Attributes:
        unit_cost: unit_cost input
        area: area input
    """
    unit_cost: float = Field(..., description="unit_cost input")
    area: float = Field(..., description="area input")


class Panel_CostModule(ModuleBase[Panel_CostInput, Float]):
    """TEAx module for Panel_Cost calculation.

Toy cost calc: cost = area * unit_cost. Second stage of the
chain — its `area` input is bound to `'Panel Area'.area` at
the usage level inside the part def.

*Source**: work/backlog/epic-pipeline-derisk-demo.md (Item 2)
*Ref**: WI-009 design.md "Structure ↔ behavior binding"
*Basis**: Synthetic validation fixture — no domain content

Inputs:
    - unit_cost: unit_cost parameter
    - area: area parameter

Outputs:
    - cost: cost result

SysML Source: models/toy_library.sysml:26

    SysML Source: models/toy_library.sysml:26

    Calculation Specification:
        cost = area * unit_cost
        
Documentation:
Toy cost calc: cost = area * unit_cost. Second stage of the
chain — its `area` input is bound to `'Panel Area'.area` at
the usage level inside the part def.

*Source**: work/backlog/epic-pipeline-derisk-demo.md (Item 2)
*Ref**: WI-009 design.md "Structure ↔ behavior binding"
*Basis**: Synthetic validation fixture — no domain content

    IMPLEMENTATION: See wi014_s4.handwritten.toy_library.panel_cost_impl
    for manual implementation.

    NOTE: Single-output module - returns Float directly (no MultiOutput needed).
    """

    name: str = "Panel_CostModule"
    version: str = "v0.1"

    def validate_and_fill_default(
        self, unit_cost: float, area: float    ) -> Panel_CostInput:
        """Validate inputs and fill defaults.

        Args:
            unit_cost: unit_cost input
            area: area input

        Returns:
            Validated input model
        """
        return Panel_CostInput(unit_cost=unit_cost, area=area)

    def run(
        self, unit_cost: float, area: float    ) -> ModuleResult[Float]:
        """Execute calculation.

        Args:
            unit_cost: unit_cost input
            area: area input

        Returns:
            Module result with Float (single-output mode)
        """
        # Validate inputs
        validated_inputs = self.validate_and_fill_default(unit_cost, area)

        # Import handwritten implementation
        from wi014_s4.handwritten.toy_library.panel_cost_impl import (
            run_panel_cost,
        )

        # Execute implementation - returns single value
        cost = run_panel_cost(validated_inputs)

        # Single output - return Float directly (RootModel[float])
        # TEAx assigns entire return value to the one channel declared in YAML
        return ModuleResult(data=Float(cost))
