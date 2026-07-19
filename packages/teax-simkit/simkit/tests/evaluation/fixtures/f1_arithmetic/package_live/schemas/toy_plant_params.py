from pydantic import BaseModel, Field


class ToyPlantParams(BaseModel):
    """Parameters from toy_plant.sysml.

    Generated from SysML calculation definitions.
    """
    toy_plant__Toy_Plant__division_a: float = Field(default=2.0, description="Entry point: division_a")
    toy_plant__Toy_Plant__division_b: float = Field(default=1.0, description="Entry point: division_b")
    toy_plant__Toy_Plant__nested_a: float = Field(default=2.0, description="Entry point: nested_a")
    toy_plant__Toy_Plant__nested_b: float = Field(default=1.0, description="Entry point: nested_b")
    toy_plant__Toy_Plant__power_a: float = Field(default=2.0, description="Entry point: power_a")
    toy_plant__Toy_Plant__power_b: float = Field(default=2.0, description="Entry point: power_b")

    model_config = {"frozen": True, "extra": "forbid"}
