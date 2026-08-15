from pydantic import BaseModel, Field


class ConstraintFreePlantParams(BaseModel):
    """Parameters from constraint_free_plant.

    Generated from SysML calculation definitions.
    """
    constraint_free_plant__freePlant__width_design: float = Field(default=4.0, description="Entry point: width_design")

    model_config = {"frozen": True, "extra": "forbid"}
