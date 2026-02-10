"""Comprehensive tests for custom schema registration feature.

Tests the complete flow from custom_schema_types parameter through registry
building, executor integration, validation, and execution.

Test Categories:
1. Registry Building (Phase 1)
2. Executor/Validator Integration (Phase 2)
3. Pipeline API (Phase 3)
4. Error Conditions & Edge Cases
"""

import json
import pytest
from pathlib import Path
from pydantic import BaseModel, RootModel

from simkit.config.schema import StrictBaseModel
from simkit.config import schema
from simkit.core.pipeline import execute_pipeline
from simkit.core.pipeline_executor import (
    SerialPipelineExecutor,
    _build_schema_type_registry,
    _build_entry_loaders,
    _BUILTIN_ENTRY_LOADERS,
    _resolve_schema_type,
    _PRIMITIVE_TYPES,
)
from simkit.core.pipeline_validator import PipelineValidator
from simkit.core.registry_builder import create_registry
from simkit.core.base import ModuleBase, ModuleResult
from simkit.io.output_router import create_default_router
from simkit.core.pipeline_registry import PipelineModuleRegistry


# Test fixtures
class CustomParamsA(StrictBaseModel):
    """Test custom schema A."""
    value_a: float
    text_a: str


class CustomParamsB(StrictBaseModel):
    """Test custom schema B."""
    value_b: int
    nested: CustomParamsA | None = None


class NotABaseModel:
    """Invalid type for testing error conditions."""
    pass


# Phase 1 Tests
class TestBuildSchemaTypeRegistry:
    """Tests for _build_schema_type_registry() function."""

    def test_returns_dict_with_builtin_schemas(self):
        """Registry includes all built-in generic TEAx schemas."""
        registry = _build_schema_type_registry()

        # Check generic built-in types
        assert "FinancialParams" in registry
        assert "FinancialResults" in registry
        assert "SyncTimeGrid" in registry
        assert "PriceTrajectory" in registry
        assert "MockForecastConfig" in registry
        assert "DynamicSimConfig" in registry
        assert "MockForecastSeries" in registry
        assert "SyncGuidanceSeries" in registry

        # Should have 8 Pydantic schemas + 4 primitives = 12 built-ins
        assert len(registry) == 12

    def test_adds_custom_schema(self):
        """Custom type added to registry with correct name."""
        registry = _build_schema_type_registry([CustomParamsA])

        assert "CustomParamsA" in registry
        assert registry["CustomParamsA"] is CustomParamsA

        # Built-ins still present
        assert "FinancialParams" in registry

    def test_adds_multiple_custom_schemas(self):
        """Multiple custom types added correctly."""
        registry = _build_schema_type_registry([CustomParamsA, CustomParamsB])

        assert "CustomParamsA" in registry
        assert "CustomParamsB" in registry
        assert registry["CustomParamsA"] is CustomParamsA
        assert registry["CustomParamsB"] is CustomParamsB

    def test_rejects_duplicate_custom_names(self):
        """Duplicate type names in list raise ValueError."""
        # Pass same class twice
        with pytest.raises(ValueError, match="Duplicate schema type name 'CustomParamsA'"):
            _build_schema_type_registry([CustomParamsA, CustomParamsA])

    def test_rejects_custom_conflicting_with_builtin(self):
        """Custom type with built-in name raises ValueError."""
        # Create custom type named "FinancialParams" (a generic built-in)
        class FinancialParams(StrictBaseModel):
            custom_field: str

        with pytest.raises(ValueError, match="Duplicate schema type name 'FinancialParams'"):
            _build_schema_type_registry([FinancialParams])

    def test_rejects_non_basemodel_type(self):
        """Non-Pydantic type raises TypeError."""
        with pytest.raises(TypeError, match="must be a Pydantic BaseModel subclass"):
            _build_schema_type_registry([NotABaseModel])

    def test_rejects_instance_instead_of_class(self):
        """Passing instance instead of class raises TypeError."""
        instance = CustomParamsA(value_a=1.0, text_a="test")

        with pytest.raises(TypeError, match="must be a Pydantic BaseModel subclass"):
            _build_schema_type_registry([instance])

    def test_empty_list_returns_builtins_only(self):
        """Empty custom type list returns only built-ins."""
        registry = _build_schema_type_registry([])

        assert "FinancialParams" in registry
        assert "CustomParamsA" not in registry

    def test_all_user_facing_schemas_registered(self):
        """Validate all user-facing built-in schemas are registered.

        This test prevents silent breakage when new schemas are added to
        simkit.config.schema without updating _build_schema_type_registry().

        User-facing schemas are those intended for:
        - EntryPoint artifact loading
        - Module I/O type hints
        - ExitPoint output writing
        """
        import inspect

        registry = _build_schema_type_registry()

        # Define expected generic user-facing schemas
        expected_user_facing_schemas = [
            schema.FinancialParams,
            schema.FinancialResults,
            schema.SyncTimeGrid,
            schema.PriceTrajectory,
            schema.MockForecastConfig,
            schema.DynamicSimConfig,
            schema.MockForecastSeries,
            schema.SyncGuidanceSeries,
        ]

        # Verify all expected schemas are registered
        for schema_cls in expected_user_facing_schemas:
            schema_name = schema_cls.__name__
            assert schema_name in registry, (
                f"User-facing schema '{schema_name}' not registered in "
                f"_build_schema_type_registry(). Update the registry builder "
                f"in simkit/core/pipeline_executor.py"
            )
            assert registry[schema_name] is schema_cls, (
                f"Schema '{schema_name}' registered but points to wrong type"
            )

        # Verify primitive types are registered
        for name, expected_type in [("float", float), ("int", int), ("str", str), ("bool", bool)]:
            assert name in registry, f"Primitive type '{name}' not registered"
            assert registry[name] is expected_type

        # Verify count matches (8 Pydantic schemas + 4 primitives = 12)
        assert len(registry) == 12, (
            f"Expected 12 built-in registry entries (8 schemas + 4 primitives), "
            f"got {len(registry)}. Update this test when adding/removing types."
        )


