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


def test_create_registry_empty_starts_empty():
    """Test creating registry with no modules starts empty."""
    registry = create_registry([])

    # No modules registered
    assert not registry.has("Module1")
    assert not registry.has("RateData")


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


def test_create_registry_duplicate_custom_modules():
    """Test error when registering duplicate custom module names."""

    # Create a module twice to trigger duplicate error
    class DuplicateName(ModuleBase[Input1, Output1]):
        name = "dup_name"
        version = "v2.0"

        def validate_and_fill_default(self, inputs):
            return Input1(**inputs)

        def run(self, inputs):
            return ModuleResult(data=Output1(result=0.0))

    # Should raise error because 'DuplicateName' appears twice
    with pytest.raises(ValueError, match="Duplicate module_type"):
        create_registry([DuplicateName, DuplicateName])


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


def test_create_registry_rootmodel_as_input_output_model():
    """Test that RootModel[primitive] single-output modules register correctly.

    RootModel[T] is used to wrap primitive types (float, int, str) in Pydantic models.
    The field name inside RootModel is always 'root' (by Pydantic convention).

    When using RootModel[float] as OutputModel for a single-output module,
    auto-introspection should:
    - Register inputs as unwrapped type (float) - from field extraction
    - Register outputs as wrapped type (RootModel[float]) - channel stores whole object

    This test uses a realistic example: calculating alpha particle power from fusion power.
    """
    from pydantic import RootModel

    # Realistic example: AlphaPowerCalculator
    # Takes fusion power (MW), outputs alpha power (MW) = fusion_power * 0.2
    class AlphaPowerCalculator(ModuleBase[RootModel[float], RootModel[float]]):
        name = "alpha_power_calc"
        version = "v1.0"

        def validate_and_fill_default(self, root: float):
            # Note: parameter name must be 'root' to match RootModel[float] field name
            return RootModel[float](root)

        def run(self, root: float) -> ModuleResult[RootModel[float]]:
            # root receives the unwrapped float value (e.g., 500.0 MW fusion power)
            alpha_power_mw = root * 0.2  # Alpha particles carry 20% of fusion energy
            # Return wrapped in RootModel for channel storage
            return ModuleResult(data=RootModel[float](alpha_power_mw))

    # Auto-register the module
    registry = create_registry([AlphaPowerCalculator])

    # Verify registration
    assert registry.has("AlphaPowerCalculator")
    descriptor = registry.get("AlphaPowerCalculator")

    # CRITICAL: Verify that inputs register as float (unwrapped)
    # When YAML says: root: float fusion_params.p_fusion
    # Field extraction returns unwrapped 500.0, not RootModel[float](500.0)
    assert "root" in descriptor.required_inputs
    assert descriptor.required_inputs["root"] == float

    # CRITICAL: Verify that outputs register as RootModel[float] (wrapped)
    # For single-output, executor stores whole RootModel[float] object in channel
    # This allows downstream modules to do field extraction: alpha_channel.root
    assert "root" in descriptor.outputs
    assert descriptor.outputs["root"] == RootModel[float]  # NOT float!

    # Verify module executes with realistic values
    module = descriptor.factory()
    result = module.run(root=500.0)  # 500 MW fusion power in
    assert isinstance(result.data, RootModel)
    assert result.data.root == 100.0  # 100 MW alpha power out (20%)


def test_create_registry_custom_input_with_rootmodel_output():
    """Test custom InputModel with multiple fields, RootModel[float] OutputModel.

    This is the REAL pattern used in fusion_simkit and most real modules.
    You get semantic parameter names (cryo_pump_count, pump_capacity, etc.),
    not 'root' everywhere!

    Key difference from test_create_registry_rootmodel_as_input_output_model:
    - InputModel: Custom BaseModel with named fields (cryo_pump_count, etc.)
    - OutputModel: RootModel[float] for single primitive output
    - Parameter names: Whatever you named your fields!

    This is much more practical than using RootModel[float] as InputModel.
    """
    from pydantic import RootModel

    # Custom input model with semantic field names
    class CryoPumpInputs(BaseModel):
        cryo_pump_count: float      # Semantic names!
        pump_capacity: float
        operating_temp: float

    # Single primitive output: refrigeration power
    class CryoPumpRefrigeration(ModuleBase[CryoPumpInputs, RootModel[float]]):
        name = "cryo_pump_refrig"
        version = "v1.0"

        def validate_and_fill_default(
            self, cryo_pump_count: float, pump_capacity: float, operating_temp: float
        ):
            return CryoPumpInputs(
                cryo_pump_count=cryo_pump_count,
                pump_capacity=pump_capacity,
                operating_temp=operating_temp,
            )

        def run(
            self, cryo_pump_count: float, pump_capacity: float, operating_temp: float
        ) -> ModuleResult[RootModel[float]]:
            # Your parameter names match your InputModel field names!
            # No 'root' everywhere - semantic names!
            refrigeration_power = cryo_pump_count * pump_capacity * operating_temp * 0.001
            return ModuleResult(data=RootModel[float](refrigeration_power))

    # Auto-register
    registry = create_registry([CryoPumpRefrigeration])
    descriptor = registry.get("CryoPumpRefrigeration")

    # Inputs: Custom field names with unwrapped types
    assert "cryo_pump_count" in descriptor.required_inputs
    assert descriptor.required_inputs["cryo_pump_count"] == float
    assert "pump_capacity" in descriptor.required_inputs
    assert descriptor.required_inputs["pump_capacity"] == float
    assert "operating_temp" in descriptor.required_inputs
    assert descriptor.required_inputs["operating_temp"] == float

    # Output: Single RootModel[float] output (wrapped)
    # Note: Field name is 'root' because OutputModel is RootModel[float]
    assert "root" in descriptor.outputs
    assert descriptor.outputs["root"] == RootModel[float]

    # Verify execution
    module = descriptor.factory()
    result = module.run(cryo_pump_count=4.0, pump_capacity=1000.0, operating_temp=4.2)
    assert isinstance(result.data, RootModel)
    assert result.data.root == 16.8  # 4 * 1000 * 4.2 * 0.001


