"""Tests for the output router."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import RootModel

from simkit.config import schema
from simkit.config.pipeline_schema import ChannelSource, PipelineChannelBinding
from simkit.io.output_router import (
    OutputRouter,
    OutputRouterError,
    WriteHandler,
    create_default_router,
    create_output_router_with_json_schemas,
)
from simkit.io import writers
from simkit.tests import fixtures as fixture_builders

SCALAR_OUTPUT_CASES = (
    ("float", 1.25, "1.25"),
    ("int", 2, "2"),
    ("str", "value", '"value"'),
    ("bool", True, "true"),
    ("RootModel[float]", RootModel[float](1.25), "1.25"),
    ("RootModel[int]", RootModel[int](2), "2"),
    ("RootModel[str]", RootModel[str]("value"), '"value"'),
    ("RootModel[bool]", RootModel[bool](True), "true"),
)


@pytest.mark.parametrize(
    ("scalar_type", "expected_name"),
    (
        (float, "RootModel[float]"),
        (int, "RootModel[int]"),
        (str, "RootModel[str]"),
        (bool, "RootModel[bool]"),
    ),
)
def test_scalar_root_model_names_are_stable(
    scalar_type: type,
    expected_name: str,
):
    assert RootModel[scalar_type].__name__ == expected_name


def test_output_router_writes_artifacts_and_manifest(tmp_path: Path):
    """Test that output router writes artifacts and manifest correctly."""
    router = create_default_router()
    metadata = fixture_builders.sample_pipeline_metadata()

    bindings = {
        "results": PipelineChannelBinding(
            type_name=schema.FinancialResults.__name__,
            channel_name="results",
            source=ChannelSource.MODULE,
            destination_filename="results.json",
        )
    }
    values = {
        "results": fixture_builders.sample_financial_results(),
    }

    result = router.write_outputs(
        bindings,
        values,
        base_output_dir=tmp_path,
        run_name="Test Run",
        pipeline_metadata=metadata,
    )

    assert result.run_dir.is_dir()
    assert result.manifest_path.exists()
    assert (result.run_dir / "results.json").exists()
    assert result.run_dir.name.startswith("test-run-")

    manifest_data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    results_record = next(
        item for item in manifest_data["artifacts"] if item["channel"] == "results"
    )
    assert results_record["type_name"] == schema.FinancialResults.__name__
    assert results_record["relative_path"] == "results.json"
    assert results_record["produced"] is True
    assert manifest_data["run_name"] == "test-run"
    assert manifest_data["metadata"]["output_folder"] == metadata["output_folder"]


def test_output_router_generates_unique_run_ids(tmp_path: Path):
    """Test that output router generates unique run IDs."""
    router = create_default_router()

    bindings = {
        "results": PipelineChannelBinding(
            type_name=schema.FinancialResults.__name__,
            channel_name="results",
            source=ChannelSource.MODULE,
            destination_filename="results.json",
        )
    }
    values = {"results": fixture_builders.sample_financial_results()}

    first = router.write_outputs(
        bindings, values, base_output_dir=tmp_path, run_name="demo"
    )
    second = router.write_outputs(
        bindings, values, base_output_dir=tmp_path, run_name="demo"
    )

    assert first.run_dir != second.run_dir
    assert first.manifest.short_id != second.manifest.short_id


def test_output_router_requires_registered_writer(tmp_path: Path):
    """Test that output router requires registered writers."""
    bindings = {
        "unsupported": PipelineChannelBinding(
            type_name="UnsupportedType",
            channel_name="unsupported",
            source=ChannelSource.MODULE,
            destination_filename="unsupported.json",
        )
    }
    values = {"unsupported": fixture_builders.sample_financial_results()}
    router = OutputRouter(type_handlers={})

    with pytest.raises(OutputRouterError, match="No writer registered"):
        router.write_outputs(bindings, values, base_output_dir=tmp_path)


def test_output_router_rejects_duplicate_filenames(tmp_path: Path):
    """Test that output router rejects duplicate filenames."""
    router = create_default_router()
    bindings = {
        "first": PipelineChannelBinding(
            type_name=schema.FinancialResults.__name__,
            channel_name="first",
            source=ChannelSource.MODULE,
            destination_filename="duplicate.json",
        ),
        "second": PipelineChannelBinding(
            type_name=schema.FinancialResults.__name__,
            channel_name="second",
            source=ChannelSource.MODULE,
            destination_filename="duplicate.json",
        ),
    }
    values = {
        "first": fixture_builders.sample_financial_results(),
        "second": fixture_builders.sample_financial_results(),
    }

    with pytest.raises(
        OutputRouterError,
        match="Destination filename 'duplicate.json' declared more than once",
    ):
        router.write_outputs(bindings, values, base_output_dir=tmp_path)


def test_output_router_extension_check(tmp_path: Path):
    """Test that output router validates file extensions."""
    router = OutputRouter(
        {
            schema.FinancialResults.__name__: WriteHandler(
                fn=writers.write_json_model, extension=".json"
            )
        }
    )
    bindings = {
        "results": PipelineChannelBinding(
            type_name=schema.FinancialResults.__name__,
            channel_name="results",
            source=ChannelSource.MODULE,
            destination_filename="results.txt",
        )
    }
    values = {"results": fixture_builders.sample_financial_results()}

    with pytest.raises(OutputRouterError, match="does not match expected extension"):
        router.write_outputs(bindings, values, base_output_dir=tmp_path)


def test_output_router_records_missing_channel(tmp_path: Path):
    """Test that output router records missing channels correctly."""
    router = create_default_router()
    bindings = {
        "results": PipelineChannelBinding(
            type_name=schema.FinancialResults.__name__,
            channel_name="results",
            source=ChannelSource.MODULE,
            destination_filename="results.json",
        )
    }

    result = router.write_outputs(
        bindings, {}, base_output_dir=tmp_path, run_name="demo"
    )

    record = result.manifest.artifacts[0]
    assert record.channel == "results"
    assert record.relative_path is None
    assert record.produced is False
    assert not (result.run_dir / "results.json").exists()


def test_output_router_handles_forecast_and_guidance_series(tmp_path: Path):
    """Test that output router handles forecast and guidance series correctly."""
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
    }
    values = {
        "forecasts": fixture_builders.sample_mock_forecast_series(),
        "guidances": fixture_builders.sample_sync_guidance_series(),
    }

    result = router.write_outputs(
        bindings, values, base_output_dir=tmp_path, run_name="sync"
    )

    run_files = {p.name for p in result.run_dir.iterdir()}
    assert {"forecasts.json", "guidances.json"} <= run_files

    recorded_types = {artifact.type_name for artifact in result.manifest.artifacts}
    assert schema.MockForecastSeries.__name__ in recorded_types
    assert schema.SyncGuidanceSeries.__name__ in recorded_types


def test_default_router_writes_all_scalar_shapes_as_natural_json(tmp_path: Path):
    router = create_default_router()
    bindings = {}
    values = {}

    for index, (type_name, value, _) in enumerate(SCALAR_OUTPUT_CASES):
        alias = f"scalar_{index}"
        bindings[alias] = PipelineChannelBinding(
            type_name=type_name,
            channel_name=alias,
            source=ChannelSource.MODULE,
            destination_filename=f"{alias}.json",
        )
        values[alias] = value

    result = router.write_outputs(
        bindings,
        values,
        base_output_dir=tmp_path,
        run_name="scalars",
    )

    for index, (_, _, expected_json) in enumerate(SCALAR_OUTPUT_CASES):
        assert (result.run_dir / f"scalar_{index}.json").read_text() == expected_json

    for bare_index, wrapped_index in zip(range(4), range(4, 8)):
        assert (result.run_dir / f"scalar_{bare_index}.json").read_bytes() == (
            result.run_dir / f"scalar_{wrapped_index}.json"
        ).read_bytes()


@pytest.mark.parametrize(
    ("type_name", "value"),
    [(type_name, value) for type_name, value, _ in SCALAR_OUTPUT_CASES],
)
def test_default_scalar_handlers_require_json_extension(
    tmp_path: Path,
    type_name: str,
    value: object,
):
    router = create_default_router()
    bindings = {
        "value": PipelineChannelBinding(
            type_name=type_name,
            channel_name="value",
            source=ChannelSource.MODULE,
            destination_filename="value.txt",
        )
    }

    with pytest.raises(OutputRouterError, match="expected extension '.json'"):
        router.write_outputs(bindings, {"value": value}, base_output_dir=tmp_path)


@pytest.mark.parametrize(
    ("type_name", "value", "expected_json"),
    (
        ("float", 0.0, "0.0"),
        ("int", 0, "0"),
        ("str", "", '""'),
        ("bool", False, "false"),
    ),
)
def test_default_router_persists_falsy_scalars(
    tmp_path: Path,
    type_name: str,
    value: object,
    expected_json: str,
):
    router = create_default_router()
    bindings = {
        "value": PipelineChannelBinding(
            type_name=type_name,
            channel_name="value",
            source=ChannelSource.MODULE,
            destination_filename="value.json",
        )
    }

    result = router.write_outputs(
        bindings,
        {"value": value},
        base_output_dir=tmp_path,
        run_name="falsy",
    )

    assert (result.run_dir / "value.json").read_text() == expected_json
    assert result.manifest.artifacts[0].produced is True
    assert result.manifest.artifacts[0].relative_path == "value.json"


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
    assert router.has_handler("FinancialResults")


def test_custom_schema_convenience_registration_preserves_default_handlers():
    router = create_output_router_with_json_schemas(
        ["float", "RootModel[float]", "MockForecastSeries"],
        include_builtins=True,
    )

    assert router._type_handlers["float"].fn is writers.write_json_payload
    assert router._type_handlers["RootModel[float]"].fn is writers.write_json_model
    assert (
        router._type_handlers["MockForecastSeries"].fn
        is writers.write_mock_forecast_series
    )


def test_register_handler_remains_a_deliberate_override():
    router = create_default_router()
    replacement = WriteHandler(fn=writers.write_json_model, extension=".custom")

    router.register_handler("float", replacement)

    assert router._type_handlers["float"] is replacement


def test_create_output_router_with_json_schemas_custom_only():
    """Test that custom-only mode excludes built-in handlers."""
    router = create_output_router_with_json_schemas(
        ["CustomSchema1"],
        include_builtins=False,
    )

    # Check custom schema is registered
    assert router.has_handler("CustomSchema1")

    # Check built-ins are NOT there
    assert not router.has_handler("FinancialResults")
    assert not router.has_handler("float")


def test_custom_only_router_can_explicitly_register_wrapped_scalar(tmp_path: Path):
    router = create_output_router_with_json_schemas(
        ["RootModel[float]"],
        include_builtins=False,
    )
    bindings = {
        "value": PipelineChannelBinding(
            type_name="RootModel[float]",
            channel_name="value",
            source=ChannelSource.MODULE,
            destination_filename="value.json",
        )
    }

    result = router.write_outputs(
        bindings,
        {"value": RootModel[float](1.25)},
        base_output_dir=tmp_path,
        run_name="wrapped",
    )

    assert (result.run_dir / "value.json").read_text() == "1.25"


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
    values = {
        "custom": fixture_builders.sample_financial_results()
    }  # Any pydantic model will work

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
    values = {"unknown": fixture_builders.sample_financial_results()}

    with pytest.raises(
        OutputRouterError, match="No writer registered for type 'UnknownType'"
    ):
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
        "first": fixture_builders.sample_financial_results(),
        "second": fixture_builders.sample_financial_results(),
    }

    with pytest.raises(
        OutputRouterError,
        match="Destination filename 'duplicate.json' declared more than once",
    ):
        router.write_outputs(bindings, values, run_name="test")


def test_create_default_router_supports_in_memory():
    """Test that create_default_router accepts in_memory parameter."""
    router = create_default_router(in_memory=True)

    bindings = {
        "results": PipelineChannelBinding(
            type_name=schema.FinancialResults.__name__,
            channel_name="results",
            source=ChannelSource.MODULE,
            destination_filename="results.json",
        )
    }
    values = {"results": fixture_builders.sample_financial_results()}

    result = router.write_outputs(bindings, values, run_name="test")

    # Should succeed without writing files
    assert result.manifest.short_id == "mem"
    assert not result.run_dir.exists()
