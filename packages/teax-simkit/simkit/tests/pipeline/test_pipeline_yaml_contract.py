from __future__ import annotations

from pathlib import Path
import re

import yaml

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "pipeline_configs" / "demo_linear_alt.yaml"

# The contract locks the linear module order matching today's async pipeline.
_EXPECTED_MODULE_ORDER = [
    "entry_point",
    "rate_data",
    "configure_battery",
    "simple_performance_sim",
    "cost_calculator",
    "project_analyzer",
    "exit_point",
]

_CHANNEL_PATTERN = re.compile(r"^(?P<class>[A-Za-z0-9_]+)\s+(?P<name>[a-z0-9_]+)$")
_NONE_PATTERN = re.compile(r"^None\s*->\s*(?P<name>[a-z0-9_]+)$")
_EXIT_OUTPUT_PATTERN = re.compile(r"^(?P<class>[A-Za-z0-9_]+)\s+(?P<filename>[A-Za-z0-9_.-]+)$")


def _assert_standard_channel(value: str) -> None:
    match = _CHANNEL_PATTERN.match(value.strip())
    assert match is not None, f"Expected '<Class> <name>' string, got: {value!r}"


def _assert_optional_channel(value: str) -> None:
    match = _NONE_PATTERN.match(value.strip())
    assert match is not None, f"Expected 'None -> <name>' sentinel, got: {value!r}"


def _assert_exit_output(value: str) -> None:
    match = _EXIT_OUTPUT_PATTERN.match(value.strip())
    assert match is not None, f"Expected '<Class> <filename>' string, got: {value!r}"
    filename = match.group("filename")
    assert "/" not in filename and "\\" not in filename, f"Filename must not include directories: {filename!r}"


def test_demo_linear_yaml_structure(sample_pipeline_yaml_path):
    spec = yaml.safe_load(sample_pipeline_yaml_path.read_text(encoding="utf-8"))
    assert spec is not None, "Fixture should deserialize into a mapping"
    assert set(spec.keys()) == {"metadata", "modules"}, (
        "Fixture must only define metadata and modules; edges are inferred via channel names"
    )

    metadata = spec["metadata"]
    assert metadata == {
        "run_description": "Demo linear pipeline for regression coverage",
        "output_folder": "pipeline_result_bundle",
    }, "Metadata block should expose run_description and output_folder"

    modules = spec["modules"]
    assert list(modules.keys()) == _EXPECTED_MODULE_ORDER, "Module keys must preserve the documented execution order"

    entry_spec = modules["entry_point"]
    assert set(entry_spec.keys()) >= {"module_type", "inputs"}
    for class_and_path in entry_spec["inputs"].values():
        parts = class_and_path.split(" ", 1)
        assert len(parts) == 2, f"Entry inputs must use '<name>: <Class> <path>' format, got {class_and_path!r}"
        class_name, path = parts
        assert class_name[0].isupper(), f"Entry input class must be TitleCase, got {class_name!r}"
        assert path, "Entry input path should not be empty"
    if "outputs" in entry_spec:
        for channel in entry_spec["outputs"].values():
            _assert_standard_channel(channel)

    for key in _EXPECTED_MODULE_ORDER[1:-1]:  # skip entry and exit for targeted assertions
        module_spec = modules[key]
        assert isinstance(module_spec["module_type"], str) and module_spec["module_type"], (
            f"module_type must be a non-empty string for module {key}"
        )
        for channel in module_spec.get("inputs", {}).values():
            normalized = channel.strip()
            if normalized.startswith("None"):
                _assert_optional_channel(normalized)
            else:
                _assert_standard_channel(normalized)
        for channel in module_spec.get("outputs", {}).values():
            _assert_standard_channel(channel)

    exit_spec = modules["exit_point"]
    assert set(exit_spec.keys()) >= {"module_type", "outputs"}
    assert exit_spec.get("inputs", {}) == {}, "ExitPoint should not declare inputs explicitly"
    expected_outputs = {
        "rate_info": "RateInfo rate_info.json",
        "battery_config": "BatteryConfig battery_config.json",
        "cost_breakdown": "CostBreakdown cost_breakdown.json",
        "telemetry": "BatteryTelemetry8760 telemetry.parquet",
        "financial_results": "FinancialResults financial_results.json",
    }
    assert exit_spec["outputs"] == expected_outputs, "ExitPoint outputs must enumerate upstream channels with filenames"
    for value in exit_spec["outputs"].values():
        _assert_exit_output(value)


def test_fixture_constant_location(sample_pipeline_yaml_path):
    assert sample_pipeline_yaml_path == FIXTURE
    assert sample_pipeline_yaml_path.exists(), "Expected pipeline YAML fixture to exist"
