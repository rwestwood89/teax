"""Domain-named output schema. UNCHANGED from today.

This is the shape that legitimately NEEDS registration under the new
contract: its name ("CostBreakdown") is domain-specific, so TEAx cannot
know how to resolve or persist it without CUSTOM_SCHEMA_TYPES.
"""
from pydantic import BaseModel, Field


class CostBreakdown(BaseModel):
    """Per-category cost detail for one heater installation."""

    hardware_usd: float = Field(description="hardware_usd output")
    install_usd: float = Field(description="install_usd output")

    model_config = {"frozen": True, "extra": "forbid"}
