"""Limit_CalcModule Module Wrapper

TEAx module for Limit_Calc calculation.

Constant limit, no `in` parameters -> not an entry channel.

Outputs:
    - limit: limit result

SysML Source: models/zero_library.sysml:9

SysML Source: models/zero_library.sysml:9

GAP: Code generator does NOT implement calc logic - only wrapper structure.
Handwritten implementation required in handwritten/zero_library/limit_calc_impl.py
"""

from pydantic import BaseModel, Field, RootModel
from simkit.core.base import ModuleBase, ModuleResult

from zero_channel.primitives import Float


class Limit_CalcInput(BaseModel):
    """Input model for Limit_CalcModule.

    Attributes:
    """


class Limit_CalcModule(ModuleBase[Limit_CalcInput, Float]):
    """TEAx module for Limit_Calc calculation.

Constant limit, no `in` parameters -> not an entry channel.

Outputs:
    - limit: limit result

SysML Source: models/zero_library.sysml:9

    SysML Source: models/zero_library.sysml:9

    Calculation Specification:
        limit = 10.0
        
Documentation:
Constant limit, no `in` parameters -> not an entry channel.

    IMPLEMENTATION: See zero_channel.handwritten.zero_library.limit_calc_impl
    for manual implementation.

    NOTE: Single-output module - returns Float directly (no MultiOutput needed).
    """

    name: str = "Limit_CalcModule"
    version: str = "v0.1"

    def validate_and_fill_default(
        self,     ) -> Limit_CalcInput:
        """Validate inputs and fill defaults.

        Args:

        Returns:
            Validated input model
        """
        return Limit_CalcInput()

    def run(
        self,     ) -> ModuleResult[Float]:
        """Execute calculation.

        Args:

        Returns:
            Module result with Float (single-output mode)
        """
        # Validate inputs
        validated_inputs = self.validate_and_fill_default()

        # Import handwritten implementation
        from zero_channel.handwritten.zero_library.limit_calc_impl import (
            run_limit_calc,
        )

        # Execute implementation - returns single value
        limit = run_limit_calc(validated_inputs)

        # Single output - return Float directly (RootModel[float])
        # TEAx assigns entire return value to the one channel declared in YAML
        return ModuleResult(data=Float(limit))
