"""Unit tests for field reference support in pipeline executor."""
import pytest
from simkit.config.schema import StrictBaseModel
from simkit.config.pipeline_schema import PipelineChannelBinding, ChannelSource
from simkit.core.pipeline_executor import (
    _resolve_input,
    PipelineExecutionContext,
    PipelineExecutionError,
)
from simkit.core.pipeline_registry import PipelineModuleRegistry


class BlanketConfig(StrictBaseModel):
    """Test schema for blanket configuration."""
    material: str
    thickness_m: float


class FusionParams(StrictBaseModel):
    """Test schema for fusion parameters with nested configs."""
    p_fusion: float
    blanket_config: BlanketConfig
    optional_blanket: BlanketConfig | None = None


@pytest.fixture
def sample_registry():
    """Create a sample registry for testing."""
    return PipelineModuleRegistry.from_static_modules()


def test_resolve_input_field_reference(sample_registry):
    """_resolve_input extracts field for field reference binding."""
    context = PipelineExecutionContext(sample_registry)
    fusion_params = FusionParams(
        p_fusion=100.0,
        blanket_config=BlanketConfig(material="steel", thickness_m=0.5)
    )
    context.set_channel("fusion_params", fusion_params)

    binding = PipelineChannelBinding(
        type_name="BlanketConfig",
        channel_name="fusion_params",
        field_path="blanket_config",
        source=ChannelSource.MODULE
    )

    result = _resolve_input(binding, context)
    assert isinstance(result, BlanketConfig)
    assert result.material == "steel"
    assert result.thickness_m == 0.5


def test_resolve_input_standard_binding(sample_registry):
    """_resolve_input returns full channel value for standard binding."""
    context = PipelineExecutionContext(sample_registry)
    fusion_params = FusionParams(
        p_fusion=100.0,
        blanket_config=BlanketConfig(material="steel", thickness_m=0.5)
    )
    context.set_channel("fusion_params", fusion_params)

    binding = PipelineChannelBinding(
        type_name="FusionParams",
        channel_name="fusion_params",
        source=ChannelSource.MODULE
    )

    result = _resolve_input(binding, context)
    assert isinstance(result, FusionParams)
    assert result.p_fusion == 100.0


def test_resolve_input_default_binding(sample_registry):
    """_resolve_input returns None for default binding (unchanged behavior)."""
    context = PipelineExecutionContext(sample_registry)

    binding = PipelineChannelBinding(
        type_name=None,
        channel_name="default_channel",
        source=ChannelSource.DEFAULT
    )

    result = _resolve_input(binding, context)
    assert result is None


def test_resolve_input_optional_field_none_raises(sample_registry):
    """Runtime error when Optional field is None."""
    context = PipelineExecutionContext(sample_registry)
    fusion_params = FusionParams(
        p_fusion=100.0,
        blanket_config=BlanketConfig(material="steel", thickness_m=0.5),
        optional_blanket=None  # Optional field is None
    )
    context.set_channel("fusion_params", fusion_params)

    binding = PipelineChannelBinding(
        type_name="BlanketConfig",
        channel_name="fusion_params",
        field_path="optional_blanket",
        source=ChannelSource.MODULE
    )

    with pytest.raises(PipelineExecutionError, match="is None"):
        _resolve_input(binding, context)


def test_resolve_input_missing_field_raises(sample_registry):
    """Runtime error when field doesn't exist (defensive check)."""
    context = PipelineExecutionContext(sample_registry)
    fusion_params = FusionParams(
        p_fusion=100.0,
        blanket_config=BlanketConfig(material="steel", thickness_m=0.5)
    )
    context.set_channel("fusion_params", fusion_params)

    binding = PipelineChannelBinding(
        type_name="SomeType",
        channel_name="fusion_params",
        field_path="nonexistent_field",
        source=ChannelSource.MODULE
    )

    with pytest.raises(PipelineExecutionError, match="has no field 'nonexistent_field'"):
        _resolve_input(binding, context)
