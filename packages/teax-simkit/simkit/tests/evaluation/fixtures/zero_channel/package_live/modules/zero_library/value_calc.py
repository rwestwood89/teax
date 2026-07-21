"""Value_CalcModule Module Wrapper

TEAx module for Value_Calc calculation.

Constant output, no `in` parameters -> not an entry channel.

Outputs:
    - value: value result

SysML Source: root-0/zero_library.sysml:4

SysML Source: root-0/zero_library.sysml:4

GAP: Code generator does NOT implement calc logic - only wrapper structure.
Handwritten implementation required in handwritten/zero_library/value_calc_impl.py
"""

from pydantic import BaseModel, Field, RootModel
from simkit.core.base import ModuleBase, ModuleResult

from zero_channel.primitives import Float


class Value_CalcInput(BaseModel):
    """Input model for Value_CalcModule.

    Attributes:
    """


class Value_CalcModule(ModuleBase[Value_CalcInput, Float]):
    """TEAx module for Value_Calc calculation.

Constant output, no `in` parameters -> not an entry channel.

Outputs:
    - value: value result

SysML Source: root-0/zero_library.sysml:4

    SysML Source: root-0/zero_library.sysml:4

    Calculation Specification:
        value = 2.0 * 3.0
        
Documentation:
Constant output, no `in` parameters -> not an entry channel.

    IMPLEMENTATION: See zero_channel.handwritten.zero_library.value_calc_impl
    for manual implementation.

    NOTE: Single-output module - returns Float directly (no MultiOutput needed).
    """

    name: str = "Value_CalcModule"
    version: str = "v0.1"

    def validate_and_fill_default(
        self,     ) -> Value_CalcInput:
        """Validate inputs and fill defaults.

        Args:

        Returns:
            Validated input model
        """
        return Value_CalcInput()

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
        from zero_channel.handwritten.zero_library.value_calc_impl import (
            run_value_calc,
        )

        # Execute implementation - returns single value
        value = run_value_calc(validated_inputs)

        # Single output - return Float directly (RootModel[float])
        # TEAx assigns entire return value to the one channel declared in YAML
        return ModuleResult(data=Float(value))