class TestPrimitiveTypeSupport:
    """Tests for primitive type resolution, registry, and entry loaders."""

    def test_schema_registry_includes_primitives(self):
        """Built-in registry includes float, int, str, bool."""
        registry = _build_schema_type_registry()
        for name, expected_type in [("float", float), ("int", int), ("str", str), ("bool", bool)]:
            assert name in registry
            assert registry[name] is expected_type

    def test_resolve_schema_type_primitives_with_registry(self):
        """_resolve_schema_type returns primitive types when registry is provided."""
        registry = _build_schema_type_registry()
        for name, expected in [("float", float), ("int", int), ("str", str), ("bool", bool)]:
            assert _resolve_schema_type(name, registry) is expected

    def test_resolve_schema_type_primitives_fallback(self):
        """_resolve_schema_type returns primitive types via fallback (no registry)."""
        for name, expected in [("float", float), ("int", int), ("str", str), ("bool", bool)]:
            assert _resolve_schema_type(name, None) is expected

    def test_primitive_entry_loaders_registered(self):
        """All 4 primitive types have entry loaders in _BUILTIN_ENTRY_LOADERS."""
        for t in (float, int, str, bool):
            assert t in _BUILTIN_ENTRY_LOADERS, f"Missing entry loader for {t.__name__}"

    def test_primitive_entry_loader_reads_float(self, tmp_path):
        """Primitive entry loader deserializes a bare float from JSON."""
        path = tmp_path / "value.json"
        path.write_text("42.0")
        result = _BUILTIN_ENTRY_LOADERS[float](path)
        assert isinstance(result, float)
        assert result == 42.0

    def test_primitive_entry_loader_reads_int(self, tmp_path):
        """Primitive entry loader deserializes a bare int from JSON."""
        path = tmp_path / "value.json"
        path.write_text("7")
        result = _BUILTIN_ENTRY_LOADERS[int](path)
        assert type(result) is int
        assert result == 7

    def test_primitive_entry_loader_reads_str(self, tmp_path):
        """Primitive entry loader deserializes a bare str from JSON."""
        path = tmp_path / "value.json"
        path.write_text('"hello"')
        result = _BUILTIN_ENTRY_LOADERS[str](path)
        assert type(result) is str
        assert result == "hello"

    def test_primitive_entry_loader_reads_bool(self, tmp_path):
        """Primitive entry loader deserializes a bare bool from JSON."""
        path = tmp_path / "value.json"
        path.write_text("true")
        result = _BUILTIN_ENTRY_LOADERS[bool](path)
        assert type(result) is bool
        assert result is True

    def test_primitive_entry_loader_rejects_bool_as_int(self, tmp_path):
        """Primitive int loader rejects JSON true (bool is subclass of int)."""
        path = tmp_path / "value.json"
        path.write_text("true")
        with pytest.raises(TypeError, match="Expected int"):
            _BUILTIN_ENTRY_LOADERS[int](path)

    def test_primitive_entry_loader_rejects_type_mismatch(self, tmp_path):
        """Primitive entry loader raises TypeError on type mismatch."""
        path = tmp_path / "value.json"
        path.write_text('"hello"')  # str, not int
        with pytest.raises(TypeError, match="Expected int"):
            _BUILTIN_ENTRY_LOADERS[int](path)


