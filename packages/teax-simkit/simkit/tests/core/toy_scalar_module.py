"""Toy module covering primitive multi-output channels."""

from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult
from simkit.tests.core.toy_modules import ToyInput


class ToyScalarOutputs(MultiOutput):
    """Container covering each scalar type supported by the default router."""

    floating: float
    integer: int
    text: str
    flag: bool


class ToyScalarOutputModule(ModuleBase[ToyInput, ToyScalarOutputs]):
    """Produces all four supported bare scalar channel types."""

    name = "ToyScalarOutput"
    version = "v1.0"

    def validate_and_fill_default(self, value: float) -> ToyInput:
        return ToyInput(value=value)

    def run(self, value: float) -> ModuleResult[ToyScalarOutputs]:
        validated = self.validate_and_fill_default(value)
        integer_value = int(validated.value)
        return ModuleResult(
            data=ToyScalarOutputs(
                floating=validated.value / 4.0,
                integer=integer_value,
                text=f"value:{integer_value}",
                flag=validated.value > 0.0,
            )
        )
