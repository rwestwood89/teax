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


def test_create_registry_accepts_external_basemodel_schemas():
    """Test that ModuleDescriptor accepts any BaseModel subclass, not just StrictBaseModel.

    This verifies Issue 1 fix: External users can define custom schemas that inherit
    from pydantic.BaseModel directly, without needing to inherit from
    simkit.config.schema.StrictBaseModel.
    """
    # Define external schemas (plain BaseModel, not StrictBaseModel)
    class ExternalInput(BaseModel):
        """Custom input schema from external package."""
        value: float
        unit: str = "MW"

    class ExternalOutput(BaseModel):
        """Custom output schema from external package."""
        result: float
        status: str

    class ExternalModule(ModuleBase[ExternalInput, ExternalOutput]):
        name = "external_module"
        version = "v1.0"

        def validate_and_fill_default(self, value: float, unit: str = "MW"):
            return ExternalInput(value=value, unit=unit)

        def run(self, value: float, unit: str = "MW"):
            inputs = self.validate_and_fill_default(value=value, unit=unit)
            return ModuleResult(
                data=ExternalOutput(result=inputs.value * 2.0, status="computed")
            )

    # Should create registry without type errors
    registry = create_registry([ExternalModule])

    # Verify registration worked
    assert registry.has("ExternalModule")
    descriptor = registry.get("ExternalModule")

    # Verify types are preserved (BaseModel subclasses, not StrictBaseModel)
    assert issubclass(descriptor.required_inputs["value"].__class__, type)
    assert issubclass(descriptor.outputs["result"].__class__, type)

    # Verify factory works
    module = descriptor.factory()
    assert isinstance(module, ExternalModule)

    # Verify module executes correctly
    result = module.run(value=100.0)
    assert result.data.result == 200.0
    assert result.data.status == "computed"


def test_create_registry_introspects_multi_output_modules():
    """Test that create_registry can introspect MultiOutput modules.

    This verifies Issue 3 fix: Modules using MultiOutput can be auto-registered
    via create_registry() without manual ModuleDescriptor construction.
    """
    from simkit.config.schema import MultiOutput

    # Define multi-output schemas
    class PowerValue(BaseModel):
        value: float

    class FusionParams(BaseModel):
        p_fusion: float

    class AlphaNeutronOutput(MultiOutput):
        """Multi-output container."""
        p_alpha: PowerValue
        p_neutron: PowerValue

    class AlphaNeutronModule(ModuleBase[FusionParams, AlphaNeutronOutput]):
        name = "alphaneutron"
        version = "v1.0"

        def validate_and_fill_default(self, p_fusion: float):
            return FusionParams(p_fusion=p_fusion)

        def run(self, p_fusion: float):
            params = self.validate_and_fill_default(p_fusion=p_fusion)
            p_alpha_val = params.p_fusion * 0.2
            p_neutron_val = params.p_fusion * 0.8
            return ModuleResult(
                data=AlphaNeutronOutput(
                    p_alpha=PowerValue(value=p_alpha_val),
                    p_neutron=PowerValue(value=p_neutron_val),
                )
            )

    # Should successfully introspect and register
    registry = create_registry([AlphaNeutronModule])

    # Verify registration
    assert registry.has("AlphaNeutronModule")
    descriptor = registry.get("AlphaNeutronModule")

    # Verify inputs extracted correctly
    assert "p_fusion" in descriptor.required_inputs
    assert descriptor.required_inputs["p_fusion"] == float

    # Verify outputs extracted from MultiOutput fields
    assert "p_alpha" in descriptor.outputs
    assert "p_neutron" in descriptor.outputs
    assert descriptor.outputs["p_alpha"] == PowerValue
    assert descriptor.outputs["p_neutron"] == PowerValue

    # Verify module executes
    module = descriptor.factory()
    result = module.run(p_fusion=100.0)
    assert isinstance(result.data, AlphaNeutronOutput)
    assert result.data.p_alpha.value == 20.0
    assert result.data.p_neutron.value == 80.0