class TestBuildChannelTypeMapPrimitiveFallback:
    """Tests for _build_channel_type_map primitive type resolution in PipelineValidator."""

    def test_build_channel_type_map_resolves_primitives_without_registry(self):
        """Validator's _build_channel_type_map resolves primitive types via fallback (no schema_type_registry)."""
        from simkit.config.pipeline_schema import (
            ChannelSource,
            PipelineChannelBinding,
            PipelineModuleSpec,
            PipelineSpecification,
        )

        # Build a minimal spec with an EntryPoint that outputs a primitive type
        entry_spec = PipelineModuleSpec(
            key="entry",
            module_type="EntryPoint",
            inputs={"val": PipelineChannelBinding(
                type_name="float",
                channel_name="val",
                source=ChannelSource.ENTRY,
                artifact_path=Path("val.json"),
            )},
            outputs={"val": PipelineChannelBinding(
                type_name="float",
                channel_name="val",
                source=ChannelSource.MODULE,
            )},
        )
        exit_spec = PipelineModuleSpec(
            key="exit",
            module_type="ExitPoint",
            inputs={},
            outputs={"val": PipelineChannelBinding(
                type_name="float",
                channel_name="val",
                source=ChannelSource.MODULE,
                destination_filename="val.json",
            )},
        )
        spec = PipelineSpecification(
            modules={"entry": entry_spec, "exit": exit_spec},
        )

        # Create validator WITHOUT schema_type_registry (forces fallback path)
        registry = PipelineModuleRegistry()
        router = create_default_router()
        validator = PipelineValidator(registry, router, schema_type_registry=None)

        channel_types = validator._build_channel_type_map(spec)
        assert "val" in channel_types
        assert channel_types["val"] is float


class TestBuildEntryLoaders:
    """Tests for _build_entry_loaders() function."""

    def test_includes_builtin_loaders(self):
        """Loader registry includes all built-in loaders."""
        loaders = _build_entry_loaders()

        # Check it's a copy, not reference to _BUILTIN_ENTRY_LOADERS
        assert loaders is not _BUILTIN_ENTRY_LOADERS

        # Check key generic built-in loaders present
        assert schema.FinancialParams in loaders
        assert schema.SyncTimeGrid in loaders
        assert schema.PriceTrajectory in loaders

    def test_registers_custom_type_loader(self):
        """Custom type gets loader registered."""
        loaders = _build_entry_loaders([CustomParamsA])

        assert CustomParamsA in loaders
        assert callable(loaders[CustomParamsA])

    def test_custom_loader_can_load_json(self, tmp_path):
        """Generated loader successfully deserializes JSON file."""
        loaders = _build_entry_loaders([CustomParamsA])
        loader = loaders[CustomParamsA]

        # Create test JSON file
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps({"value_a": 42.5, "text_a": "hello"}))

        # Load using generated loader
        obj = loader(test_file)

        assert isinstance(obj, CustomParamsA)
        assert obj.value_a == 42.5
        assert obj.text_a == "hello"

    def test_multiple_custom_loaders_independent(self, tmp_path):
        """Multiple custom loaders don't interfere (lambda closure test)."""
        loaders = _build_entry_loaders([CustomParamsA, CustomParamsB])

        # Create test files
        file_a = tmp_path / "a.json"
        file_a.write_text(json.dumps({"value_a": 1.0, "text_a": "A"}))

        file_b = tmp_path / "b.json"
        file_b.write_text(json.dumps({"value_b": 99, "nested": None}))

        # Load with correct loaders
        obj_a = loaders[CustomParamsA](file_a)
        obj_b = loaders[CustomParamsB](file_b)

        # Verify types are correct (not all mapped to same type)
        assert isinstance(obj_a, CustomParamsA)
        assert isinstance(obj_b, CustomParamsB)
        assert obj_a.text_a == "A"
        assert obj_b.value_b == 99


# Phase 2 Tests
class TestSerialPipelineExecutorIntegration:
    """Tests for executor with custom schema registries."""

    def test_constructor_accepts_optional_parameters(self):
        """Executor accepts new keyword-only parameters."""
        schema_registry = _build_schema_type_registry([CustomParamsA])
        entry_loaders = _build_entry_loaders([CustomParamsA])

        # Should not raise
        executor = SerialPipelineExecutor(
            schema_type_registry=schema_registry,
            entry_loaders=entry_loaders,
        )

        assert executor._schema_type_registry is schema_registry
        assert executor._entry_loaders is entry_loaders

    def test_backward_compatible_with_no_args(self):
        """Executor works with no arguments (creates empty registry)."""
        executor = SerialPipelineExecutor()

        # Should use built-in defaults
        assert executor._schema_type_registry is None
        assert executor._entry_loaders is not None
        assert len(executor._entry_loaders) > 0

    def test_backward_compatible_with_registry_only(self):
        """Executor works with only registry arg (existing pattern)."""
        registry = PipelineModuleRegistry()
        executor = SerialPipelineExecutor(registry)

        assert executor._registry is registry


