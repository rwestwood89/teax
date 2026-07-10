"""CostCalcModule — multi-output module. UNCHANGED from today.

Returns a CostCalcOutput container; the executor decomposes its fields
onto separate channels, four of which carry bare JSON-native scalars.
The module author writes natural Python — no wrapping, no ceremony.
That readability is exactly what the contract change preserves: the fix
lives in TEAx's default router, not here.
"""
from simkit.core.base import ModuleBase, ModuleResult
from pydantic import BaseModel, Field

from heater_tea.schemas.cost_breakdown import CostBreakdown
from heater_tea.schemas.cost_calc_output import CostCalcOutput


class CostCalcInput(BaseModel):
    """Input model for CostCalcModule."""

    efficiency: float = Field(..., description="efficiency input")
    unit_budget_usd: float = Field(..., description="unit_budget_usd input")


class CostCalcModule(ModuleBase[CostCalcInput, CostCalcOutput]):
    """Levelized cost and sizing for the heater installation.

    SysML Source: models/analyses/heater.sysml:12
    """

    name: str = "CostCalcModule"
    version: str = "v0.1"

    def validate_and_fill_default(
        self, efficiency: float, unit_budget_usd: float
    ) -> CostCalcInput:
        return CostCalcInput(efficiency=efficiency, unit_budget_usd=unit_budget_usd)

    def run(self, efficiency: float, unit_budget_usd: float) -> ModuleResult[CostCalcOutput]:
        inputs = self.validate_and_fill_default(efficiency, unit_budget_usd)
        hardware = 260.0 / inputs.efficiency
        install = 120.0
        lcoe = (hardware + install) / 2.66
        units = int(inputs.unit_budget_usd // (hardware + install))
        return ModuleResult(
            data=CostCalcOutput(
                lcoe_usd_mwh=round(lcoe, 1),          # -> bare float channel
                unit_count=units,                     # -> bare int channel
                cost_class="moderate" if lcoe < 160 else "high",  # -> bare str channel
                viable=units >= 1,                    # -> bare bool channel
                breakdown=CostBreakdown(              # -> CostBreakdown channel
                    hardware_usd=round(hardware, 2), install_usd=install
                ),
            )
        )
