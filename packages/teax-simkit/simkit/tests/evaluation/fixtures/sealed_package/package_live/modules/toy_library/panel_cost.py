"""Panel_CostModule Module Wrapper

TEAx module for Panel_Cost calculation.

Toy cost calc: cost = area * unit_cost. Second stage of the
chain — its `area` input is bound to `'Panel Area'.area` at
the usage level inside the part def.

*Source**: work/backlog/epic-pipeline-derisk-demo.md (Item 2)
*Ref**: WI-009 design.md "Structure ↔ behavior binding"
*Basis**: Synthetic validation fixture — no domain content

Inputs:
    - area: area parameter
    - unit_cost: unit_cost parameter

Outputs:
    - cost: cost result

SysML Source: root-0/toy_library.sysml:26

SysML Source: root-0/toy_library.sysml:26

GAP: Code generator does NOT implement calc logic - only wrapper structure.
Handwritten implementation required in handwritten/toy_library/panel_cost_impl.py
"""

from pydantic import BaseModel, Field, RootModel
from simkit.core.base import ModuleBase, ModuleResult

from wi014_s4.primitives import Float


class Panel_CostInput(BaseModel):
    """Input model for Panel_CostModule.

    Attributes:
        area: area input
        unit_cost: unit_cost input
    """
    area: float = Field(..., description="area input")
    unit_cost: float = Field(..., description="unit_cost input")


class Panel_CostModule(ModuleBase[Panel_CostInput, Float]):
    """TEAx module for Panel_Cost calculation.

Toy cost calc: cost = area * unit_cost. Second stage of the
chain — its `area` input is bound to `'Panel Area'.area` at
the usage level inside the part def.

*Source**: work/backlog/epic-pipeline-derisk-demo.md (Item 2)
*Ref**: WI-009 design.md "Structure ↔ behavior binding"
*Basis**: Synthetic validation fixture — no domain content

Inputs:
    - area: area parameter
    - unit_cost: unit_cost parameter

Outputs:
    - cost: cost result

SysML Source: root-0/toy_library.sysml:26

    SysML Source: root-0/toy_library.sysml:26

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
        self, area: float, unit_cost: float    ) -> Panel_CostInput:
        """Validate inputs and fill defaults.

        Args:
            area: area input
            unit_cost: unit_cost input

        Returns:
            Validated input model
        """
        return Panel_CostInput(area=area, unit_cost=unit_cost)

    def run(
        self, area: float, unit_cost: float    ) -> ModuleResult[Float]:
        """Execute calculation.

        Args:
            area: area input
            unit_cost: unit_cost input

        Returns:
            Module result with Float (single-output mode)
        """
        # Validate inputs
        validated_inputs = self.validate_and_fill_default(area, unit_cost)

        # Import handwritten implementation
        from wi014_s4.handwritten.toy_library.panel_cost_impl import (
            run_panel_cost,
        )

        # Execute implementation - returns single value
        cost = run_panel_cost(validated_inputs)

        # Single output - return Float directly (RootModel[float])
        # TEAx assigns entire return value to the one channel declared in YAML
        return ModuleResult(data=Float(cost))
