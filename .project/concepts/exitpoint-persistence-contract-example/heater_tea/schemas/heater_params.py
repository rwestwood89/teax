"""Entry-point parameter group. UNCHANGED from today's codegen output.

Domain-named schema: registered via CUSTOM_SCHEMA_TYPES so the EntryPoint
can load it from JSON and the ExitPoint could persist it if exported.
"""
from pydantic import BaseModel, Field


class HeaterParams(BaseModel):
    """Parameters from heater.sysml. Generated from SysML calculation definitions."""

    heater__element__input_power_kw: float = Field(default=2.0, description="Entry point: input_power_kw")
    heater__element__loss_fraction: float = Field(default=0.13, description="Entry point: loss_fraction")
    heater__site__unit_budget_usd: float = Field(default=900.0, description="Entry point: unit_budget_usd")

    model_config = {"frozen": True, "extra": "forbid"}
