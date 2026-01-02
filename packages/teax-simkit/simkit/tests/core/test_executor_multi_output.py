"""Unit tests for executor handling of MultiOutput modules."""
import pytest
from pydantic import BaseModel, Field

from simkit.config.schema import MultiOutput
from simkit.core.base import ModuleBase, ModuleResult
from simkit.core.pipeline_executor import PipelineExecutionContext, SerialPipelineExecutor
from simkit.core.pipeline_registry import ModuleDescriptor, PipelineModuleRegistry
from simkit.config.pipeline_schema import PipelineModuleSpec, PipelineChannelBinding, ChannelSource


# Test schemas
class PowerValue(BaseModel):
    """Test schema for power values."""
    value: float = Field(description="Power value [MW]")


class FusionParams(BaseModel):
    """Test schema for fusion parameters."""
    p_fusion: float = Field(gt=0, description="Fusion power [MW]")


# Multi-output container
class AlphaNeutronSplitOutput(MultiOutput):
    """Multi-output with two power channels."""
    p_alpha: PowerValue
    p_neutron: PowerValue


class AlphaNeutronSplitInput(BaseModel):
    """Input for fusion split module."""
    fusion_params: FusionParams


# Test module using MultiOutput
class AlphaNeutronSplitModule(ModuleBase[AlphaNeutronSplitInput, AlphaNeutronSplitOutput]):
    """Test module that returns MultiOutput."""
    name = "alphaneutronsplit"
    version = "v1.0"

    def validate_and_fill_default(self, fusion_params: FusionParams):
        return AlphaNeutronSplitInput(fusion_params=fusion_params)

    def run(self, fusion_params: FusionParams) -> ModuleResult[AlphaNeutronSplitOutput]:
        inputs = self.validate_and_fill_default(fusion_params=fusion_params)
        p_fusion = inputs.fusion_params.p_fusion

        # D-T fusion: 3.52 MeV alpha, 14.06 MeV neutron (total 17.58 MeV)
        p_alpha = p_fusion * 3.52 / 17.58
        p_neutron = p_fusion * 14.06 / 17.58

        return ModuleResult(
            data=AlphaNeutronSplitOutput(
                p_alpha=PowerValue(value=p_alpha),
                p_neutron=PowerValue(value=p_neutron),
            )
        )


def test_executor_handles_multi_output_module():
    """Test that executor extracts MultiOutput fields to separate channels."""
    # Setup registry
    registry = PipelineModuleRegistry()
    registry.register(
        "AlphaNeutronSplit",
        ModuleDescriptor(
            module_type="AlphaNeutronSplit",
            factory=lambda: AlphaNeutronSplitModule(),
            required_inputs={"fusion_params": FusionParams},
            optional_inputs={},
            outputs={"p_alpha": PowerValue, "p_neutron": PowerValue},
            version="v1.0",
        ),
    )

    # Setup context with input data
    context = PipelineExecutionContext(registry)
    fusion_params = FusionParams(p_fusion=2600.0)
    context.set_channel("fusion_params", fusion_params)

    # Setup module spec
    module_spec = PipelineModuleSpec(
        key="alphaneutronsplit",
        module_type="AlphaNeutronSplit",
        inputs={
            "fusion_params": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="FusionParams",
                channel_name="fusion_params",
            )
        },
        outputs={
            "p_alpha": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="PowerValue",
                channel_name="p_alpha",
            ),
            "p_neutron": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="PowerValue",
                channel_name="p_neutron",
            ),
        },
    )

    # Execute module via executor's internal method
    executor = SerialPipelineExecutor(registry=registry)
    executor._execute_module("alphaneutronsplit", module_spec, context)

    # Verify both output channels were created
    assert "p_alpha" in context.channels
    assert "p_neutron" in context.channels

    # Verify channel values are PowerValue instances (not the MultiOutput container)
    p_alpha = context.channels["p_alpha"]
    p_neutron = context.channels["p_neutron"]

    assert isinstance(p_alpha, PowerValue)
    assert isinstance(p_neutron, PowerValue)
    assert not isinstance(p_alpha, MultiOutput)
    assert not isinstance(p_neutron, MultiOutput)

    # Verify physics is correct (D-T fusion split)
    assert p_alpha.value == pytest.approx(520.5, rel=1e-1)  # 2600 * 3.52/17.58
    assert p_neutron.value == pytest.approx(2079.4, rel=1e-1)  # 2600 * 14.06/17.58

    # Verify energy conservation
    assert p_alpha.value + p_neutron.value == pytest.approx(2600.0, rel=1e-6)


