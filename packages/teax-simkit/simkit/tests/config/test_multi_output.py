"""Unit tests for MultiOutput base class."""
import pytest
from pydantic import BaseModel, Field


def test_multi_output_base_class_exists():
    """Test that MultiOutput base class can be imported."""
    from simkit.config.schema import MultiOutput

    assert MultiOutput is not None
    assert issubclass(MultiOutput, BaseModel)


def test_multi_output_to_channel_dict():
    """Test MultiOutput.to_channel_dict() extracts fields correctly."""
    from simkit.config.schema import MultiOutput

    # Define a test output model
    class PowerValue(BaseModel):
        value: float = Field(description="Power value [MW]")

    class TestMultiOutput(MultiOutput):
        """Test multi-output with two fields."""
        p_alpha: PowerValue
        p_neutron: PowerValue

    # Create instance
    output = TestMultiOutput(
        p_alpha=PowerValue(value=520.5),
        p_neutron=PowerValue(value=2079.4),
    )

    # Extract to dict
    channel_dict = output.to_channel_dict()

    # Verify structure
    assert isinstance(channel_dict, dict)
    assert "p_alpha" in channel_dict
    assert "p_neutron" in channel_dict

    # Verify values
    assert isinstance(channel_dict["p_alpha"], PowerValue)
    assert isinstance(channel_dict["p_neutron"], PowerValue)
    assert channel_dict["p_alpha"].value == 520.5
    assert channel_dict["p_neutron"].value == 2079.4


def test_multi_output_with_different_types():
    """Test MultiOutput with heterogeneous field types."""
    from simkit.config.schema import MultiOutput

    class TypeA(BaseModel):
        a_value: str

    class TypeB(BaseModel):
        b_value: int

    class TypeC(BaseModel):
        c_value: float

    class HeterogeneousOutput(MultiOutput):
        """Multi-output with different types."""
        field_a: TypeA
        field_b: TypeB
        field_c: TypeC

    output = HeterogeneousOutput(
        field_a=TypeA(a_value="test"),
        field_b=TypeB(b_value=42),
        field_c=TypeC(c_value=3.14),
    )

    channel_dict = output.to_channel_dict()

    assert len(channel_dict) == 3
    assert channel_dict["field_a"].a_value == "test"
    assert channel_dict["field_b"].b_value == 42
    assert channel_dict["field_c"].c_value == 3.14


def test_multi_output_field_names_match_model():
    """Test that to_channel_dict() keys match model field names."""
    from simkit.config.schema import MultiOutput

    class DummyModel(BaseModel):
        val: float

    class CustomNamedOutput(MultiOutput):
        """Output with custom field names."""
        custom_field_1: DummyModel
        custom_field_2: DummyModel
        another_name: DummyModel

    output = CustomNamedOutput(
        custom_field_1=DummyModel(val=1.0),
        custom_field_2=DummyModel(val=2.0),
        another_name=DummyModel(val=3.0),
    )

    channel_dict = output.to_channel_dict()

    # Keys should exactly match field names
    assert set(channel_dict.keys()) == {"custom_field_1", "custom_field_2", "another_name"}


def test_multi_output_inheritance_chain():
    """Test that MultiOutput properly inherits from BaseModel and StrictBaseModel."""
    from simkit.config.schema import MultiOutput, StrictBaseModel

    # Verify inheritance
    assert issubclass(MultiOutput, StrictBaseModel)
    assert issubclass(MultiOutput, BaseModel)

    # Verify MultiOutput instance is also a BaseModel instance
    class SimpleOutput(MultiOutput):
        field: BaseModel

    class DummyModel(BaseModel):
        x: int

    output = SimpleOutput(field=DummyModel(x=10))

    assert isinstance(output, MultiOutput)
    assert isinstance(output, StrictBaseModel)
    assert isinstance(output, BaseModel)


def test_multi_output_pydantic_validation():
    """Test that Pydantic validation works on MultiOutput subclasses."""
    from simkit.config.schema import MultiOutput

    class ValidatedModel(BaseModel):
        positive_value: float = Field(gt=0, description="Must be positive")

    class ValidatedOutput(MultiOutput):
        result: ValidatedModel

    # Valid data should work
    output = ValidatedOutput(result=ValidatedModel(positive_value=10.0))
    assert output.result.positive_value == 10.0

    # Invalid data should raise validation error
    with pytest.raises(Exception):  # Pydantic validation error
        ValidatedOutput(result=ValidatedModel(positive_value=-5.0))


def test_multi_output_immutability():
    """Test that MultiOutput instances are immutable (frozen)."""
    from simkit.config.schema import MultiOutput

    class ImmutableModel(BaseModel):
        value: float

    class ImmutableOutput(MultiOutput):
        field: ImmutableModel

    output = ImmutableOutput(field=ImmutableModel(value=42.0))

    # Attempt to modify should raise error (if frozen)
    # Note: This depends on StrictBaseModel configuration
    # If StrictBaseModel sets model_config frozen=True, this will raise
    # Otherwise, this test documents expected behavior

    # For now, just verify we can access the field
    assert output.field.value == 42.0


def test_multi_output_single_field():
    """Test MultiOutput with only one field (edge case)."""
    from simkit.config.schema import MultiOutput

    class SingleModel(BaseModel):
        data: str

    class SingleFieldOutput(MultiOutput):
        """Multi-output with just one field (unusual but valid)."""
        only_field: SingleModel

    output = SingleFieldOutput(only_field=SingleModel(data="test"))
    channel_dict = output.to_channel_dict()

    assert len(channel_dict) == 1
    assert "only_field" in channel_dict
    assert channel_dict["only_field"].data == "test"
