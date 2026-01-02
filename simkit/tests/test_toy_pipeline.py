"""End-to-end tests for generic framework using toy modules.

These tests exercise the pipeline framework without any battery dependencies,
providing battery-free test coverage that can be run after separating
the battery code into a separate package.
"""
from pathlib import Path

from pydantic import RootModel

from simkit.core.pipeline import execute_pipeline
from simkit.core.registry_builder import create_registry
from simkit.io.output_router import create_output_router_with_json_schemas

from .core.toy_modules import (
    ToyAdderModule,
    ToyDoublerModule,
    ToyInput,
    ToyMultiOutputModule,
    ToyOutput,
)


def _toy_spec_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "fixtures"
        / "pipeline_configs"
        / "toy_linear.yaml"
    )


def test_toy_pipeline_executes_two_modules(tmp_path):
    """E2E test: ToyModule pipeline without any battery dependencies."""
    registry = create_registry([ToyDoublerModule, ToyAdderModule])
    output_router = create_output_router_with_json_schemas(
        ["ToyInput", "RootModel[float]"],
        include_builtins=False,
    )

    result = execute_pipeline(
        str(_toy_spec_path()),
        output_dir=str(tmp_path / "outputs"),
        registry=registry,
        custom_schema_types=[ToyInput],
        output_router=output_router,
    )

    # Verify pipeline succeeded
    assert result.provenance is not None

    # Verify channel values are correct (outputs are RootModel[float])
    # Input: 10.0
    # After doubler: 10.0 * 2.0 = 20.0
    # After adder: 20.0 + 22.0 = 42.0
    assert "doubled" in result.outputs
    assert "added" in result.outputs
    assert result.outputs["doubled"].root == 20.0
    assert result.outputs["added"].root == 42.0


def test_toy_pipeline_in_memory_mode():
    """Test that toy pipeline works in in-memory mode without file output."""
    registry = create_registry([ToyDoublerModule, ToyAdderModule])
    output_router = create_output_router_with_json_schemas(
        ["ToyInput", "RootModel[float]"],
        include_builtins=False,
        in_memory=True,
    )

    result = execute_pipeline(
        str(_toy_spec_path()),
        output_router=output_router,
        registry=registry,
        custom_schema_types=[ToyInput],
    )

    # Verify pipeline succeeded
    assert result.provenance is not None

    # Verify in-memory mode
    assert result.manifest is not None
    assert result.manifest.base_output_dir == "<in-memory>"

    # Verify outputs are accessible (RootModel[float])
    assert "doubled" in result.outputs
    assert "added" in result.outputs
    assert isinstance(result.outputs["doubled"], RootModel)
    assert isinstance(result.outputs["added"], RootModel)
    assert result.outputs["doubled"].root == 20.0
    assert result.outputs["added"].root == 42.0


def test_toy_pipeline_with_file_output(tmp_path):
    """Test that toy pipeline writes output files correctly."""
    registry = create_registry([ToyDoublerModule, ToyAdderModule])
    output_router = create_output_router_with_json_schemas(
        ["ToyInput", "RootModel[float]"],
        include_builtins=False,
    )

    output_dir = tmp_path / "outputs"
    result = execute_pipeline(
        str(_toy_spec_path()),
        output_dir=str(output_dir),
        registry=registry,
        custom_schema_types=[ToyInput],
        output_router=output_router,
    )

    # Verify pipeline succeeded and files were written
    assert result.manifest is not None
    run_dir = Path(result.manifest.base_output_dir) / result.manifest.run_directory
    assert run_dir.exists()

    # Verify expected output files exist
    expected_files = {"doubled.json", "added.json", "manifest.json"}
    actual_files = {p.name for p in run_dir.iterdir()}
    assert expected_files <= actual_files


def test_toy_pipeline_provenance_tracking():
    """Test that toy pipeline tracks provenance correctly."""
    registry = create_registry([ToyDoublerModule, ToyAdderModule])
    output_router = create_output_router_with_json_schemas(
        ["ToyInput", "RootModel[float]"],
        include_builtins=False,
        in_memory=True,
    )

    result = execute_pipeline(
        str(_toy_spec_path()),
        output_router=output_router,
        registry=registry,
        custom_schema_types=[ToyInput],
    )

    # Verify provenance metadata
    assert result.provenance is not None
    assert result.provenance.config_hash is not None
    assert "doubler" in result.provenance.module_versions
    assert "adder" in result.provenance.module_versions

    # Verify pipeline metadata
    assert result.pipeline_metadata is not None
    assert result.pipeline_metadata.run_description == (
        "Generic framework test pipeline without battery dependencies"
    )


def test_toy_module_registry_has_no_battery_imports():
    """Test that ToyModule-based registry has no battery module dependencies."""
    registry = create_registry([ToyDoublerModule, ToyAdderModule])

    # Should have ToyDoublerModule and ToyAdderModule
    # (EntryPoint and ExitPoint are handled specially by executor, not in registry)
    assert registry.has("ToyDoublerModule")
    assert registry.has("ToyAdderModule")

    # Should NOT have battery modules
    assert not registry.has("RateData")
    assert not registry.has("ConfigureBattery")
    assert not registry.has("CostCalculator")
    assert not registry.has("SimplePerformanceSim")
    assert not registry.has("ProjectAnalyzer")
    assert not registry.has("SynchronousSim")


def test_toy_multi_output_module_registration():
    """Test that ToyMultiOutputModule registers correctly for multi-output testing."""
    registry = create_registry([ToyMultiOutputModule])

    assert registry.has("ToyMultiOutputModule")
    descriptor = registry.get("ToyMultiOutputModule")

    # Verify inputs
    assert "value" in descriptor.required_inputs
    assert descriptor.required_inputs["value"] == float

    # Verify outputs (from MultiOutput fields)
    assert "doubled" in descriptor.outputs
    assert "tripled" in descriptor.outputs
    assert descriptor.outputs["doubled"] == ToyOutput
    assert descriptor.outputs["tripled"] == ToyOutput


def test_toy_multi_output_module_execution():
    """Test that ToyMultiOutputModule produces correct multiple outputs."""
    module = ToyMultiOutputModule()

    result = module.run(value=10.0)

    assert result.data.doubled.value == 20.0  # 10 * 2
    assert result.data.tripled.value == 30.0  # 10 * 3
