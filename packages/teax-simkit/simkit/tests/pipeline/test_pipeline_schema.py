from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from simkit.io.readers import read_pipeline_spec
from simkit.config.pipeline_schema import ChannelSource, build_pipeline_spec


def _write_temp_config(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_read_pipeline_spec_success(sample_pipeline_yaml_path: Path):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)

    assert spec.source_path == sample_pipeline_yaml_path
    assert spec.metadata is not None
    assert spec.metadata.run_description == "Demo linear pipeline for regression coverage"
    assert spec.metadata.output_folder == "pipeline_result_bundle"

    entry = spec.modules["entry_point"]
    geo_binding = entry.outputs["geo"]
    assert geo_binding.channel_name == "geo"
    assert geo_binding.artifact_path == Path("../geography_us_ca_pge.json")
    assert geo_binding.source is ChannelSource.ENTRY

    perf_inputs = spec.modules["simple_performance_sim"].inputs
    assert perf_inputs["pv_profile"].is_default
    assert perf_inputs["battery"].channel_name == "battery_config"

    analyzer_inputs = spec.modules["project_analyzer"].inputs
    assert analyzer_inputs["financial_params"].channel_name == "financial_params"

    exit_module = spec.modules["exit_point"]
    assert not exit_module.inputs

    exit_outputs = exit_module.outputs
    assert set(exit_outputs.keys()) == {
        "rate_info",
        "battery_config",
        "cost_breakdown",
        "telemetry",
        "financial_results",
    }
    assert exit_outputs["rate_info"].destination_filename == "rate_info.json"
    assert exit_outputs["battery_config"].destination_filename == "battery_config.json"
    assert exit_outputs["cost_breakdown"].destination_filename == "cost_breakdown.json"
    assert exit_outputs["telemetry"].destination_filename == "telemetry.parquet"
    assert exit_outputs["financial_results"].destination_filename == "financial_results.json"


def test_exit_point_outputs_parse_with_filenames(sample_pipeline_spec: dict) -> None:
    spec = build_pipeline_spec(sample_pipeline_spec)
    exit_outputs = spec.modules["exit_point"].outputs

    rate_binding = exit_outputs["rate_info"]
    assert rate_binding.type_name == "RateInfo"
    assert rate_binding.channel_name == "rate_info"
    assert rate_binding.destination_filename == "rate_info.json"

    telemetry_binding = exit_outputs["telemetry"]
    assert telemetry_binding.type_name == "BatteryTelemetry8760"
    assert telemetry_binding.channel_name == "telemetry"
    assert telemetry_binding.destination_filename == "telemetry.parquet"


def test_exit_point_outputs_require_unique_filenames(sample_pipeline_spec: dict, tmp_path: Path) -> None:
    broken_spec = deepcopy(sample_pipeline_spec)
    exit_outputs = broken_spec["modules"]["exit_point"]["outputs"]
    exit_outputs["duplicate"] = "BatteryTelemetry8760 telemetry.parquet"

    path = _write_temp_config(tmp_path, broken_spec)

    with pytest.raises(ValueError, match="duplicate destination filename"):
        read_pipeline_spec(path)


def test_exit_point_outputs_require_filename(sample_pipeline_spec: dict, tmp_path: Path) -> None:
    broken_spec = deepcopy(sample_pipeline_spec)
    broken_spec["modules"]["exit_point"]["outputs"]["telemetry"] = "BatteryTelemetry8760"

    path = _write_temp_config(tmp_path, broken_spec)

    with pytest.raises(ValueError, match="'<Type> <filename>'"):
        read_pipeline_spec(path)


def test_exit_point_outputs_require_known_channel(sample_pipeline_spec: dict, tmp_path: Path) -> None:
    broken_spec = deepcopy(sample_pipeline_spec)
    broken_spec["modules"]["exit_point"]["outputs"]["unknown"] = "RateInfo unknown.json"

    path = _write_temp_config(tmp_path, broken_spec)

    with pytest.raises(ValueError, match="references unknown channel"):
        read_pipeline_spec(path)


def test_read_pipeline_spec_requires_entry_and_exit(sample_pipeline_spec: dict, tmp_path: Path):
    broken_spec = deepcopy(sample_pipeline_spec)
    broken_spec["modules"].pop("entry_point")
    path = _write_temp_config(tmp_path, broken_spec)

    with pytest.raises(ValueError, match="EntryPoint"):
        read_pipeline_spec(path)


def test_read_pipeline_spec_rejects_unknown_channel(sample_pipeline_spec: dict, tmp_path: Path):
    broken_spec = deepcopy(sample_pipeline_spec)
    broken_spec["modules"]["project_analyzer"]["inputs"]["rate_info"] = "RateInfo missing_rate"
    path = _write_temp_config(tmp_path, broken_spec)

    with pytest.raises(ValueError, match="missing_rate"):
        read_pipeline_spec(path)


def test_read_pipeline_spec_rejects_duplicate_output(sample_pipeline_spec: dict, tmp_path: Path):
    broken_spec = deepcopy(sample_pipeline_spec)
    broken_spec["modules"]["cost_calculator"]["outputs"]["duplicate"] = "CostBreakdown cost_breakdown"
    path = _write_temp_config(tmp_path, broken_spec)

    with pytest.raises(ValueError, match="cost_calculator"):
        read_pipeline_spec(path)


def test_read_pipeline_spec_allows_missing_metadata(sample_pipeline_spec: dict, tmp_path: Path):
    spec_without_metadata = deepcopy(sample_pipeline_spec)
    spec_without_metadata.pop("metadata", None)
    path = _write_temp_config(tmp_path, spec_without_metadata)

    spec = read_pipeline_spec(path)

    assert spec.metadata is None


def test_read_pipeline_spec_rejects_unknown_metadata(sample_pipeline_spec: dict, tmp_path: Path):
    broken_spec = deepcopy(sample_pipeline_spec)
    broken_spec.setdefault("metadata", {})["unexpected"] = "value"
    path = _write_temp_config(tmp_path, broken_spec)

    with pytest.raises(ValidationError, match="unexpected"):
        read_pipeline_spec(path)


def test_read_pipeline_spec_rejects_empty_output_folder(sample_pipeline_spec: dict, tmp_path: Path):
    broken_spec = deepcopy(sample_pipeline_spec)
    broken_spec.setdefault("metadata", {})["output_folder"] = "   "
    path = _write_temp_config(tmp_path, broken_spec)

    with pytest.raises(ValidationError, match="output_folder"):
        read_pipeline_spec(path)
