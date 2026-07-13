"""Evaluator: prepare once, evaluate per case (touches the generated package — D2)."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Protocol

from pydantic import BaseModel

from ..core.pipeline import (
    _build_entry_loaders,
    _build_schema_type_registry,
    entry_point_validate,
)
from ..core.pipeline_executor import PipelineExecutionContext, SerialPipelineExecutor
from ..io.output_router import create_output_router_with_json_schemas

from .entry_source import MappingEntrySource
from .evidence import EvidenceProvenance, ModelEvidence
from .failure import EvaluationFailed, EvaluationFailure, EvaluationPhase
from .package_load import PackageLoader
from .projection import project

REPORT_CHANNEL = "constraint_report"


class Evaluator(Protocol):
    def evaluate(self, typed_inputs: Mapping[str, BaseModel]) -> ModelEvidence: ...


def _json_safe(value: Any) -> Any:
    """Non-finite floats -> a stable tag; everything else passes through.

    Digest-input only (design.md#implementation-notes) — never the on-disk
    evidence encoding.
    """
    if isinstance(value, float) and not math.isfinite(value):
        tag = "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf")
        return {"__nonfinite__": tag}
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(val) for val in value]
    return value


def _input_digest(typed_inputs: Mapping[str, BaseModel]) -> str:
    payload = {channel: _json_safe(model.model_dump(mode="json")) for channel, model in typed_inputs.items()}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class _MappingContext(PipelineExecutionContext):
    def __init__(self, registry, entry_values: Mapping[str, BaseModel]) -> None:
        super().__init__(registry)
        self.entry_values = entry_values


class _MappingExecutor(SerialPipelineExecutor):
    """Real executor with only file-backed EntryPoint loading replaced (B4)."""

    def _execute_entry(self, module_spec, spec, context) -> None:
        for binding in module_spec.outputs.values():
            context.set_channel(binding.channel_name, context.entry_values[binding.channel_name])


class PreparedEvaluator:
    """In-memory evaluator: prepare once (topology + write-handler validation,
    INV3), evaluate per case with a fresh context (no channel bleed)."""

    EVIDENCE_SCHEMA_VERSION = "v1"
    EVALUATOR_VERSION = "v1"

    def __init__(self, loader: PackageLoader, spec_path: Path) -> None:
        self.package, self.fingerprint = loader.load()
        custom_types = list(self.package.CUSTOM_SCHEMA_TYPES)
        schema_types = _build_schema_type_registry(custom_types)
        entry_loaders = _build_entry_loaders(custom_types)
        registry_factory = getattr(self.package, f"create_{self.package.__name__}_registry")
        self._registry = registry_factory()
        spec = entry_point_validate(spec_path)

        router = create_output_router_with_json_schemas(
            [t.__name__ for t in custom_types], include_builtins=True, in_memory=True
        )
        self._executor = _MappingExecutor(
            self._registry,
            output_router=router,
            schema_type_registry=dict(schema_types),
            entry_loaders=dict(entry_loaders),
        )
        try:
            self._graph = self._executor.build_graph(spec)
        except Exception as error:
            raise EvaluationFailed(
                EvaluationFailure(
                    phase=EvaluationPhase.PREPARATION,
                    cause=f"{type(error).__name__}: {error}",
                )
            ) from error
        self._source = MappingEntrySource.from_spec(spec, schema_types)
        # Convenience access to the entry channel's type; this evaluator is
        # bound to one pipeline, so the entry model is known at prepare time.
        self.ToyPlantParams = self.package.ToyPlantParams

    def evaluate(self, typed_inputs: Mapping[str, BaseModel]) -> ModelEvidence:
        validated = self._source.validate(typed_inputs)
        context = _MappingContext(self._registry, validated)
        try:
            result = self._executor.run(self._graph, context, persist_outputs=False)
        except Exception as error:
            raise EvaluationFailed(
                EvaluationFailure(
                    phase=EvaluationPhase.MODULE_EXECUTION,
                    cause=f"{type(error).__name__}: {error}",
                )
            ) from error
        report = result.outputs[REPORT_CHANNEL]
        provenance = EvidenceProvenance(
            executable_fingerprint=self.fingerprint,
            evidence_schema_version=self.EVIDENCE_SCHEMA_VERSION,
            evaluator_version=self.EVALUATOR_VERSION,
            input_digest=_input_digest(typed_inputs),
        )
        return project(result, report, provenance=provenance)
