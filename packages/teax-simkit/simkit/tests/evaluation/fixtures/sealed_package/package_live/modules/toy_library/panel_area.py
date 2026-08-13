"""Panel_AreaModule Module Wrapper

TEAx module for Panel_Area calculation.

Toy geometry calc: rectangular panel area = length * width.
First stage of a two-calc chain used to validate usage-level
calc chaining for the WI-010 plant idiom.

*Source**: work/backlog/epic-pipeline-derisk-demo.md (Item 2)
*Ref**: WI-009 design.md "Structure ↔ behavior binding"
*Basis**: Synthetic validation fixture — no domain content

Inputs:
    - length: length parameter
    - width: width parameter

Outputs:
    - area: area result

SysML Source: models/toy_library.sysml:4

SysML Source: models/toy_library.sysml:4

GAP: Code generator does NOT implement calc logic - only wrapper structure.
Handwritten implementation required in handwritten/toy_library/panel_area_impl.py
"""

from pydantic import BaseModel, Field, RootModel
from simkit.core.base import ModuleBase, ModuleResult

from wi014_s4.primitives import Float


class Panel_AreaInput(BaseModel):
    """Input model for Panel_AreaModule.

    Attributes:
        length: length input
        width: width input
    """
    length: float = Field(..., description="length input")
    width: float = Field(..., description="width input")


class Panel_AreaModule(ModuleBase[Panel_AreaInput, Float]):
    """TEAx module for Panel_Area calculation.

Toy geometry calc: rectangular panel area = length * width.
First stage of a two-calc chain used to validate usage-level
calc chaining for the WI-010 plant idiom.

*Source**: work/backlog/epic-pipeline-derisk-demo.md (Item 2)
*Ref**: WI-009 design.md "Structure ↔ behavior binding"
*Basis**: Synthetic validation fixture — no domain content

Inputs:
    - length: length parameter
    - width: width parameter

Outputs:
    - area: area result

SysML Source: models/toy_library.sysml:4

    SysML Source: models/toy_library.sysml:4

    Calculation Specification:
        area = length * width
        
Documentation:
Toy geometry calc: rectangular panel area = length * width.
First stage of a two-calc chain used to validate usage-level
calc chaining for the WI-010 plant idiom.

*Source**: work/backlog/epic-pipeline-derisk-demo.md (Item 2)
*Ref**: WI-009 design.md "Structure ↔ behavior binding"
*Basis**: Synthetic validation fixture — no domain content

    IMPLEMENTATION: See wi014_s4.handwritten.toy_library.panel_area_impl
    for manual implementation.

    NOTE: Single-output module - returns Float directly (no MultiOutput needed).
    """

    name: str = "Panel_AreaModule"
    version: str = "v0.1"

    def validate_and_fill_default(
        self, length: float, width: float    ) -> Panel_AreaInput:
        """Validate inputs and fill defaults.

        Args:
            length: length input
            width: width input

        Returns:
            Validated input model
        """
        return Panel_AreaInput(length=length, width=width)

    def run(
        self, length: float, width: float    ) -> ModuleResult[Float]:
        """Execute calculation.

        Args:
            length: length input
            width: width input

        Returns:
            Module result with Float (single-output mode)
        """
        # Validate inputs
        validated_inputs = self.validate_and_fill_default(length, width)

        # Import handwritten implementation
        from wi014_s4.handwritten.toy_library.panel_area_impl import (
            run_panel_area,
        )

        # Execute implementation - returns single value
        area = run_panel_area(validated_inputs)

        # Single output - return Float directly (RootModel[float])
        # TEAx assigns entire return value to the one channel declared in YAML
        return ModuleResult(data=Float(area))
