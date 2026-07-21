"""Failure-context transport for the serial executor."""
from __future__ import annotations

import traceback

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


class _Value(BaseModel):
    value: float


class _SentinelError(Exception):
    pass


class _FailingModule(ModuleBase):
    name = "failing"
    version = "test-only"

    def __init__(self, error: Exception) -> None:
        self._error = error

    def run(self) -> ModuleResult[_Value]:
        raise self._error


class _SuccessfulModule(ModuleBase):
    name = "successful"
    version = "test-only"

    def run(self) -> ModuleResult[_Value]:
        return ModuleResult(data=_Value(value=1.0))


class _NoopEntryExecutor(SerialPipelineExecutor):
    def _execute_entry(self, module_spec, spec, context) -> None:
        return None


def _graph(module_type: str, module_key: str):
    output = PipelineChannelBinding(
        source=ChannelSource.MODULE,
        type_name="_Value",
        channel_name="result",
    )
    spec = PipelineSpecification(
        modules={
            "entry": PipelineModuleSpec(key="entry", module_type="EntryPoint"),
            module_key: PipelineModuleSpec(
                key=module_key,
                module_type=module_type,
                outputs={"result": output},
            ),
            "exit": PipelineModuleSpec(
                key="exit",
                module_type="ExitPoint",
                outputs={"result": output},
            ),
        }
    )
    return PipelineDagBuilder().build(spec)


def _register(registry, module_type, factory) -> None:
    registry.register(
        module_type,
        ModuleDescriptor(
            module_type=module_type,
            factory=factory,
            required_inputs={},
            optional_inputs={},
            outputs={"result": _Value},
            version="test-only",
        ),
    )


def test_run_records_failing_key_without_changing_exception_and_resets_context():
    sentinel = _SentinelError("arithmetic failed")
    registry = PipelineModuleRegistry()
    _register(registry, "FailingModule", lambda: _FailingModule(sentinel))
    _register(registry, "SuccessfulModule", _SuccessfulModule)
    executor = _NoopEntryExecutor(registry)
    context = PipelineExecutionContext(registry)
    other_context = PipelineExecutionContext(registry)

    with pytest.raises(_SentinelError) as caught:
        executor.run(
            _graph("FailingModule", "later_constraint"),
            context,
            persist_outputs=False,
        )

    assert caught.value is sentinel
    assert "run" in [frame.name for frame in traceback.extract_tb(sentinel.__traceback__)]
    assert context.failed_module_key == "later_constraint"
    assert other_context.failed_module_key is None

    executor.run(
        _graph("SuccessfulModule", "successful_constraint"),
        context,
        persist_outputs=False,
    )
    assert context.failed_module_key is None
    assert other_context.failed_module_key is None
