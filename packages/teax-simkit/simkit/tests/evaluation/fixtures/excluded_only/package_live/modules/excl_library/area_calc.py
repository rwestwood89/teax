"""Area_CalcModule Module Wrapper

TEAx module for Area_Calc calculation.

Inputs:
    - width: width parameter

Outputs:
    - area: area result

SysML Source: root-0/excl_library.sysml:4

SysML Source: root-0/excl_library.sysml:4

GAP: Code generator does NOT implement calc logic - only wrapper structure.
Handwritten implementation required in handwritten/excl_library/area_calc_impl.py
"""

from pydantic import BaseModel, Field, RootModel
from simkit.core.base import ModuleBase, ModuleResult

from excl_only.primitives import Float


class Area_CalcInput(BaseModel):
    """Input model for Area_CalcModule.

    Attributes:
        width: width input
    """
    width: float = Field(..., description="width input")


class Area_CalcModule(ModuleBase[Area_CalcInput, Float]):
    """TEAx module for Area_Calc calculation.

Inputs:
    - width: width parameter

Outputs:
    - area: area result

SysML Source: root-0/excl_library.sysml:4

    SysML Source: root-0/excl_library.sysml:4

    Calculation Specification:
        area = width * 3.0

    IMPLEMENTATION: See excl_only.handwritten.excl_library.area_calc_impl
    for manual implementation.

    NOTE: Single-output module - returns Float directly (no MultiOutput needed).
    """

    name: str = "Area_CalcModule"
    version: str = "v0.1"

    def validate_and_fill_default(
        self, width: float    ) -> Area_CalcInput:
        """Validate inputs and fill defaults.

        Args:
            width: width input

        Returns:
            Validated input model
        """
        return Area_CalcInput(width=width)

    def run(
        self, width: float    ) -> ModuleResult[Float]:
        """Execute calculation.

        Args:
            width: width input

        Returns:
            Module result with Float (single-output mode)
        """
        # Validate inputs
        validated_inputs = self.validate_and_fill_default(width)

        # Import handwritten implementation
        from excl_only.handwritten.excl_library.area_calc_impl import (
            run_area_calc,
        )

        # Execute implementation - returns single value
        area = run_area_calc(validated_inputs)

        # Single output - return Float directly (RootModel[float])
        # TEAx assigns entire return value to the one channel declared in YAML
        return ModuleResult(data=Float(area))
