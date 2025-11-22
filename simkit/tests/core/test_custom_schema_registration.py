"""Comprehensive tests for custom schema registration feature.

Tests the complete flow from custom_schema_types parameter through registry
building, executor integration, validation, and execution.

Test Categories:
1. Registry Building (Phase 1)
2. Executor/Validator Integration (Phase 2)
3. Pipeline API (Phase 3)
4. Error Conditions & Edge Cases
5. Backward Compatibility
"""

import json
import pytest
from pathlib import Path
from pydantic import BaseModel, RootModel

from simkit.config.schema import StrictBaseModel
from simkit.core.pipeline import execute_pipeline
from simkit.core.pipeline_executor import (
    SerialPipelineExecutor,
    _build_schema_type_registry,
    _build_entry_loaders,
    _BUILTIN_ENTRY_LOADERS,
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
        """Registry includes all 18 built-in TEAx schemas."""
        registry = _build_schema_type_registry()

        # Check a few key built-ins
        assert "Geography" in registry
        assert "RateInfo" in registry
        assert "BatteryConfig" in registry
        assert "LoadProfile8760" in registry

        # Should have all built-ins (18 total)
        assert len(registry) >= 18

    def test_adds_custom_schema(self):
        """Custom type added to registry with correct name."""
        registry = _build_schema_type_registry([CustomParamsA])

        assert "CustomParamsA" in registry
        assert registry["CustomParamsA"] is CustomParamsA

        # Built-ins still present
        assert "Geography" in registry

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
        # Create custom type named "Geography"
        class Geography(StrictBaseModel):
            custom_field: str

        with pytest.raises(ValueError, match="Duplicate schema type name 'Geography'"):
            _build_schema_type_registry([Geography])

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

        assert "Geography" in registry
        assert "CustomParamsA" not in registry

    def test_all_user_facing_schemas_registered(self):
        """Validate all user-facing built-in schemas are registered.

        This test prevents silent breakage when new schemas are added to
        simkit.config.schema without updating _build_schema_type_registry().

        User-facing schemas are those intended for:
        - EntryPoint artifact loading (e.g., Geography, LoadProfile8760)
        - Module I/O type hints (e.g., BatteryConfig, RateInfo)
        - ExitPoint output writing (e.g., FinancialResults, BatteryTelemetry8760)

        Excluded schemas:
        - MultiOutput: Abstract base class for multi-output modules
        - Provenance, PipelineRunMetadata, RunManifest, RunArtifactRecord:
          Pipeline metadata (internal use only, not user-loadable)
        - CostLineItem, CashflowEntry, LedgerEntry:
          Nested fields within larger schemas (not standalone artifacts)
        - TimeSpan, SyncOuterStep, InnerLoopConfig, etc.:
          Internal synchronous sim types (not standalone artifacts)
        - DesignPrefs: Optional module input, not loaded from EntryPoint
        """
        from simkit.config import schema
        import inspect

        registry = _build_schema_type_registry()

        # Define expected user-facing schemas (must match _build_schema_type_registry)
        # This list should be updated when new user-facing schemas are added
        expected_user_facing_schemas = [
            schema.Geography,
            schema.FinancialParams,
            schema.LoadProfile8760,
            schema.PVProfile8760,
            schema.RateInfo,
            schema.BatteryConfig,
            schema.BatteryTelemetry8760,
            schema.CostBreakdown,
            schema.FinancialResults,
            schema.SyncTimeGrid,
            schema.BatteryState,
            schema.PriceTrajectory,
            schema.MockForecastConfig,
            schema.GuidanceConfig,
            schema.DynamicSimConfig,
            schema.MockForecastSeries,
            schema.SyncGuidanceSeries,
            schema.SyncTelemetrySeries,
            # Add new user-facing schemas here as they are created
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

        # Verify count matches (18 currently expected)
        assert len(expected_user_facing_schemas) == 18, (
            f"Expected 18 user-facing schemas, but list has "
            f"{len(expected_user_facing_schemas)}. Update this test when "
            f"adding/removing user-facing schemas."
        )

        # Optional: Warn about unregistered StrictBaseModel subclasses
        # This helps catch schemas that should be registered but aren't
        all_schema_classes = [
            obj for name, obj in inspect.getmembers(schema, inspect.isclass)
            if (issubclass(obj, schema.StrictBaseModel)
                and obj is not schema.StrictBaseModel
                and not name.startswith('_'))
        ]

        unregistered_schemas = [
            cls for cls in all_schema_classes
            if cls.__name__ not in registry
        ]

        # Document which schemas are intentionally unregistered
        intentionally_excluded = {
            'MultiOutput',  # Abstract base class for multi-output modules
            'Provenance',  # Pipeline metadata
            'PipelineRunMetadata',  # Pipeline metadata
            'RunArtifactRecord',  # Pipeline metadata
            'RunManifest',  # Pipeline metadata
            'CostLineItem',  # Nested field in CostBreakdown
            'CashflowEntry',  # Nested field in FinancialResults
            'LedgerEntry',  # Nested field in FinancialResults
            'DesignPrefs',  # Optional module input, not loaded from EntryPoint
            'TimeSpan',  # Internal synchronous sim type
            'SyncOuterStep',  # Internal synchronous sim type
            'InnerLoopConfig',  # Internal synchronous sim type
            'PriceTrajectoryWindow',  # Derived from PriceTrajectory, internal only
            'MockForecastMetadata',  # Metadata field within MockForecastPoint
            'MockForecastPoint',  # Nested type within MockForecastSeries
            'GuidanceMetadata',  # Metadata field within SyncGuidance
            'SyncGuidance',  # Nested type within SyncGuidanceSeries
            'DynamicsInitInput',  # Internal module private input
            'DynamicsStepInput',  # Internal module private input
            'SyncTelemetryFrame',  # Nested type within SyncTelemetrySeries
            'SyncSimOutputs',  # Internal module composite output
        }

        unexpected_unregistered = [
            cls.__name__ for cls in unregistered_schemas
            if cls.__name__ not in intentionally_excluded
        ]

        if unexpected_unregistered:
            import warnings
            warnings.warn(
                f"Found unregistered schemas that may need registration: "
                f"{unexpected_unregistered}. Review these and either add to "
                f"_build_schema_type_registry() or add to intentionally_excluded "
                f"set in this test.",
                UserWarning
            )


class TestBuildEntryLoaders:
    """Tests for _build_entry_loaders() function."""

    def test_includes_builtin_loaders(self):
        """Loader registry includes all built-in loaders."""
        loaders = _build_entry_loaders()

        # Check it's a copy, not reference to _BUILTIN_ENTRY_LOADERS
        assert loaders is not _BUILTIN_ENTRY_LOADERS

        # Check key built-in loaders present
        from simkit.config import schema
        assert schema.Geography in loaders
        assert schema.LoadProfile8760 in loaders
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
        """Executor works with no arguments (backward compat)."""
        executor = SerialPipelineExecutor()

        # Should use built-in defaults
        assert executor._schema_type_registry is None
        assert executor._entry_loaders is not None
        assert len(executor._entry_loaders) > 0

    def test_backward_compatible_with_registry_only(self):
        """Executor works with only registry arg (existing pattern)."""
        registry = PipelineModuleRegistry.from_static_modules()
        executor = SerialPipelineExecutor(registry)

        assert executor._registry is registry


class TestPipelineValidatorIntegration:
    """Tests for validator with custom schema registry."""

    def test_constructor_accepts_optional_parameter(self):
        """Validator accepts schema_type_registry parameter."""
        schema_registry = _build_schema_type_registry([CustomParamsA])
        registry = PipelineModuleRegistry.from_static_modules()
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
      root: float doubled

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