def test_executor_multi_output_with_heterogeneous_types():
    """Test MultiOutput with different field types routes correctly."""

    class TypeA(BaseModel):
        a: str

    class TypeB(BaseModel):
        b: int

    class HeterogeneousOutput(MultiOutput):
        field_a: TypeA
        field_b: TypeB

    class HeterogeneousInput(BaseModel):
        value: float

    class HeterogeneousModule(ModuleBase[HeterogeneousInput, HeterogeneousOutput]):
        name = "hetero"
        version = "v1.0"

        def validate_and_fill_default(self, value: float):
            return HeterogeneousInput(value=value)

        def run(self, value: float) -> ModuleResult[HeterogeneousOutput]:
            return ModuleResult(
                data=HeterogeneousOutput(
                    field_a=TypeA(a="test"),
                    field_b=TypeB(b=42),
                )
            )

    # Setup
    registry = PipelineModuleRegistry()
    registry.register(
        "HeterogeneousModule",
        ModuleDescriptor(
            module_type="HeterogeneousModule",
            factory=lambda: HeterogeneousModule(),
            required_inputs={"value": float},
            optional_inputs={},
            outputs={"field_a": TypeA, "field_b": TypeB},
            version="v1.0",
        ),
    )

    context = PipelineExecutionContext(registry)
    context.set_channel("input_value", 3.14)

    module_spec = PipelineModuleSpec(
        key="hetero_module",
        module_type="HeterogeneousModule",
        inputs={
            "value": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="float",
                channel_name="input_value",
            )
        },
        outputs={
            "field_a": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="TypeA",
                channel_name="out_a",
            ),
            "field_b": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="TypeB",
                channel_name="out_b",
            ),
        },
    )

    executor = SerialPipelineExecutor(registry=registry)
    executor._execute_module("hetero_module", module_spec, context)

    # Verify both channels created with correct types
    assert context.channels["out_a"].a == "test"
    assert context.channels["out_b"].b == 42


def test_executor_multi_output_missing_field_error():
    """Test error when YAML declares field not in MultiOutput."""

    class PartialOutput(MultiOutput):
        """Output with only one field."""
        field1: PowerValue

    class PartialModule(ModuleBase[FusionParams, PartialOutput]):
        name = "partial"
        version = "v1.0"

        def validate_and_fill_default(self, fusion_params: FusionParams):
            return fusion_params

        def run(self, fusion_params: FusionParams) -> ModuleResult[PartialOutput]:
            return ModuleResult(data=PartialOutput(field1=PowerValue(value=100.0)))

    # Setup registry
    registry = PipelineModuleRegistry()
    registry.register(
        "PartialModule",
        ModuleDescriptor(
            module_type="PartialModule",
            factory=lambda: PartialModule(),
            required_inputs={"fusion_params": FusionParams},
            optional_inputs={},
            # YAML declares field2 which doesn't exist in PartialOutput!
            outputs={
                "field1": PowerValue,
                "field2": PowerValue,  # ← Missing in MultiOutput!
            },
            version="v1.0",
        ),
    )

    context = PipelineExecutionContext(registry)
    context.set_channel("fusion_params", FusionParams(p_fusion=100.0))

    module_spec = PipelineModuleSpec(
        key="partial_module",
        module_type="PartialModule",
        inputs={
            "fusion_params": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="FusionParams",
                channel_name="fusion_params",
            )
        },
        outputs={
            "field1": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="PowerValue",
                channel_name="out1",
            ),
            "field2": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="PowerValue",
                channel_name="out2",
            ),
        },
    )

    executor = SerialPipelineExecutor(registry=registry)

    # Should raise error about missing field
    with pytest.raises(RuntimeError, match="missing field 'field2'"):
        executor._execute_module("partial_module", module_spec, context)


def test_executor_backward_compatibility_with_dict_pattern():
    """Test that executor still handles legacy Dict[str, BaseModel] pattern."""
    from typing import Dict

    # Legacy multi-output module using dict pattern (like SynchronousSimModule)
    class LegacyOutput(BaseModel):
        value: float

    class LegacyInput(BaseModel):
        input: float

    class LegacyDictModule(ModuleBase[LegacyInput, Dict[str, BaseModel]]):
        name = "legacy_dict"
        version = "v1.0"

        def validate_and_fill_default(self, input: float):
            return LegacyInput(input=input)

        def run(self, input: float) -> ModuleResult[Dict[str, BaseModel]]:
            # Return dict directly (legacy pattern)
            return ModuleResult(
                data={
                    "output1": LegacyOutput(value=input * 2.0),
                    "output2": LegacyOutput(value=input * 3.0),
                }
            )

    # Setup
    registry = PipelineModuleRegistry()
    registry.register(
        "LegacyDictModule",
        ModuleDescriptor(
            module_type="LegacyDictModule",
            factory=lambda: LegacyDictModule(),
            required_inputs={"input": float},
            optional_inputs={},
            outputs={"output1": LegacyOutput, "output2": LegacyOutput},
            version="v1.0",
        ),
    )

    context = PipelineExecutionContext(registry)
    context.set_channel("input_data", 10.0)

    module_spec = PipelineModuleSpec(
        key="legacy_module",
        module_type="LegacyDictModule",
        inputs={
            "input": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="float",
                channel_name="input_data",
            )
        },
        outputs={
            "output1": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="LegacyOutput",
                channel_name="out1",
            ),
            "output2": PipelineChannelBinding(
                source=ChannelSource.MODULE,
                type_name="LegacyOutput",
                channel_name="out2",
            ),
        },
    )

    executor = SerialPipelineExecutor(registry=registry)
    executor._execute_module("legacy_module", module_spec, context)

    # Verify legacy dict pattern still works
    assert "out1" in context.channels
    assert "out2" in context.channels
    assert context.channels["out1"].value == 20.0
    assert context.channels["out2"].value == 30.0
