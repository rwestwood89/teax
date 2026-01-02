from __future__ import annotations

from pathlib import Path

from simkit.config import battery_schema
from simkit.core.pipeline import execute_pipeline
from simkit.io.output_router import create_default_router


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


def test_execute_pipeline_in_memory_mode(geography_us_ca):
    """Test that in-memory mode provides data in result.outputs but doesn't write files."""
    # Create router with in_memory=True
    router = create_default_router(in_memory=True)

    # Execute pipeline with in-memory router
    result = execute_pipeline(_spec_path(), output_router=router)

    # (a) Verify no files were written to disk
    assert result.manifest is not None
    assert result.manifest.base_output_dir == "<in-memory>"
    assert result.manifest.short_id == "mem"

    # Verify the synthetic run directory doesn't exist on disk
    synthetic_run_dir = Path(result.manifest.base_output_dir) / result.manifest.run_directory
    assert not synthetic_run_dir.exists()

    # (b) Validate that actual result output models are accessible and correct
    outputs = result.outputs

    # Verify all expected outputs are present
    assert "rate_info" in outputs
    assert "battery_config" in outputs
    assert "cost_breakdown" in outputs
    assert "telemetry" in outputs
    assert "financial_results" in outputs

    # Validate that outputs are real Pydantic model instances with actual data
    rate_info = outputs["rate_info"]
    assert isinstance(rate_info, battery_schema.RateInfo)
    assert rate_info.currency == geography_us_ca.currency
    assert len(rate_info.energy_price_usd_per_kwh) == 8760

    battery_config = outputs["battery_config"]
    assert isinstance(battery_config, battery_schema.BatteryConfig)
    assert battery_config.capacity_kwh > 0

    cost_breakdown = outputs["cost_breakdown"]
    assert isinstance(cost_breakdown, battery_schema.CostBreakdown)
    assert cost_breakdown.currency == "USD"

    telemetry = outputs["telemetry"]
    assert isinstance(telemetry, battery_schema.BatteryTelemetry8760)
    assert len(telemetry.soc_kwh) == 8760

    financial_results = outputs["financial_results"]
    # FinancialResults is a generic type
    from simkit.config import schema
    assert isinstance(financial_results, schema.FinancialResults)
    assert financial_results.currency == "USD"

    # Verify manifest recorded artifacts correctly
    assert len(result.manifest.artifacts) == 5
    for artifact in result.manifest.artifacts:
        assert artifact.produced is True
        assert artifact.type_name in [
            "RateInfo",
            "BatteryConfig",
            "CostBreakdown",
            "BatteryTelemetry8760",
            "FinancialResults",
        ]
        assert artifact.relative_path is not None  # Even in-memory mode records the "would-be" paths

    # Verify provenance is still populated
    assert result.provenance is not None
    assert result.provenance.config_hash is not None
    assert "rate_data" in result.provenance.module_versions
