"""Verification tests that core framework has no battery dependencies.

These tests ensure Phase 5 (Clean Core Framework) is complete - the teax-simkit
package should have zero references to battery-specific code.
"""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_core_init_has_no_battery_exports():
    """Verify simkit.core doesn't export battery modules."""
    from simkit import core

    # Battery modules should NOT be present
    assert not hasattr(core, "ConfigureBatteryModule")
    assert not hasattr(core, "CostCalculatorModule")
    assert not hasattr(core, "SimplePerformanceSimModule")
    assert not hasattr(core, "ProjectAnalyzerModule")
    assert not hasattr(core, "RateDataModule")
    assert not hasattr(core, "SynchronousSimModule")

    # Framework exports should exist
    assert hasattr(core, "ModuleBase")
    assert hasattr(core, "ModuleResult")
    assert hasattr(core, "PipelineModuleRegistry")
    assert hasattr(core, "ModuleDescriptor")
    assert hasattr(core, "create_registry")
    assert hasattr(core, "introspect_module")


def test_schema_has_no_battery_types():
    """Verify simkit.config.schema has no battery types."""
    from simkit.config import schema

    # Battery-specific types should NOT be present
    assert not hasattr(schema, "BatteryConfig")
    assert not hasattr(schema, "BatteryState")
    assert not hasattr(schema, "BatteryTelemetry8760")
    assert not hasattr(schema, "Geography")
    assert not hasattr(schema, "LoadProfile8760")
    assert not hasattr(schema, "RateInfo")
    assert not hasattr(schema, "CostBreakdown")

    # Generic types should exist
    assert hasattr(schema, "StrictBaseModel")
    assert hasattr(schema, "MultiOutput")
    assert hasattr(schema, "PriceTrajectory")
    assert hasattr(schema, "FinancialParams")
    assert hasattr(schema, "FinancialResults")


def test_registry_has_no_from_static_modules():
    """Verify from_static_modules() is removed."""
    from simkit.core.pipeline_registry import PipelineModuleRegistry

    assert not hasattr(PipelineModuleRegistry, "from_static_modules")


def test_no_battery_schema_file():
    """Verify battery_schema.py does not exist in teax-simkit."""
    import importlib.util

    spec = importlib.util.find_spec("simkit.config.battery_schema")
    assert spec is None, "battery_schema.py should not exist in teax-simkit"


def test_no_battery_imports_in_framework():
    """Verify no battery_schema imports in framework code (excluding test files)."""
    result = subprocess.run(
        ["grep", "-r", "--include=*.py", "--exclude-dir=tests", "battery_schema", "packages/teax-simkit/simkit/"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    # Should find nothing (empty stdout) - grep returns 1 when no matches
    assert result.stdout == "", f"Found battery_schema imports:\n{result.stdout}"


def test_no_battery_config_imports():
    """Verify no BatteryConfig references in framework code (excluding tests)."""
    result = subprocess.run(
        ["grep", "-r", "--include=*.py", "--exclude-dir=tests", "BatteryConfig", "packages/teax-simkit/simkit/"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.stdout == "", f"Found BatteryConfig references:\n{result.stdout}"


def test_no_load_profile_imports():
    """Verify no LoadProfile8760 references in framework code (excluding tests)."""
    result = subprocess.run(
        ["grep", "-r", "--include=*.py", "--exclude-dir=tests", "LoadProfile8760", "packages/teax-simkit/simkit/"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.stdout == "", f"Found LoadProfile8760 references:\n{result.stdout}"


def test_no_geography_imports():
    """Verify no Geography references in framework code (excluding tests)."""
    result = subprocess.run(
        ["grep", "-r", "--include=*.py", "--exclude-dir=tests", "Geography", "packages/teax-simkit/simkit/"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    # Filter out any false positives from comments or docs
    lines = [line for line in result.stdout.split("\n") if line and not line.strip().startswith("#")]
    assert len(lines) == 0, f"Found Geography references:\n{result.stdout}"


def test_defaults_has_no_battery_defaults():
    """Verify defaults.py has no battery-specific defaults."""
    from simkit.config import defaults

    # Battery defaults should NOT be present
    assert not hasattr(defaults, "DEFAULT_ROUNDTRIP_EFFICIENCY")
    assert not hasattr(defaults, "DEFAULT_SOC_MIN")
    assert not hasattr(defaults, "DEFAULT_SOC_MAX")
    assert not hasattr(defaults, "DEFAULT_BATTERY_NOTES")
    assert not hasattr(defaults, "default_design_prefs")

    # Generic defaults should exist
    assert hasattr(defaults, "DEFAULT_DISCOUNT_RATE")
    assert hasattr(defaults, "DEFAULT_ANALYSIS_YEARS")
    assert hasattr(defaults, "default_financial_params")
    assert hasattr(defaults, "default_time_index")


def test_readers_has_no_battery_readers():
    """Verify readers.py has no battery-specific readers."""
    from simkit.io import readers

    # Battery readers should NOT be present
    assert not hasattr(readers, "read_parquet_load_profile")
    assert not hasattr(readers, "read_parquet_pv_profile")

    # Generic readers should exist
    assert hasattr(readers, "read_json_model")
    assert hasattr(readers, "read_yaml_config")
    assert hasattr(readers, "read_pipeline_spec")


def test_writers_has_no_battery_writers():
    """Verify writers.py has no battery-specific writers."""
    from simkit.io import writers

    # Battery writers should NOT be present
    assert not hasattr(writers, "write_parquet_telemetry")
    assert not hasattr(writers, "write_sync_telemetry_series")
    assert not hasattr(writers, "_telemetry_frames_to_dataframe")

    # Generic writers should exist
    assert hasattr(writers, "write_json_model")
    assert hasattr(writers, "write_json_payload")
    assert hasattr(writers, "write_provenance")
