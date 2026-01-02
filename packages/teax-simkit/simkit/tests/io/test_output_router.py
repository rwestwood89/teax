from __future__ import annotations

import json
from pathlib import Path

import pytest
import pandas as pd

from simkit.config import battery_schema, schema
from simkit.config.pipeline_schema import ChannelSource, PipelineChannelBinding
from simkit.io.output_router import (
    OutputRouter,
    OutputRouterError,
    WriteHandler,
    create_default_router,
    create_output_router_with_json_schemas,
)
from simkit.io import writers
from simkit.io.readers import read_pipeline_spec
from simkit.tests import fixtures as fixture_builders


PIPELINE_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "pipeline_configs" / "demo_linear_alt.yaml"


@pytest.fixture
def exit_bindings():
    spec = read_pipeline_spec(PIPELINE_FIXTURE)
    return spec.modules["exit_point"].outputs


@pytest.fixture
def exit_payload() -> dict[str, schema.StrictBaseModel]:
    return fixture_builders.sample_exit_payload()


@pytest.fixture
def sync_outputs() -> battery_schema.SyncSimOutputs:
    return fixture_builders.sample_sync_outputs()


def test_output_router_writes_artifacts_and_manifest(tmp_path: Path, exit_bindings, exit_payload):
    router = create_default_router()
    metadata = fixture_builders.sample_pipeline_metadata()

    result = router.write_outputs(
        exit_bindings,
        exit_payload,
        base_output_dir=tmp_path,
        run_name="Demo Linear",
        pipeline_metadata=metadata,
    )

    assert result.run_dir.is_dir()
    assert result.manifest_path.exists()
    assert (result.run_dir / "telemetry.parquet").exists()
    assert result.run_dir.name.startswith("demo-linear-")

    manifest_data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    telemetry_record = next(item for item in manifest_data["artifacts"] if item["channel"] == "telemetry")
    assert telemetry_record["type_name"] == battery_schema.BatteryTelemetry8760.__name__
    assert telemetry_record["relative_path"] == "telemetry.parquet"
    assert telemetry_record["produced"] is True
    assert manifest_data["run_name"] == "demo-linear"
    assert manifest_data["metadata"]["output_folder"] == metadata["output_folder"]


def test_output_router_generates_unique_run_ids(tmp_path: Path, exit_bindings, exit_payload):
    router = create_default_router()

    first = router.write_outputs(exit_bindings, exit_payload, base_output_dir=tmp_path, run_name="demo")
    second = router.write_outputs(exit_bindings, exit_payload, base_output_dir=tmp_path, run_name="demo")

    assert first.run_dir != second.run_dir
    assert first.manifest.short_id != second.manifest.short_id


def test_output_router_requires_registered_writer(tmp_path: Path):
    bindings = {
        "unsupported": PipelineChannelBinding(
            type_name="UnsupportedType",
            channel_name="unsupported",
            source=ChannelSource.MODULE,
            destination_filename="unsupported.json",
        )
    }
    values = {"unsupported": fixture_builders.sample_rate_info()}
    router = OutputRouter(type_handlers={})

    with pytest.raises(OutputRouterError, match="No writer registered"):
        router.write_outputs(bindings, values, base_output_dir=tmp_path)


def test_output_router_rejects_duplicate_filenames(tmp_path: Path):
    router = create_default_router()
    bindings = {
        "first": PipelineChannelBinding(
            type_name=battery_schema.RateInfo.__name__,
            channel_name="first",
            source=ChannelSource.MODULE,
            destination_filename="duplicate.json",
        ),
        "second": PipelineChannelBinding(
            type_name=battery_schema.RateInfo.__name__,
            channel_name="second",
            source=ChannelSource.MODULE,
            destination_filename="duplicate.json",
        ),
    }
    values = {
        "first": fixture_builders.sample_rate_info(),
        "second": fixture_builders.sample_rate_info(),
    }

    with pytest.raises(OutputRouterError, match="Destination filename 'duplicate.json' declared more than once"):
        router.write_outputs(bindings, values, base_output_dir=tmp_path)


