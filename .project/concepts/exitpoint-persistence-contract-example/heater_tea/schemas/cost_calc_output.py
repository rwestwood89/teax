"""Multi-output container. UNCHANGED from today's codegen output.

The executor decomposes each field onto its own channel:
  - lcoe_usd_mwh -> channel carries a bare float   (JSON-native shape)
  - unit_count   -> channel carries a bare int     (JSON-native shape)
  - cost_class   -> channel carries a bare str     (JSON-native shape)
  - viable       -> channel carries a bare bool    (JSON-native shape)
  - breakdown    -> channel carries a CostBreakdown (domain-named schema)

Fields stay natural Python types — never RootModel — per
docs/rootmodel-and-primitives.md. The new contract is what finally lets
the four bare-scalar channels reach the ExitPoint (previously T-1/T-2).
"""
from pydantic import Field
from simkit.config.schema import MultiOutput

from heater_tea.schemas.cost_breakdown import CostBreakdown


class CostCalcOutput(MultiOutput):
    """Multi-output container for CostCalc."""

    lcoe_usd_mwh: float = Field(description="lcoe_usd_mwh output")
    unit_count: int = Field(description="unit_count output")
    cost_class: str = Field(description="cost_class output")
    viable: bool = Field(description="viable output")
    breakdown: CostBreakdown = Field(description="breakdown output")
