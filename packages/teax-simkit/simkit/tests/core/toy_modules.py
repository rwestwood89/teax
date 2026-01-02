"""Toy modules for generic framework testing.

These modules provide battery-free test coverage for the pipeline framework.
They can be used to verify registry, executor, validator, and pipeline
functionality without importing any domain-specific (battery) code.

Design Pattern:
- For simple single-value outputs, use RootModel[float] as the OutputModel.
  This allows field extraction via .root for downstream modules.
- For complex outputs, use custom BaseModel subclasses.
- For multi-output modules, use MultiOutput container class.
"""
from pydantic import BaseModel, RootModel

from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult


class ToyInput(BaseModel):
    """Simple input schema for toy modules."""

    value: float


class ToyOutput(BaseModel):
    """Simple output schema for toy modules."""

    value: float


class ToyDoublerModule(ModuleBase[ToyInput, RootModel[float]]):
    """Doubles input value. For framework testing.

    Uses RootModel[float] output to demonstrate single-primitive-output pattern.
    """

    name = "ToyDoubler"
    version = "v1.0"

    def validate_and_fill_default(self, value: float) -> ToyInput:
        return ToyInput(value=value)

    def run(self, value: float) -> ModuleResult[RootModel[float]]:
        validated = self.validate_and_fill_default(value)
        return ModuleResult(data=RootModel[float](validated.value * 2.0))


class ToyAdderModule(ModuleBase[RootModel[float], RootModel[float]]):
    """Adds 22 to input value. For framework testing.

    Uses RootModel[float] for both input and output to demonstrate chaining.
    """

    name = "ToyAdder"
    version = "v1.0"

    def validate_and_fill_default(self, root: float) -> RootModel[float]:
        return RootModel[float](root)

    def run(self, root: float) -> ModuleResult[RootModel[float]]:
        validated = self.validate_and_fill_default(root)
        return ModuleResult(data=RootModel[float](validated.root + 22.0))


class ToyMultiOutput(MultiOutput):
    """Container for multiple outputs from ToyMultiOutputModule."""

    doubled: ToyOutput
    tripled: ToyOutput


class ToyMultiOutputModule(ModuleBase[ToyInput, ToyMultiOutput]):
    """Produces multiple outputs: doubled and tripled. For multi-output testing."""

    name = "ToyMultiOutput"
    version = "v1.0"

    def validate_and_fill_default(self, value: float) -> ToyInput:
        return ToyInput(value=value)

    def run(self, value: float) -> ModuleResult[ToyMultiOutput]:
        validated = self.validate_and_fill_default(value)
        return ModuleResult(
            data=ToyMultiOutput(
                doubled=ToyOutput(value=validated.value * 2.0),
                tripled=ToyOutput(value=validated.value * 3.0),
            )
        )