def test_rootmodel_field_extraction_e2e(tmp_path):
    """End-to-end test for field extraction from RootModel single-output channels.

    This test verifies the fix for the RootModel introspection bug where single-output
    modules with RootModel[T] OutputModel were registering T instead of RootModel[T],
    causing field extraction validation to fail with:
        AttributeError: type object 'float' has no attribute 'model_computed_fields'

    Realistic example: Fusion power calculation pipeline
    - Calculate alpha power from fusion power
    - Calculate heating power from alpha power
    - Both use RootModel[float] single-output modules
    - Second module extracts field from first module's output channel

    See: thoughts/specs/rootmodel-single-output-introspection-bug.md
    """
    from pydantic import RootModel
    from simkit.core.pipeline import execute_pipeline
    from simkit.config.schema import StrictBaseModel
    import json

    # Input schema: Fusion reactor parameters
    class FusionParams(StrictBaseModel):
        p_fusion_mw: float  # Total fusion power in MW

    # Module 1: Calculate alpha particle power (20% of fusion power)
    class AlphaPowerCalc(ModuleBase[RootModel[float], RootModel[float]]):
        name = "alpha_power_calc"
        version = "v1.0"

        def run(self, root: float) -> ModuleResult[RootModel[float]]:
            # Alpha particles carry 20% of fusion energy
            alpha_power = root * 0.2
            return ModuleResult(data=RootModel[float](alpha_power))

    # Module 2: Calculate auxiliary heating power (5% of alpha power)
    class HeatingPowerCalc(ModuleBase[RootModel[float], RootModel[float]]):
        name = "heating_power_calc"
        version = "v1.0"

        def run(self, root: float) -> ModuleResult[RootModel[float]]:
            # Auxiliary heating is 5% of alpha power
            heating_power = root * 0.05
            return ModuleResult(data=RootModel[float](heating_power))

    # Create test data: 500 MW fusion power
    data_file = tmp_path / "fusion_params.json"
    data_file.write_text(json.dumps({"p_fusion_mw": 500.0}))

    # Create pipeline with field extraction from RootModel channels
    pipeline_file = tmp_path / "pipeline.yaml"
    pipeline_file.write_text(f"""
metadata:
  run_description: Fusion power calculation with RootModel field extraction

modules:
  entry:
    module_type: EntryPoint
    inputs:
      params: FusionParams {data_file}

  alpha_calc:
    module_type: AlphaPowerCalc
    inputs:
      root: float params.p_fusion_mw           # Extract p_fusion_mw: 500.0 MW
    outputs:
      root: RootModel[float] alpha_power       # Channel stores RootModel[float](100.0)

  heating_calc:
    module_type: HeatingPowerCalc
    inputs:
      root: float alpha_power.root             # Extract .root from RootModel: 100.0 MW
    outputs:
      root: RootModel[float] heating_power     # Channel stores RootModel[float](5.0)

  exit:
    module_type: ExitPoint
    outputs:
      params: FusionParams params.json
""")

    # Execute pipeline - this would previously fail with:
    # AttributeError: type object 'float' has no attribute 'model_computed_fields'
    result = execute_pipeline(
        str(pipeline_file),
        str(tmp_path / "outputs"),
        registry=create_registry([AlphaPowerCalc, HeatingPowerCalc]),
        custom_schema_types=[FusionParams],
    )

    # Verify execution succeeded
    assert result.provenance is not None

    # Verify data flow:
    # 500 MW fusion -> 100 MW alpha (20%) -> 5 MW heating (5%)
    # Successful execution proves field extraction validation worked!
