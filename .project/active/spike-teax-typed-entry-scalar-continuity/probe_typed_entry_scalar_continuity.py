"""Throwaway S5 probe for typed EntryPoint injection and scalar continuity.

The prototype deliberately lives outside production code. It reuses TEAx's
real parser, validator, graph, executor, module registry, and output router.
Only the EntryPoint source is replaced for the mapping-backed leg.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from types import MappingProxyType
from typing import Any, ClassVar, Mapping

from pydantic import BaseModel, RootModel

from simkit.core.base import ModuleBase, ModuleResult
from simkit.core.pipeline import (
    _build_entry_loaders,
    _build_schema_type_registry,
    entry_point_validate,
)
from simkit.core.pipeline_executor import (
    PipelineExecutionContext,
    RunResult,
    SerialPipelineExecutor,
)
from simkit.core.registry_builder import create_registry
from simkit.io.output_router import create_default_router


HOME = Path(__file__).resolve().parent
SPEC_PATH = HOME / "probe_pipeline.yaml"
CANDIDATE_PATH = HOME / "candidate.json"
NO_PERSIST_OUTPUT_DIR = HOME / "no-persist-outputs"
CANDIDATE_COUNT = 100


class ProbeInput(BaseModel):
    value: float


class ProbeDoubler(ModuleBase[ProbeInput, RootModel[float]]):
    name = "probe_doubler"
    version = "s5"
    run_count: ClassVar[int] = 0

    def validate_and_fill_default(self, value: float) -> ProbeInput:
        return ProbeInput(value=value)

    def run(self, value: float) -> ModuleResult[RootModel[float]]:
        type(self).run_count += 1
        validated = self.validate_and_fill_default(value)
        return ModuleResult(data=RootModel[float](validated.value * 2.0))


class ProbeAdder(ModuleBase[RootModel[float], RootModel[float]]):
    name = "probe_adder"
    version = "s5"
    run_count: ClassVar[int] = 0
    received_types: ClassVar[list[type]] = []

    def validate_and_fill_default(self, root: float) -> RootModel[float]:
        return RootModel[float](root)

    def run(self, root: float) -> ModuleResult[RootModel[float]]:
        type(self).run_count += 1
        type(self).received_types.append(type(root))
        validated = self.validate_and_fill_default(root)
        return ModuleResult(data=RootModel[float](validated.root + 22.0))


@dataclass(frozen=True)
class MappingEntrySource:
    """Strict, already-typed values keyed by EntryPoint channel ID."""

    expected_types: Mapping[str, type[BaseModel]]

    @classmethod
    def from_spec(
        cls,
        specification: Any,
        schema_types: Mapping[str, type],
    ) -> "MappingEntrySource":
        entry = next(module for module in specification.modules.values() if module.is_entry)
        expected: dict[str, type[BaseModel]] = {}
        for binding in entry.outputs.values():
            type_name = binding.type_name
            expected_type = schema_types.get(type_name)
            if expected_type is None:
                raise TypeError(f"Entry channel {binding.channel_name!r} has unknown type {type_name!r}")
            expected[binding.channel_name] = expected_type
        return cls(expected_types=MappingProxyType(expected))

    def validate(self, values: Mapping[str, Any]) -> Mapping[str, BaseModel]:
        expected_keys = set(self.expected_types)
        supplied_keys = set(values)
        missing = sorted(expected_keys - supplied_keys)
        extra = sorted(supplied_keys - expected_keys)
        if missing or extra:
            raise ValueError(f"Entry mapping key mismatch: missing={missing}, extra={extra}")

        validated: dict[str, BaseModel] = {}
        for channel_name, expected_type in self.expected_types.items():
            value = values[channel_name]
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"Entry channel {channel_name!r} expects {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )
            validated[channel_name] = value
        return MappingProxyType(validated)


class MappingPipelineExecutionContext(PipelineExecutionContext):
    def __init__(self, registry: Any, entry_values: Mapping[str, BaseModel]) -> None:
        super().__init__(registry)
        self.entry_values = entry_values


class MappingSerialPipelineExecutor(SerialPipelineExecutor):
    """Real executor with only file-backed EntryPoint loading replaced."""

    def _execute_entry(self, module_spec: Any, spec: Any, context: Any) -> None:
        del spec
        if not isinstance(context, MappingPipelineExecutionContext):
            raise TypeError("Mapping executor requires MappingPipelineExecutionContext")
        for binding in module_spec.outputs.values():
            context.set_channel(
                binding.channel_name,
                context.entry_values[binding.channel_name],
            )


class PreparedMappingPipeline:
    def __init__(
        self,
        executor: MappingSerialPipelineExecutor,
        graph: Any,
        registry: Any,
        entry_source: MappingEntrySource,
    ) -> None:
        self.executor = executor
        self.graph = graph
        self.registry = registry
        self.entry_source = entry_source
        self.contexts: list[MappingPipelineExecutionContext] = []

    def evaluate(self, values: Mapping[str, Any]) -> RunResult:
        # This validation is deliberately before context creation and module execution.
        validated = self.entry_source.validate(values)
        context = MappingPipelineExecutionContext(self.registry, validated)
        result = self.executor.run(
            self.graph,
            context,
            base_output_dir=NO_PERSIST_OUTPUT_DIR,
            persist_outputs=False,
        )
        self.contexts.append(context)
        return result


def normalize_outputs(result: RunResult) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for name, value in result.outputs.items():
        normalized[name] = (
            value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        )
    return normalized


def prepare_mapping_pipeline(
    specification: Any,
    registry: Any,
    schema_types: Mapping[str, type],
    entry_loaders: Mapping[type, Any],
) -> PreparedMappingPipeline:
    executor = MappingSerialPipelineExecutor(
        registry,
        schema_type_registry=dict(schema_types),
        entry_loaders=dict(entry_loaders),
    )
    graph = executor.build_graph(specification)
    source = MappingEntrySource.from_spec(specification, schema_types)
    return PreparedMappingPipeline(executor, graph, registry, source)


def main() -> None:
    ProbeDoubler.run_count = 0
    ProbeAdder.run_count = 0
    ProbeAdder.received_types = []

    registry = create_registry([ProbeDoubler, ProbeAdder])
    custom_types = [ProbeInput, RootModel[float]]
    schema_types = _build_schema_type_registry(custom_types)
    entry_loaders = _build_entry_loaders(custom_types)
    specification = entry_point_validate(SPEC_PATH)
    candidates = [ProbeInput(value=-50.0 + index * 1.25) for index in range(CANDIDATE_COUNT)]

    preparation_started = perf_counter()
    prepared = prepare_mapping_pipeline(
        specification,
        registry,
        schema_types,
        entry_loaders,
    )
    mapping_preparation_seconds = perf_counter() - preparation_started

    mapping_started = perf_counter()
    mapping_results = [
        normalize_outputs(prepared.evaluate({"candidate": candidate}))
        for candidate in candidates
    ]
    mapping_evaluation_seconds = perf_counter() - mapping_started

    file_executor = SerialPipelineExecutor(
        registry,
        schema_type_registry=dict(schema_types),
        entry_loaders=dict(entry_loaders),
    )
    file_preparation_started = perf_counter()
    file_graph = file_executor.build_graph(specification)
    file_preparation_seconds = perf_counter() - file_preparation_started
    file_results: list[dict[str, Any]] = []
    file_started = perf_counter()
    for candidate in candidates:
        CANDIDATE_PATH.write_text(candidate.model_dump_json(), encoding="utf-8")
        context = PipelineExecutionContext(registry)
        result = file_executor.run(file_graph, context, persist_outputs=False)
        file_results.append(normalize_outputs(result))
    file_evaluation_seconds = perf_counter() - file_started

    assert mapping_results == file_results
    for candidate, outputs in zip(candidates, mapping_results, strict=True):
        assert outputs == {
            "doubled": candidate.value * 2.0,
            "result": candidate.value * 2.0 + 22.0,
        }

    # Retain all contexts so object IDs cannot be reused, then prove each case kept
    # its own candidate and channels after every later case completed.
    assert len({id(context) for context in prepared.contexts}) == CANDIDATE_COUNT
    assert len({id(context.channels) for context in prepared.contexts}) == CANDIDATE_COUNT
    for candidate, context in zip(candidates, prepared.contexts, strict=True):
        assert context.channels["candidate"] == candidate
        assert context.channels["doubled"].root == candidate.value * 2.0
        assert context.channels["result"].root == candidate.value * 2.0 + 22.0

    module_counts_before_invalid = (ProbeDoubler.run_count, ProbeAdder.run_count)
    invalid_errors: dict[str, str] = {}
    invalid_cases = {
        "missing": {},
        "extra": {
            "candidate": ProbeInput(value=1.0),
            "unexpected": ProbeInput(value=2.0),
        },
        "wrong_type": {"candidate": RootModel[float](1.0)},
    }
    for name, values in invalid_cases.items():
        try:
            prepared.evaluate(values)
        except (TypeError, ValueError) as error:
            invalid_errors[name] = str(error)
        else:
            raise AssertionError(f"Invalid mapping {name!r} was accepted")
    assert (ProbeDoubler.run_count, ProbeAdder.run_count) == module_counts_before_invalid

    # Rebuild the validated graph for every candidate to quantify what prepare-once
    # removes. This leg uses the same mapping source and still persists nothing.
    unprepared_started = perf_counter()
    unprepared_results: list[dict[str, Any]] = []
    for candidate in candidates:
        one_shot = prepare_mapping_pipeline(
            specification,
            registry,
            schema_types,
            entry_loaders,
        )
        unprepared_results.append(
            normalize_outputs(one_shot.evaluate({"candidate": candidate}))
        )
    unprepared_evaluation_seconds = perf_counter() - unprepared_started
    assert unprepared_results == mapping_results

    assert all(received_type is float for received_type in ProbeAdder.received_types)
    assert not NO_PERSIST_OUTPUT_DIR.exists()

    scalar_names = [
        "float",
        "int",
        "str",
        "bool",
        "RootModel[float]",
        "RootModel[int]",
        "RootModel[str]",
        "RootModel[bool]",
    ]
    router = create_default_router()
    assert all(router.has_handler(name) for name in scalar_names)

    cache_speedup = unprepared_evaluation_seconds / mapping_evaluation_seconds
    report = {
        "candidate_count": CANDIDATE_COUNT,
        "mapping_file_parity_cases": sum(
            mapping == file for mapping, file in zip(mapping_results, file_results, strict=True)
        ),
        "invalid_mappings_rejected_before_module_run": sorted(invalid_errors),
        "invalid_errors": invalid_errors,
        "fresh_contexts": len(prepared.contexts),
        "state_leak_detected": False,
        "scalar_continuity": {
            "producer_channel_type": RootModel[float].__name__,
            "consumer_runtime_type": "float",
            "all_consumer_values_were_float": True,
        },
        "default_scalar_exit_handlers": scalar_names,
        "no_persist_output_directory_exists": False,
        "timing_ms": {
            "mapping_prepare_once": round(mapping_preparation_seconds * 1000, 3),
            "mapping_100_evaluations": round(mapping_evaluation_seconds * 1000, 3),
            "file_prepare_once": round(file_preparation_seconds * 1000, 3),
            "file_100_evaluations_including_input_rewrites": round(
                file_evaluation_seconds * 1000, 3
            ),
            "mapping_100_rebuild_and_evaluations": round(
                unprepared_evaluation_seconds * 1000, 3
            ),
        },
        "prepare_once_speedup_over_rebuild_each_case": round(cache_speedup, 3),
        "prepare_once_materially_faster_at_1_25x_threshold": cache_speedup >= 1.25,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
