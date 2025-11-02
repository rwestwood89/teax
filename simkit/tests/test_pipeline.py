from __future__ import annotations

from pathlib import Path

from simkit.core.pipeline import execute_pipeline


def _spec_path() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "pipeline_configs" / "demo_linear_alt.yaml"


def test_execute_pipeline_end_to_end(tmp_path, geography_us_ca):
    output_dir = tmp_path / "outputs"
    result = execute_pipeline(_spec_path(), output_dir)

    manifest = result.manifest
    assert manifest is not None
    run_dir = Path(manifest.base_output_dir) / manifest.run_directory
    assert run_dir.exists()
    expected_files = {
        "rate_info.json",
        "battery_config.json",
        "cost_breakdown.json",
        "telemetry.parquet",
        "financial_results.json",
        "manifest.json",
    }
    assert {p.name for p in run_dir.iterdir()} >= expected_files
    outputs = result.outputs
    assert outputs["rate_info"].currency == geography_us_ca.currency
    assert len(outputs["telemetry"].charge_in_kwh) == 8760


def test_execute_pipeline_populates_provenance_metadata(tmp_path):
    output_dir = tmp_path / "outputs"
    result = execute_pipeline(_spec_path(), output_dir)

    assert result.pipeline_metadata.spec_path.endswith("demo_linear_alt.yaml")
    assert result.pipeline_metadata.run_description == "Demo linear pipeline for regression coverage"
    assert result.pipeline_metadata.output_folder == "pipeline_result_bundle"
    assert result.provenance.notes == "Demo linear pipeline for regression coverage"
    assert result.provenance.output_folder == "pipeline_result_bundle"
    assert "rate_data" in result.provenance.module_versions

    manifest = result.manifest
    assert manifest is not None
    assert manifest.run_name == "pipeline-result-bundle"
    assert manifest.metadata is not None
    assert manifest.metadata["output_folder"] == "pipeline_result_bundle"


def test_execute_pipeline_honors_output_dir_env(tmp_path, monkeypatch):
    base_output = tmp_path / "env-output"
    monkeypatch.setenv("PYRONDO_OUTPUT_DIR", str(base_output))

    result = execute_pipeline(_spec_path(), None)

    manifest = result.manifest
    assert manifest is not None
    assert Path(manifest.base_output_dir) == base_output.resolve()
