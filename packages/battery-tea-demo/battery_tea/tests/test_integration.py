"""Integration tests for battery TEA pipelines."""
from __future__ import annotations

import pytest
from pydantic import RootModel

from battery_tea import create_battery_registry, schemas
from simkit.config import schema as simkit_schema


class TestRegistryIntegration:
    """Tests for battery registry integration with simkit."""

    def test_create_battery_registry(self):
        """create_battery_registry returns a valid registry."""
        registry = create_battery_registry()

        assert registry is not None
        # Should have registered modules
        module_count = sum(1 for _ in registry.items())
        assert module_count > 0

    def test_registry_contains_expected_modules(self):
        """Registry contains all expected battery modules."""
        registry = create_battery_registry()
        module_names = {name for name, _ in registry.items()}

        # Check for expected module types
        expected = {
            "RateData",
            "ConfigureBattery",
            "SimplePerformanceSim",
            "CostCalculator",
            "ProjectAnalyzer",
            "SynchronousSim",
        }

        for expected_name in expected:
            assert expected_name in module_names, f"Missing module: {expected_name}"

    def test_registry_module_descriptors_valid(self):
        """Each registered module has valid descriptor metadata."""
        registry = create_battery_registry()

        for module_type, descriptor in registry.items():
            # Descriptor should have required fields
            assert descriptor.module_type == module_type
            assert callable(descriptor.factory)
            assert isinstance(descriptor.required_inputs, dict) or isinstance(descriptor.required_inputs, type({}.keys()))
            assert isinstance(descriptor.outputs, dict) or isinstance(descriptor.outputs, type({}.keys()))
            assert isinstance(descriptor.version, str)


class TestModuleInstantiation:
    """Tests for module instantiation via registry."""

    def test_rate_data_module_factory(self):
        """RateData module can be instantiated from registry."""
        registry = create_battery_registry()
        descriptor = registry.get("RateData")
        module = descriptor.factory()

        assert module is not None
        assert hasattr(module, "run")
        assert hasattr(module, "validate_and_fill_default")

    def test_configure_battery_module_factory(self):
        """ConfigureBattery module can be instantiated from registry."""
        registry = create_battery_registry()
        descriptor = registry.get("ConfigureBattery")
        module = descriptor.factory()

        assert module is not None
        assert hasattr(module, "run")

    def test_cost_calculator_module_factory(self):
        """CostCalculator module can be instantiated from registry."""
        registry = create_battery_registry()
        descriptor = registry.get("CostCalculator")
        module = descriptor.factory()

        assert module is not None
        assert hasattr(module, "run")

    def test_simple_performance_sim_module_factory(self):
        """SimplePerformanceSim module can be instantiated from registry."""
        registry = create_battery_registry()
        descriptor = registry.get("SimplePerformanceSim")
        module = descriptor.factory()

        assert module is not None
        assert hasattr(module, "run")

    def test_project_analyzer_module_factory(self):
        """ProjectAnalyzer module can be instantiated from registry."""
        registry = create_battery_registry()
        descriptor = registry.get("ProjectAnalyzer")
        module = descriptor.factory()

        assert module is not None
        assert hasattr(module, "run")

    def test_synchronous_sim_module_factory(self):
        """SynchronousSim module can be instantiated from registry."""
        registry = create_battery_registry()
        descriptor = registry.get("SynchronousSim")
        module = descriptor.factory()

        assert module is not None
        assert hasattr(module, "run")


class TestPipelineExecution:
    """Tests for YAML pipeline execution."""

    def test_demo_linear_pipeline_executes(self, tmp_path):
        """demo_linear_alt.yaml executes successfully."""
        from pathlib import Path

        from simkit.core.pipeline import execute_pipeline

        registry = create_battery_registry()
        config_path = Path(__file__).parent / "fixtures" / "pipeline_configs" / "demo_linear_alt.yaml"

        result = execute_pipeline(
            str(config_path),
            output_dir=str(tmp_path),
            registry=registry,
            custom_schema_types=[
                schemas.Geography,
                schemas.LoadProfile8760,
                schemas.RateInfo,
                schemas.BatteryConfig,
                schemas.BatteryTelemetry8760,
                schemas.CostBreakdown,
                # RootModel wrappers actually carried on the exit channels, so the
                # default router registers write handlers for them.
                schemas.RateInfoOutput,
                schemas.BatteryConfigOutput,
                schemas.BatteryTelemetry8760Output,
                schemas.CostBreakdownOutput,
                RootModel[simkit_schema.FinancialResults],
            ],
        )

        # Verify outputs exist
        assert result.outputs is not None
        assert "rate_info" in result.outputs
        assert "battery_config" in result.outputs
        assert "telemetry" in result.outputs
        assert "cost_breakdown" in result.outputs
        assert "financial_results" in result.outputs
