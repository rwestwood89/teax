"""Unit tests for registry builder."""
import pytest
from pydantic import BaseModel
from simkit.core.base import ModuleBase, ModuleResult
from simkit.core.module_introspector import ModuleIntrospectionError
from simkit.core.registry_builder import create_registry


class Input1(BaseModel):
    value: float


class Output1(BaseModel):
    result: float


class Module1(ModuleBase[Input1, Output1]):
    name = "module1"
    version = "v1.0"

    def validate_and_fill_default(self, inputs):
        return Input1(**inputs)

    def run(self, inputs):
        return ModuleResult(data=Output1(result=0.0))


class Module2(ModuleBase[Input1, Output1]):
    name = "module2"
    version = "v1.0"

    def validate_and_fill_default(self, inputs):
        return Input1(**inputs)

    def run(self, inputs):
        return ModuleResult(data=Output1(result=0.0))


def test_create_registry_single_module():
    """Test creating registry with single module."""
    registry = create_registry([Module1])

    assert registry.has("Module1")
    descriptor = registry.get("Module1")
    assert descriptor.version == "v1.0"
    assert descriptor.module_type == "Module1"


def test_create_registry_multiple_modules():
    """Test creating registry with multiple modules."""
    registry = create_registry([Module1, Module2])

    assert registry.has("Module1")
    assert registry.has("Module2")


def test_create_registry_with_builtins():
    """Test creating registry that includes built-in modules."""
    registry = create_registry([Module1], include_builtins=True)

    # Custom module
    assert registry.has("Module1")

    # Built-in modules
    assert registry.has("RateData")
    assert registry.has("ConfigureBattery")


def test_create_registry_module_type_override():
    """Test overriding module_type name."""
    registry = create_registry([Module1], module_type_override={Module1: "CustomName"})

    assert registry.has("CustomName")
    assert not registry.has("Module1")


def test_create_registry_duplicate_names():
    """Test error when duplicate module_type names detected."""

    # Create two modules with same class name (would conflict)
    class DuplicateModule(ModuleBase[Input1, Output1]):
        name = "dup"
        version = "v1.0"

        def validate_and_fill_default(self, inputs):
            return Input1(**inputs)

        def run(self, inputs):
            return ModuleResult(data=Output1(result=0.0))

    with pytest.raises(ValueError, match="Duplicate module_type"):
        create_registry([DuplicateModule, DuplicateModule])


def test_create_registry_duplicate_with_builtins():
    """Test error when custom module conflicts with builtin name."""

    # Create a module that would conflict with builtin 'RateData'
    class RateData(ModuleBase[Input1, Output1]):
        name = "rate_data_custom"
        version = "v2.0"

        def validate_and_fill_default(self, inputs):
            return Input1(**inputs)

        def run(self, inputs):
            return ModuleResult(data=Output1(result=0.0))

    # Should raise error because 'RateData' already exists in builtins
    with pytest.raises(ValueError, match="Duplicate module_type"):
        create_registry([RateData], include_builtins=True)


def test_create_registry_invalid_module():
    """Test error when module fails introspection."""

    class InvalidModule(ModuleBase):  # type: ignore - Missing type params
        name = "invalid"
        version = "v1.0"

    with pytest.raises(ModuleIntrospectionError, match="Failed to register"):
        create_registry([InvalidModule])


def test_registry_factory_creates_instances():
    """Test that factory functions create module instances."""
    registry = create_registry([Module1])
    descriptor = registry.get("Module1")

    instance1 = descriptor.factory()
    instance2 = descriptor.factory()

    assert isinstance(instance1, Module1)
    assert isinstance(instance2, Module1)
    assert instance1 is not instance2  # New instance each time


def test_registry_factory_closure_correctness():
    """Test that factory closure captures correct module class."""
    registry = create_registry([Module1, Module2])

    descriptor1 = registry.get("Module1")
    descriptor2 = registry.get("Module2")

    instance1 = descriptor1.factory()
    instance2 = descriptor2.factory()

    # Each factory should create the correct type
    assert isinstance(instance1, Module1)
    assert isinstance(instance2, Module2)
    assert not isinstance(instance1, Module2)
    assert not isinstance(instance2, Module1)


def test_create_registry_empty_list():
    """Test creating registry with empty module list."""
    registry = create_registry([])

    # Should work but have no custom modules
    assert not registry.has("Module1")


def test_create_registry_preserves_metadata():
    """Test that registry preserves all module metadata."""

    class DetailedInput(BaseModel):
        required_field: float
        optional_field: float = 10.0

    class DetailedOutput(BaseModel):
        output1: float
        output2: str

    class DetailedModule(ModuleBase[DetailedInput, DetailedOutput]):
        name = "detailed"
        version = "v2.5"

        def validate_and_fill_default(self, inputs):
            return DetailedInput(**inputs)

        def run(self, inputs):
            return ModuleResult(data=DetailedOutput(output1=0.0, output2="test"))

    registry = create_registry([DetailedModule])
    descriptor = registry.get("DetailedModule")

    # Check metadata preserved
    assert descriptor.version == "v2.5"
    assert "required_field" in descriptor.required_inputs
    assert "optional_field" in descriptor.optional_inputs
    assert "output1" in descriptor.outputs
    assert "output2" in descriptor.outputs
