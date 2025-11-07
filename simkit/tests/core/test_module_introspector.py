"""Unit tests for module introspection."""
import pytest
from pydantic import BaseModel
from simkit.core.base import ModuleBase, ModuleResult
from simkit.core.module_introspector import (
    ModuleIntrospectionError,
    extract_field_types,
    extract_io_models,
    introspect_module,
)


class SimpleInput(BaseModel):
    value: float


class SimpleOutput(BaseModel):
    result: float


class ValidModule(ModuleBase[SimpleInput, SimpleOutput]):
    name = "valid_module"
    version = "v1.0"

    def validate_and_fill_default(self, inputs):
        return SimpleInput(**inputs)

    def run(self, inputs):
        return ModuleResult(data=SimpleOutput(result=0.0))


def test_extract_io_models_success():
    """Test extracting InputModel and OutputModel from valid module."""
    input_model, output_model = extract_io_models(ValidModule)
    assert input_model == SimpleInput
    assert output_model == SimpleOutput


def test_extract_io_models_missing_type_params():
    """Test error when module doesn't specify type parameters."""

    class InvalidModule(ModuleBase):  # type: ignore
        pass

    with pytest.raises(ModuleIntrospectionError, match="does not inherit from ModuleBase with type parameters"):
        extract_io_models(InvalidModule)


def test_extract_io_models_non_basemodel_input():
    """Test error when InputModel is not a BaseModel subclass."""

    class InvalidInput:
        pass

    class InvalidModule(ModuleBase[InvalidInput, SimpleOutput]):  # type: ignore
        pass

    with pytest.raises(ModuleIntrospectionError, match="must be a Pydantic BaseModel"):
        extract_io_models(InvalidModule)


def test_extract_io_models_non_basemodel_output():
    """Test error when OutputModel is not a BaseModel subclass."""

    class InvalidOutput:
        pass

    class InvalidModule(ModuleBase[SimpleInput, InvalidOutput]):  # type: ignore
        pass

    with pytest.raises(ModuleIntrospectionError, match="must be a Pydantic BaseModel"):
        extract_io_models(InvalidModule)


def test_extract_field_types_required_and_optional():
    """Test extracting required and optional fields from Pydantic model."""

    class MixedFieldsModel(BaseModel):
        required_field: float
        optional_field: float = 1.0
        optional_with_none: float | None = None

    required, optional = extract_field_types(MixedFieldsModel)

    assert "required_field" in required
    assert "optional_field" in optional
    assert "optional_with_none" in optional


def test_extract_field_types_all_required():
    """Test model with only required fields."""

    class AllRequiredModel(BaseModel):
        field1: float
        field2: str

    required, optional = extract_field_types(AllRequiredModel)

    assert len(required) == 2
    assert len(optional) == 0
    assert "field1" in required
    assert "field2" in required


def test_extract_field_types_all_optional():
    """Test model with only optional fields."""

    class AllOptionalModel(BaseModel):
        field1: float = 1.0
        field2: str = "default"

    required, optional = extract_field_types(AllOptionalModel)

    assert len(required) == 0
    assert len(optional) == 2
    assert "field1" in optional
    assert "field2" in optional


def test_extract_field_types_empty_model():
    """Test model with no fields."""

    class EmptyModel(BaseModel):
        pass

    required, optional = extract_field_types(EmptyModel)

    assert len(required) == 0
    assert len(optional) == 0


def test_introspect_module_success():
    """Test full module introspection on valid module."""
    metadata = introspect_module(ValidModule)

    assert metadata["module_type"] == "ValidModule"
    assert metadata["input_model"] == SimpleInput
    assert metadata["output_model"] == SimpleOutput
    assert metadata["version"] == "v1.0"
    assert metadata["name"] == "valid_module"
    assert "value" in metadata["required_inputs"]
    assert "result" in metadata["outputs"]


def test_introspect_module_uses_defaults():
    """Test that introspection works with default name/version from base class."""

    class ModuleWithDefaults(ModuleBase[SimpleInput, SimpleOutput]):
        # Inherit default name and version from ModuleBase
        pass

    # Should not raise error - defaults are acceptable
    metadata = introspect_module(ModuleWithDefaults)

    # Should use default values from base class
    assert metadata["name"] == "module"  # Default from ModuleBase
    assert metadata["version"] == "v0.1"  # Default from ModuleBase


def test_introspect_module_with_optional_inputs():
    """Test introspection on module with optional input fields."""

    class InputWithOptional(BaseModel):
        required_value: float
        optional_value: float = 10.0

    class OutputSimple(BaseModel):
        result: float

    class ModuleWithOptional(ModuleBase[InputWithOptional, OutputSimple]):
        name = "module_with_optional"
        version = "v1.0"

        def validate_and_fill_default(self, inputs):
            return InputWithOptional(**inputs)

        def run(self, inputs):
            return ModuleResult(data=OutputSimple(result=0.0))

    metadata = introspect_module(ModuleWithOptional)

    assert "required_value" in metadata["required_inputs"]
    assert "optional_value" in metadata["optional_inputs"]
    assert len(metadata["required_inputs"]) == 1
    assert len(metadata["optional_inputs"]) == 1
