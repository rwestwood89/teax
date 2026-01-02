from __future__ import annotations

import os
from pathlib import Path

import pytest

from simkit.config import environment as env
from simkit.config.pipeline_schema import (
    ChannelSource,
    PipelineChannelBinding,
    PipelineModuleSpec,
    PipelineSpecification,
)
from simkit.core.pipeline_executor import PipelineExecutionContext, SerialPipelineExecutor
from simkit.core.pipeline_registry import PipelineModuleRegistry
from simkit.core.pipeline_validator import PipelineValidationError
from simkit.io import readers
from simkit.io.output_router import OutputRouter, OutputRouterError

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _copy_fixture(src_name: str, dest: Path) -> None:
    dest.write_bytes((FIXTURE_DIR / src_name).read_bytes())


def test_load_entry_binding_prefers_literal_path(tmp_path, monkeypatch):
    monkeypatch.delenv("PYRONDO_INPUT_DIR", raising=False)
    executor = SerialPipelineExecutor()
    binding = PipelineChannelBinding(
        type_name="Geography",
        channel_name="geo",
        source=ChannelSource.ENTRY,
        artifact_path=Path("inputs/geography.json"),
    )

    literal_dir = tmp_path / "inputs"
    literal_dir.mkdir(parents=True)
    artifact_path = literal_dir / "geography.json"
    _copy_fixture("geography_us_ca_pge.json", artifact_path)

    value, resolved = executor._load_entry_binding("entry_point", binding, tmp_path)

    assert resolved == artifact_path.resolve()
    assert value.country == "US"


def test_load_entry_binding_uses_pyrondo_input_dir_fallback(tmp_path, monkeypatch):
    executor = SerialPipelineExecutor()
    binding = PipelineChannelBinding(
        type_name="Geography",
        channel_name="geo",
        source=ChannelSource.ENTRY,
        artifact_path=Path("geographies/us_ca_pge.json"),
    )

    base_dir = tmp_path / "spec"
    base_dir.mkdir()

    fallback_dir = tmp_path / "env_inputs"
    fallback_dir.mkdir()
    fallback_artifact = fallback_dir / "geographies" / "us_ca_pge.json"
    fallback_artifact.parent.mkdir(parents=True, exist_ok=True)
    _copy_fixture("geography_us_ca_pge.json", fallback_artifact)

    monkeypatch.setenv("PYRONDO_INPUT_DIR", str(fallback_dir))

    value, resolved = executor._load_entry_binding("entry_point", binding, base_dir)

    assert resolved == fallback_artifact.resolve()
    assert value.country == "US"


def test_load_entry_binding_reports_all_attempted_paths(tmp_path, monkeypatch):
    executor = SerialPipelineExecutor()
    binding = PipelineChannelBinding(
        type_name="Geography",
        channel_name="geo",
        source=ChannelSource.ENTRY,
        artifact_path=Path("missing/geography.json"),
    )

    base_dir = tmp_path / "spec"
    base_dir.mkdir()

    fallback_dir = tmp_path / "env_inputs"
    fallback_dir.mkdir()
    monkeypatch.setenv("PYRONDO_INPUT_DIR", str(fallback_dir))

    with pytest.raises(PipelineValidationError) as excinfo:
        executor._load_entry_binding("entry_point", binding, base_dir)

    message = str(excinfo.value)
    literal_path = (base_dir / binding.artifact_path).resolve()
    fallback_path = (fallback_dir / binding.artifact_path).resolve()
    assert str(literal_path) in message
    assert str(fallback_path) in message


def test_execute_entry_invokes_loadenv(monkeypatch, tmp_path):
    called: list[bool] = []

    def fake_loadenv() -> None:
        called.append(True)

    monkeypatch.setattr("simkit.core.pipeline_executor.loadenv", fake_loadenv)

    executor = SerialPipelineExecutor()
    context = PipelineExecutionContext(PipelineModuleRegistry())
    module_spec = PipelineModuleSpec.model_construct(
        key="entry_point",
        module_type="EntryPoint",
        outputs={
            "geo": PipelineChannelBinding(
                type_name="Geography",
                channel_name="geo",
                source=ChannelSource.ENTRY,
                artifact_path=Path("inputs/geography.json"),
            )
        },
    )
    spec = PipelineSpecification.model_construct(modules={}, source_path=tmp_path / "pipeline.yaml")

    monkeypatch.setattr(
        SerialPipelineExecutor,
        "_load_entry_binding",
        lambda self, module_key, binding, base_dir: ("stub", base_dir),
    )

    executor._execute_entry(module_spec, spec, context)

    assert called, "loadenv should be invoked before resolving entry artifacts"
    assert context.entry_artifacts["geo"] == spec.source_path.parent


def test_resolve_input_dir_defaults_when_env_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("PYRONDO_INPUT_DIR", raising=False)
    monkeypatch.setattr(env, "_PROJECT_ROOT", tmp_path)

    result = env.resolve_input_dir()

    expected = (tmp_path / "run_data" / "inputs").resolve()
    assert result == expected
    assert "PYRONDO_INPUT_DIR" not in os.environ


def test_executor_validates_output_router_handlers():
    """Test that validation fails early if output router doesn't have required handlers."""
    registry = PipelineModuleRegistry.from_static_modules()
    executor = SerialPipelineExecutor(registry, output_router=OutputRouter(type_handlers={}))

    spec_path = FIXTURE_DIR / "pipeline_configs" / "demo_linear_alt.yaml"
    spec = readers.read_pipeline_spec(spec_path)

    # Validation now happens at build_graph time, not runtime
    with pytest.raises(PipelineValidationError, match="no registered write handler"):
        executor.build_graph(spec)