def test_output_router_extension_check(tmp_path: Path):
    router = OutputRouter(
        {battery_schema.RateInfo.__name__: WriteHandler(fn=writers.write_json_model, extension=".json")}
    )
    bindings = {
        "rate_info": PipelineChannelBinding(
            type_name=battery_schema.RateInfo.__name__,
            channel_name="rate_info",
            source=ChannelSource.MODULE,
            destination_filename="rate_info.txt",
        )
    }
    values = {"rate_info": fixture_builders.sample_rate_info()}

    with pytest.raises(OutputRouterError, match="does not match expected extension"):
        router.write_outputs(bindings, values, base_output_dir=tmp_path)


def test_output_router_records_missing_channel(tmp_path: Path):
    router = create_default_router()
    bindings = {
        "rate_info": PipelineChannelBinding(
            type_name=battery_schema.RateInfo.__name__,
            channel_name="rate_info",
            source=ChannelSource.MODULE,
            destination_filename="rate_info.json",
        )
    }

    result = router.write_outputs(bindings, {}, base_output_dir=tmp_path, run_name="demo")

    record = result.manifest.artifacts[0]
    assert record.channel == "rate_info"
    assert record.relative_path is None
    assert record.produced is False
    assert not (result.run_dir / "rate_info.json").exists()


def test_output_router_handles_synchronous_sim(tmp_path: Path, sync_outputs: battery_schema.SyncSimOutputs):
    router = create_default_router()
    bindings = {
        "forecasts": PipelineChannelBinding(
            type_name=schema.MockForecastSeries.__name__,
            channel_name="forecasts",
            source=ChannelSource.MODULE,
            destination_filename="forecasts.json",
        ),
        "guidances": PipelineChannelBinding(
            type_name=schema.SyncGuidanceSeries.__name__,
            channel_name="guidances",
            source=ChannelSource.MODULE,
            destination_filename="guidances.json",
        ),
        "telemetry": PipelineChannelBinding(
            type_name=battery_schema.SyncTelemetrySeries.__name__,
            channel_name="telemetry",
            source=ChannelSource.MODULE,
            destination_filename="telemetry.parquet",
        ),
    }
    values = {
        "forecasts": sync_outputs.forecasts,
        "guidances": sync_outputs.guidances,
        "telemetry": sync_outputs.telemetry,
    }

    result = router.write_outputs(bindings, values, base_output_dir=tmp_path, run_name="sync")

    run_files = {p.name for p in result.run_dir.iterdir()}
    assert {"forecasts.json", "guidances.json", "telemetry.parquet"} <= run_files

    telemetry = pd.read_parquet(result.run_dir / "telemetry.parquet")
    assert set(telemetry.columns) >= {"outer_index", "inner_timestamp", "soc_kwh"}

    recorded_types = {artifact.type_name for artifact in result.manifest.artifacts}
    assert schema.MockForecastSeries.__name__ in recorded_types
    assert schema.SyncGuidanceSeries.__name__ in recorded_types
    assert battery_schema.SyncTelemetrySeries.__name__ in recorded_types


def test_create_output_router_with_json_schemas_includes_builtins():
    """Test that custom JSON schemas include built-in handlers when requested."""
    router = create_output_router_with_json_schemas(
        ["CustomSchema1", "CustomSchema2"],
        include_builtins=True,
    )

    # Check custom schemas are registered
    assert router.has_handler("CustomSchema1")
    assert router.has_handler("CustomSchema2")

    # Check built-ins are still there
    assert router.has_handler("RateInfo")
    assert router.has_handler("BatteryConfig")
    assert router.has_handler("FinancialResults")


