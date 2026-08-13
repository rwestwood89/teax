from pydantic import BaseModel, Field


class ExclPlantParams(BaseModel):
    """Parameters from excl_plant.

    Generated from SysML calculation definitions.
    """
    excl_plant__exclPlant__width_design: float = Field(default=4.0, description="Entry point: width_design")

    model_config = {"frozen": True, "extra": "forbid"}
