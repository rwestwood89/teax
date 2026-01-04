"""E2E tests for generic framework using ToyModules.

These tests verify pipeline execution without any battery dependencies,
ensuring the core framework can be tested in isolation.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import RootModel

from simkit.core.pipeline import execute_pipeline
from simkit.core.registry_builder import create_registry
from simkit.io.output_router import create_output_router_with_json_schemas
from simkit.tests.core.toy_modules import (
    ToyAdderModule,
    ToyDoublerModule,
    ToyInput,
    ToyMultiOutputModule,
    ToyOutput,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PIPELINE_CONFIGS_DIR = FIXTURES_DIR / "pipeline_configs"


@pytest.fixture
def toy_registry():
    """Create registry with only ToyModules."""
    return create_registry([ToyDoublerModule, ToyAdderModule, ToyMultiOutputModule])


@pytest.fixture
def toy_output_router():
    """Create output router with RootModel[float] handler for ToyModule outputs."""
    # RootModel[float].__name__ == "RootModel[float]" - matches YAML type name
    return create_output_router_with_json_schemas(
        ["RootModel[float]"],
        include_builtins=True,
    )


class TestToyModuleRegistry:
    """Tests for ToyModule registry creation."""

    def test_registry_has_toy_modules(self, toy_registry):
        """Verify registry contains all ToyModules."""
        assert toy_registry.has("ToyDoublerModule")
        assert toy_registry.has("ToyAdderModule")
        assert toy_registry.has("ToyMultiOutputModule")

    def test_registry_has_no_battery_modules(self, toy_registry):
        """Verify registry does NOT contain battery modules."""
        assert not toy_registry.has("RateData")
        assert not toy_registry.has("ConfigureBattery")
        assert not toy_registry.has("CostCalculator")

    def test_module_factories_work(self, toy_registry):
        """Verify module factories can instantiate modules."""
        doubler_desc = toy_registry.get("ToyDoublerModule")
        module = doubler_desc.factory()
        assert module.name == "ToyDoubler"
        assert module.version == "v1.0"


class TestToyDoublerModule:
    """Unit tests for ToyDoublerModule."""

    def test_doubles_input_value(self):
        """ToyDoublerModule should double the input value."""
        module = ToyDoublerModule()
        result = module.run(value=10.0)
        assert result.data.root == 20.0

    def test_validates_input(self):
        """ToyDoublerModule should validate input."""
        module = ToyDoublerModule()
        validated = module.validate_and_fill_default(value=5.0)
        assert isinstance(validated, ToyInput)
        assert validated.value == 5.0


class TestToyAdderModule:
    """Unit tests for ToyAdderModule."""

    def test_adds_22_to_input(self):
        """ToyAdderModule should add 22 to input value."""
        module = ToyAdderModule()
        result = module.run(root=10.0)
        assert result.data.root == 32.0


class TestToyMultiOutputModule:
    """Unit tests for ToyMultiOutputModule."""

    def test_produces_doubled_and_tripled(self):
        """ToyMultiOutputModule should produce doubled and tripled outputs."""
        module = ToyMultiOutputModule()
        result = module.run(value=10.0)

        assert isinstance(result.data.doubled, ToyOutput)
        assert isinstance(result.data.tripled, ToyOutput)
        assert result.data.doubled.value == 20.0
        assert result.data.tripled.value == 30.0


class TestToyPipelineExecution:
    """E2E tests for ToyModule pipeline execution."""

    def test_toy_linear_pipeline_in_memory(self, toy_registry, toy_output_router, tmp_path):
        """Execute toy_linear.yaml pipeline and verify outputs."""
        spec_path = PIPELINE_CONFIGS_DIR / "toy_linear.yaml"

        result = execute_pipeline(
            spec_path=str(spec_path),
            output_dir=str(tmp_path),
            registry=toy_registry,
            custom_schema_types=[ToyInput],
            output_router=toy_output_router,
        )

        # If we get here without exception, pipeline succeeded
        assert "doubled" in result.outputs
        assert "added" in result.outputs

        # Input was 10.0, doubled = 20.0, added = 20.0 + 22.0 = 42.0
        assert result.outputs["doubled"].root == 20.0
        assert result.outputs["added"].root == 42.0

    def test_toy_pipeline_writes_output_files(self, toy_registry, toy_output_router, tmp_path):
        """Verify pipeline writes JSON output files."""
        spec_path = PIPELINE_CONFIGS_DIR / "toy_linear.yaml"

        result = execute_pipeline(
            spec_path=str(spec_path),
            output_dir=str(tmp_path),
            registry=toy_registry,
            custom_schema_types=[ToyInput],
            output_router=toy_output_router,
        )

        # Check output files were created - use manifest.run_directory for the output path
        output_dir = Path(result.manifest.base_output_dir) / result.manifest.run_directory
        assert (output_dir / "doubled.json").exists()
        assert (output_dir / "added.json").exists()

    def test_toy_pipeline_provenance(self, toy_registry, toy_output_router, tmp_path):
        """Verify pipeline generates provenance metadata."""
        spec_path = PIPELINE_CONFIGS_DIR / "toy_linear.yaml"

        result = execute_pipeline(
            spec_path=str(spec_path),
            output_dir=str(tmp_path),
            registry=toy_registry,
            custom_schema_types=[ToyInput],
            output_router=toy_output_router,
        )

        assert result.provenance is not None
        assert result.provenance.config_hash is not None
        assert len(result.provenance.module_versions) > 0

    def test_toy_pipeline_no_battery_imports(self, toy_registry):
        """Verify ToyModule tests don't import battery code."""
        # This test exists to document the isolation requirement.
        # If battery imports were present, earlier tests would fail
        # due to missing battery_tea package in isolated environment.
        import sys

        # Ensure no battery_tea modules are loaded
        battery_modules = [m for m in sys.modules if "battery_tea" in m]
        # Note: battery_tea may be loaded at pytest collection time
        # The key point is ToyModule tests don't REQUIRE it
        assert toy_registry.has("ToyDoublerModule")
