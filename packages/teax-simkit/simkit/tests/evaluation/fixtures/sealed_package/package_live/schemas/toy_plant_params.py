from pydantic import BaseModel, Field


class ToyPlantParams(BaseModel):
    """Parameters from toy_plant.

    Generated from SysML calculation definitions.
    """
    toy_plant__demo_plant__plant_budget: float = Field(default=5000.0, description="Entry point: plant_budget")
    toy_plant__demo_plant__plant_length: float = Field(default=4.0, description="Entry point: plant_length")
    toy_plant__demo_plant__plant_unit_cost: float = Field(default=250.0, description="Entry point: plant_unit_cost")
    toy_plant__demo_plant__plant_width: float = Field(default=3.0, description="Entry point: plant_width")

    model_config = {"frozen": True, "extra": "forbid"}