def test_create_output_router_with_json_schemas_custom_only():
    """Test that custom-only mode excludes built-in handlers."""
    router = create_output_router_with_json_schemas(
        ["CustomSchema1"],
        include_builtins=False,
    )

    # Check custom schema is registered
    assert router.has_handler("CustomSchema1")

    # Check built-ins are NOT there
    assert not router.has_handler("RateInfo")
    assert not router.has_handler("BatteryConfig")


def test_create_output_router_with_json_schemas_rejects_duplicates():
    """Test that duplicate schema types raise ValueError."""
    with pytest.raises(ValueError, match="Duplicate schema types"):
        create_output_router_with_json_schemas(
            ["CustomSchema1", "CustomSchema1", "CustomSchema2"]
        )


def test_output_router_in_memory_mode_validates_without_writing(tmp_path: Path):
    """Test that in-memory mode validates but doesn't write files."""
    router = create_output_router_with_json_schemas(
        ["CustomType"],
        in_memory=True,
    )

    bindings = {
        "custom": PipelineChannelBinding(
            type_name="CustomType",
            channel_name="custom",
            source=ChannelSource.MODULE,
            destination_filename="custom.json",
        )
    }
    values = {"custom": fixture_builders.sample_rate_info()}  # Any pydantic model will work

    result = router.write_outputs(
        bindings,
        values,
        run_name="test_run",
        pipeline_metadata={"foo": "bar"},
    )

    # Verify result has synthetic paths
    assert result.run_dir == Path("<in-memory>") / "test_run-mem"
    assert result.manifest.short_id == "mem"
    assert result.manifest.base_output_dir == "<in-memory>"
    assert result.manifest.run_name == "test_run"

    # Verify manifest has correct artifacts
    assert len(result.manifest.artifacts) == 1
    assert result.manifest.artifacts[0].channel == "custom"
    assert result.manifest.artifacts[0].type_name == "CustomType"
    assert result.manifest.artifacts[0].produced is True
    assert result.manifest.artifacts[0].relative_path == "custom.json"

    # Verify no files were written to disk
    assert not result.run_dir.exists()


def test_output_router_in_memory_still_validates():
    """Test that in-memory mode still performs validation checks."""
    router = create_output_router_with_json_schemas(
        ["CustomType"],
        in_memory=True,
    )

    # Missing handler should still fail
    bindings = {
        "unknown": PipelineChannelBinding(
            type_name="UnknownType",
            channel_name="unknown",
            source=ChannelSource.MODULE,
            destination_filename="unknown.json",
        )
    }
    values = {"unknown": fixture_builders.sample_rate_info()}

    with pytest.raises(OutputRouterError, match="No writer registered for type 'UnknownType'"):
        router.write_outputs(bindings, values, run_name="test")

    # Duplicate filenames should still fail
    bindings = {
        "first": PipelineChannelBinding(
            type_name="CustomType",
            channel_name="first",
            source=ChannelSource.MODULE,
            destination_filename="duplicate.json",
        ),
        "second": PipelineChannelBinding(
            type_name="CustomType",
            channel_name="second",
            source=ChannelSource.MODULE,
            destination_filename="duplicate.json",
        ),
    }
    values = {
        "first": fixture_builders.sample_rate_info(),
        "second": fixture_builders.sample_rate_info(),
    }

    with pytest.raises(OutputRouterError, match="Destination filename 'duplicate.json' declared more than once"):
        router.write_outputs(bindings, values, run_name="test")


def test_create_default_router_supports_in_memory():
    """Test that create_default_router accepts in_memory parameter."""
    router = create_default_router(in_memory=True)

    bindings = {
        "rate_info": PipelineChannelBinding(
            type_name="RateInfo",
            channel_name="rate_info",
            source=ChannelSource.MODULE,
            destination_filename="rate_info.json",
        )
    }
    values = {"rate_info": fixture_builders.sample_rate_info()}

    result = router.write_outputs(bindings, values, run_name="test")

    # Should succeed without writing files
    assert result.manifest.short_id == "mem"
    assert not result.run_dir.exists()
