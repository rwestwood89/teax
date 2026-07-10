"""EfficiencyCalcModule — single-output module. UNCHANGED from today.

Single-output modules return the whole Float (= RootModel[float]); the
executor stores that whole object on the channel, so the channel's
declared type is RootModel[float]. Downstream consumers extract `.root`.

Under the new contract this channel can ALSO go straight to the
ExitPoint with no registration — "RootModel[float]" is one of the eight
default handler names.
"""
from simkit.core.base import ModuleBase, ModuleResult
from pydantic import BaseModel, Field

from heater_tea.primitives import Float


class EfficiencyCalcInput(BaseModel):
    """Input model for EfficiencyCalcModule."""

    input_power_kw: float = Field(..., description="input_power_kw input")
    loss_fraction: float = Field(..., description="loss_fraction input")


class EfficiencyCalcModule(ModuleBase[EfficiencyCalcInput, Float]):
    """Thermal conversion efficiency: efficiency = 1.0 - loss_fraction.

    SysML Source: models/analyses/heater.sysml:4
    NOTE: Single-output module - returns Float directly (no MultiOutput needed).
    """

    name: str = "EfficiencyCalcModule"
    version: str = "v0.1"

    def validate_and_fill_default(
        self, input_power_kw: float, loss_fraction: float
    ) -> EfficiencyCalcInput:
        return EfficiencyCalcInput(
            input_power_kw=input_power_kw, loss_fraction=loss_fraction
        )

    def run(self, input_power_kw: float, loss_fraction: float) -> ModuleResult[Float]:
        inputs = self.validate_and_fill_default(input_power_kw, loss_fraction)
        efficiency = 1.0 - inputs.loss_fraction
        return ModuleResult(data=Float(efficiency))
