from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from simkit.core.pipeline import execute_pipeline

_SPEC_PATH = Path(__file__).resolve().parent / "fixtures" / "pipeline_configs" / "synchronous_sim_stubbed.yaml"


def test_synchronous_sim_stubbed_happy_path(tmp_path, geography_us_ca):
    output_dir = tmp_path / "outputs"
    result = execute_pipeline(_SPEC_PATH, output_dir)

    forecasts = result.outputs["forecasts"]
    guidances = result.outputs["guidances"]
    telemetry = result.outputs["telemetry"]

    first_frame = telemetry.frames[0]
    assert first_frame.inner_times[0].tzinfo is not None
    assert guidances.series[0].setpoint_kw == 0.0
    assert forecasts.series[0].metadata.currency == geography_us_ca.currency

    manifest = result.manifest
    assert manifest is not None
    expected_files = {"forecasts.json", "guidances.json", "telemetry.parquet", "manifest.json"}
    run_dir = Path(manifest.base_output_dir) / manifest.run_directory
    assert expected_files <= {p.name for p in run_dir.iterdir()}


def test_synchronous_sim_stubbed_failure_annotation(tmp_path):
    fixture_root = Path(__file__).resolve().parent / "fixtures"
    pipeline_dir = tmp_path / "fixtures" / "pipeline_configs"
    pipeline_dir.mkdir(parents=True)
    shutil.copytree(fixture_root / "synchronous_sim", tmp_path / "fixtures" / "synchronous_sim")

    failure_spec = pipeline_dir / "synchronous_sim_stubbed_failure.yaml"
    spec_text = _SPEC_PATH.read_text(encoding="utf-8")
    failure_spec.write_text(
        spec_text.replace("dynamic_sim_config.json", "dynamic_sim_config_failure.json"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as error:
        execute_pipeline(failure_spec, tmp_path / "outputs")

    assert "[component=dynamics]" in str(error.value)
