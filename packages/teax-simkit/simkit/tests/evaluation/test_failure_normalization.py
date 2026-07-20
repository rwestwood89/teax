"""Focused evaluator normalization and identity-boundary regressions."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from simkit.config.pipeline_schema import (
    ChannelSource,
    PipelineChannelBinding,
    PipelineModuleSpec,
    PipelineSpecification,
)
from simkit.core.base import ModuleBase, ModuleResult
from simkit.core.pipeline_executor import PipelineExecutionContext, SerialPipelineExecutor
from simkit.core.pipeline_graph import PipelineDagBuilder
from simkit.core.pipeline_registry import ModuleDescriptor, PipelineModuleRegistry
from simkit.evaluation import EvaluationFailed, EvaluationFailure, EvaluationPhase
from simkit.evaluation.evaluator import FileBackedEvaluator, _normalize_run_failure
from simkit.evaluation.package_load import ProvisionalPackageLoader

from .conftest import ENTRY_FIXTURES_DIR, FIXTURE_DIR


class _SentinelError(Exception):
    pass


class _Value(BaseModel):
    value: float


class _SuccessfulModule(ModuleBase):
    name = "successful"
    version = "test-only"

    def run(self) -> ModuleResult[_Value]:
        return ModuleResult(data=_Value(value=1.0))


class _NoopEntryExecutor(SerialPipelineExecutor):
    def _execute_entry(self, module_spec, spec, context) -> None:
        return None


class _ExitFailingContext(PipelineExecutionContext):
    def __init__(self, registry, error: Exception) -> None:
        super().__init__(registry)
        self._error = error

    def get_channel(self, name: str):
        if name == "result":
            raise self._error
        return super().get_channel(name)


def _loader(tmp_path: Path) -> ProvisionalPackageLoader:
    return ProvisionalPackageLoader(
        package_dir=FIXTURE_DIR,
        package_name="wi014_s4",
        link_root=tmp_path / "package_links",
    )


def _file_evaluator(tmp_path: Path, output_dir: Path) -> FileBackedEvaluator:
    return FileBackedEvaluator(
        _loader(tmp_path),
        FIXTURE_DIR,
        tmp_path / "work",
        output_dir,
    )


def _exit_graph():
    output = PipelineChannelBinding(
        source=ChannelSource.MODULE,
        type_name="_Value",
        channel_name="result",
    )
    spec = PipelineSpecification(
        modules={
            "entry": PipelineModuleSpec(key="entry", module_type="EntryPoint"),
            "successful_module": PipelineModuleSpec(
                key="successful_module",
                module_type="SuccessfulModule",
                outputs={"result": output},
            ),
            "exit": PipelineModuleSpec(
                key="exit", module_type="ExitPoint", outputs={"result": output}
            ),
        }
    )
    return PipelineDagBuilder().build(spec)


def test_normalizer_builds_complete_record_and_chains_original():
    registry = PipelineModuleRegistry()
    context = PipelineExecutionContext(registry)
    context.failed_module_key = "failed_key"
    original = _SentinelError("arithmetic failed")

    with pytest.raises(EvaluationFailed) as caught:
        _normalize_run_failure(original, context)

    assert caught.value.__cause__ is original
    assert caught.value.failure == EvaluationFailure(
        phase=EvaluationPhase.MODULE_EXECUTION,
        module_or_channel="failed_key",
        cause="_SentinelError: arithmetic failed",
    )


def test_file_entry_failure_has_no_module_identity(tmp_path):
    evaluator = _file_evaluator(tmp_path, tmp_path / "outputs")
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")

    with pytest.raises(EvaluationFailed) as caught:
        evaluator.evaluate(malformed)

    assert caught.value.failure.phase is EvaluationPhase.MODULE_EXECUTION
    assert caught.value.failure.module_or_channel is None
    assert caught.value.__cause__ is not None


def test_exit_collection_failure_has_no_module_identity():
    registry = PipelineModuleRegistry()
    registry.register(
        "SuccessfulModule",
        ModuleDescriptor(
            module_type="SuccessfulModule",
            factory=_SuccessfulModule,
            required_inputs={},
            optional_inputs={},
            outputs={"result": _Value},
            version="test-only",
        ),
    )
    original = _SentinelError("exit collection failed")
    context = _ExitFailingContext(registry, original)
    executor = _NoopEntryExecutor(registry)

    with pytest.raises(_SentinelError) as raw:
        executor.run(_exit_graph(), context, persist_outputs=False)

    assert raw.value is original
    assert context.failed_module_key is None
    with pytest.raises(EvaluationFailed) as caught:
        _normalize_run_failure(original, context)
    assert caught.value.failure.phase is EvaluationPhase.MODULE_EXECUTION
    assert caught.value.failure.module_or_channel is None
    assert caught.value.__cause__ is original


def test_router_setup_failure_is_output_write_with_no_module_identity(tmp_path):
    """A router/output-setup failure happens inside the write phase, so it is
    honestly stamped OUTPUT_WRITE (Item 11 C1) — not MODULE_EXECUTION, which it
    used to claim while OUTPUT_WRITE was defined-never-emitted. No module failed,
    so the module identity stays None."""
    output_file = tmp_path / "output-file"
    output_file.write_text("occupied", encoding="utf-8")
    evaluator = _file_evaluator(tmp_path, output_file)

    with pytest.raises(EvaluationFailed) as caught:
        evaluator.evaluate(ENTRY_FIXTURES_DIR / "satisfied.json")

    assert caught.value.failure.phase is EvaluationPhase.OUTPUT_WRITE
    assert caught.value.failure.module_or_channel is None
    assert caught.value.__cause__ is not None