class TestPipelineValidatorIntegration:
    """Tests for validator with custom schema registry."""

    def test_constructor_accepts_optional_parameter(self):
        """Validator accepts schema_type_registry parameter."""
        schema_registry = _build_schema_type_registry([CustomParamsA])
        registry = PipelineModuleRegistry()
        router = create_default_router()

        # Should not raise
        validator = PipelineValidator(
            registry,
            router,
            schema_type_registry=schema_registry,
        )

        assert validator._schema_type_registry is schema_registry


# Phase 3 Tests
class TestExecutePipelineAPI:
    """Tests for execute_pipeline() with custom_schema_types."""

    def test_backward_compatible_no_custom_types(self):
        """execute_pipeline accepts call without custom_schema_types (backward compat)."""
        # Test that the signature accepts no custom_schema_types parameter
        # (actual execution would require full pipeline setup with proper OutputRouter handlers)
        # This test verifies backward compatibility of the function signature
        assert hasattr(execute_pipeline, '__call__')

        # Verify the function signature includes the new parameter as optional
        import inspect
        sig = inspect.signature(execute_pipeline)
        assert 'custom_schema_types' in sig.parameters
        assert sig.parameters['custom_schema_types'].default is None


# Phase 4 E2E Tests
class TestE2ECustomSchemaFieldReference:
    """End-to-end integration tests with custom schemas."""

    def test_custom_schema_entry_with_field_reference(self, tmp_path):
        """Full pipeline: custom schema at EntryPoint with field extraction."""
        # Define custom module that uses extracted field and returns simple value
        class FieldDoubler(ModuleBase[RootModel[float], RootModel[float]]):
            name = "field_doubler"
            version = "v1.0"

            def run(self, root: float) -> ModuleResult[RootModel[float]]:
                return ModuleResult(data=RootModel[float](root * 2))

        # Create test data
        data_file = tmp_path / "params.json"
        data_file.write_text(json.dumps({"value_a": 21.0, "text_a": "test"}))

        # Create pipeline
        pipeline_yaml = tmp_path / "pipeline.yaml"
        pipeline_yaml.write_text(f"""
metadata:
  run_description: Test custom schema field reference

modules:
  entry:
    module_type: EntryPoint
    inputs:
      params: CustomParamsA {data_file}

  doubler:
    module_type: FieldDoubler
    inputs:
      root: float params.value_a
    outputs:
      root: RootModel[float] doubled

  exit:
    module_type: ExitPoint
    outputs:
      params: CustomParamsA params.json
""")

        # Execute with custom schema - validates field reference extraction and auto-router
        result = execute_pipeline(
            str(pipeline_yaml),
            str(tmp_path / "outputs"),
            registry=create_registry([FieldDoubler]),
            custom_schema_types=[CustomParamsA],
        )

        # Verify execution succeeded (validates field reference extraction worked)
        # If params.value_a field reference failed, pipeline would have crashed
        assert result.provenance is not None

        # Verify custom schema was loaded and written via auto-created router
        assert "params" in result.outputs
        assert isinstance(result.outputs["params"], CustomParamsA)
        assert result.outputs["params"].value_a == 21.0
        assert result.outputs["params"].text_a == "test"

        # Verify output file was actually written to disk
        output_files = list((tmp_path / "outputs").rglob("params.json"))
        assert len(output_files) == 1, "Custom schema should be written to params.json"


# Error Condition Tests (Risk Scenarios)
class TestErrorConditions:
    """Tests for error handling and edge cases."""

    def test_missing_type_in_custom_list_helpful_error(self, tmp_path):
        """Pipeline referencing unregistered custom type gives helpful error."""
        # Pipeline references CustomParamsB but we don't pass it
        pipeline_yaml = tmp_path / "pipeline.yaml"
        data_file = tmp_path / "data.json"
        data_file.write_text(json.dumps({"value_b": 1, "nested": None}))

        # Add CustomParamsA as exit output (since it's in custom_schema_types)
        data_file_a = tmp_path / "data_a.json"
        data_file_a.write_text(json.dumps({"value_a": 1.0, "text_a": "test"}))

        pipeline_yaml.write_text(f"""
modules:
  entry:
    module_type: EntryPoint
    inputs:
      params_b: CustomParamsB {data_file}
      params_a: CustomParamsA {data_file_a}
  exit:
    module_type: ExitPoint
    outputs:
      params_a: CustomParamsA params_a.json
""")

        # Should fail with helpful message about CustomParamsB not being registered
        with pytest.raises(ValueError, match="Unknown schema type 'CustomParamsB'"):
            execute_pipeline(
                str(pipeline_yaml),
                str(tmp_path / "outputs"),
                custom_schema_types=[CustomParamsA],  # Missing CustomParamsB!
            )
