"""Serial pipeline executor leveraging the channel-based specification."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from ..config import schema
from ..config.environment import loadenv, resolve_input_dir
from ..config.pipeline_schema import (
    ChannelSource,
    PipelineChannelBinding,
    PipelineModuleSpec,
    PipelineSpecification,
)
from ..io import readers
from ..io.output_router import OutputRouter, OutputRouterError, OutputRouterResult, create_default_router
from .pipeline_graph import PipelineGraph
from .pipeline_registry import ModuleDescriptor, PipelineModuleRegistry
from .pipeline_validator import PipelineValidationError, PipelineValidator


class PipelineExecutionContext:
    """Execution state for a pipeline run."""

    def __init__(
        self,
        registry: PipelineModuleRegistry,
    ) -> None:
        self.registry = registry
        self.channels: Dict[str, Any] = {}
        self.module_versions: Dict[str, str] = {}
        self.entry_artifacts: Dict[str, Path] = {}

    def set_channel(self, name: str, value: Any) -> None:
        self.channels[name] = value

    def get_channel(self, name: str) -> Any:
        if name not in self.channels:
            raise KeyError(f"Channel '{name}' not produced during execution")
        return self.channels[name]

    def record_entry_artifact(self, name: str, path: Path) -> None:
        self.entry_artifacts[name] = path


@dataclass(frozen=True)
class RunResult:
    """Container for pipeline execution results."""

    outputs: Mapping[str, Any]
    manifest: schema.RunManifest | None
    module_versions: Mapping[str, str]
    pipeline_metadata: schema.PipelineRunMetadata | None = None
    provenance: schema.Provenance | None = None


class SerialPipelineExecutor:
    """Executes modules in topological order using registry metadata."""

    def __init__(
        self,
        registry: PipelineModuleRegistry | None = None,
        *,
        output_router: OutputRouter | None = None,
    ) -> None:
        self._registry = registry or PipelineModuleRegistry.from_static_modules()
        self._validator = PipelineValidator(self._registry)
        self._output_router = output_router or create_default_router()

    def build_graph(self, spec: PipelineSpecification) -> PipelineGraph:
        return self._validator.validate(spec)

    def run(
        self,
        graph: PipelineGraph,
        context: PipelineExecutionContext,
        *,
        base_output_dir: Path | None = None,
        run_name: str | None = None,
        pipeline_metadata: object | None = None,
        persist_outputs: bool = True,
    ) -> RunResult:
        spec = graph.spec
        exit_spec = next((m for m in spec.modules.values() if m.is_exit), None)
        if exit_spec is None:  # pragma: no cover - validator guarantees an exit module
            raise PipelineValidationError("Pipeline is missing an ExitPoint module")

        if persist_outputs:
            self._ensure_exit_handlers(exit_spec)

        exit_outputs: Dict[str, Any] | None = None
        for module_key in graph.topological_order:
            module_spec = spec.modules[module_key]
            if module_spec.is_entry:
                self._execute_entry(module_spec, spec, context)
                continue
            if module_spec.is_exit:
                exit_outputs = {}
                for field, binding in module_spec.outputs.items():
                    try:
                        exit_outputs[field] = context.get_channel(binding.channel_name)
                    except KeyError:
                        # Optional exit outputs may not be produced; skip here, router will record absence.
                        continue
                break
            self._execute_module(module_key, module_spec, context)
        else:  # pragma: no cover - spec validator guarantees an exit node
            raise RuntimeError("Pipeline specification is missing an exit module")

        if exit_outputs is None:  # pragma: no cover - defensive guard
            raise RuntimeError("Pipeline execution did not encounter ExitPoint outputs")

        router_manifest: schema.RunManifest | None = None
        if persist_outputs:
            router_result = self._output_router.write_outputs(
                exit_spec.outputs,
                context.channels,
                base_output_dir=base_output_dir,
                run_name=run_name,
                pipeline_metadata=pipeline_metadata,
            )
            router_manifest = router_result.manifest

        return RunResult(
            outputs=exit_outputs,
            manifest=router_manifest,
            module_versions=dict(context.module_versions),
        )

    # ------------------------------------------------------------------
    # Execution helpers

    def _execute_entry(
        self, module_spec: PipelineModuleSpec, spec: PipelineSpecification, context: PipelineExecutionContext
    ) -> None:
        loadenv()

        if spec.source_path is not None:
            base_dir = spec.source_path.parent
        else:
            base_dir = Path.cwd()
        for binding in module_spec.outputs.values():
            value, resolved_path = self._load_entry_binding(module_spec.key, binding, base_dir)
            context.set_channel(binding.channel_name, value)
            context.record_entry_artifact(binding.channel_name, resolved_path)

    def _execute_module(
        self,
        module_key: str,
        module_spec: PipelineModuleSpec,
        context: PipelineExecutionContext,
    ) -> None:
        descriptor = self._registry.get(module_spec.module_type)
        module = descriptor.factory()

        # Gather inputs
        kwargs: Dict[str, Any] = {}
        for field, binding in module_spec.inputs.items():
            kwargs[field] = _resolve_input(binding, context)

        outputs = module_spec.outputs
        result = module.run(**kwargs)
        data = result.data
        if len(outputs) == 1:
            binding = next(iter(outputs.values()))
            context.set_channel(binding.channel_name, data)
        else:
            if not isinstance(data, Mapping):
                raise RuntimeError(
                    f"Module '{module_key}' produced multiple outputs but returned non-mapping data"
                )
            for field, binding in outputs.items():
                context.set_channel(binding.channel_name, data[field])

        context.module_versions[module_key] = descriptor.version

    # ------------------------------------------------------------------
    # Utility helpers

    def _ensure_exit_handlers(self, module_spec: PipelineModuleSpec) -> None:
        for binding in module_spec.outputs.values():
            type_name = binding.type_name
            if type_name is None:
                raise OutputRouterError(
                    f"ExitPoint binding '{binding.channel_name}' is missing a type declaration"
                )
            if not self._output_router.has_handler(type_name):
                raise OutputRouterError(
                    f"No writer registered for ExitPoint output type '{type_name}'"
                )

    def _load_entry_binding(
        self,
        module_key: str,
        binding: PipelineChannelBinding,
        base_dir: Path,
    ) -> tuple[Any, Path]:
        """
        Resolve the artifact path for an entry binding. 
        
        Will first try to resolve paths relative to "base_dir", but will fall back to:
        - Resolving relative to `PYRONDO_INPUT_DIR` environment variable if it is set.
        - Resolving relative to `run_data/inputs` in the project root if `PYRONDO_INPUT_DIR` is not set.
        - Raising a `PipelineValidationError` if the artifact path cannot be resolved.

        Args:
            module_key: The key of the module that is binding the artifact.
            binding: The binding of the artifact.
            base_dir: The base directory to resolve the artifact path relative to. Should come from either the pipeline spec or the current working directory.

        Returns:
            A tuple of the artifact value and the resolved path.
        """
        if binding.artifact_path is None:
            raise ValueError(f"Entry binding '{binding.channel_name}' is missing an artifact path")
        literal = binding.artifact_path
        if not literal.is_absolute():
            literal = (base_dir / literal).resolve()
        attempted_paths = [literal]
        if literal.exists():
            resolved_path = literal
        else:
            fallback_root = resolve_input_dir()
            fallback = (fallback_root / binding.artifact_path).resolve()
            if fallback not in attempted_paths:
                attempted_paths.append(fallback)
            if fallback.exists():
                resolved_path = fallback
            else:
                attempted = ", ".join(str(path) for path in attempted_paths)
                raise PipelineValidationError(
                    (
                        f"Entry binding '{binding.channel_name}' could not locate artifact. "
                        f"Attempted paths: {attempted}"
                    ),
                    module=module_key,
                    details={
                        "channel": binding.channel_name,
                        "attempted_paths": [str(path) for path in attempted_paths],
                    },
                )
        type_cls = _resolve_schema_type(binding.type_name)
        loader = _ENTRY_LOADERS.get(type_cls)
        if loader is None:
            raise ValueError(f"No loader registered for entry binding type '{binding.type_name}'")
        return loader(resolved_path), resolved_path


# ----------------------------------------------------------------------
# Helper functions


def _resolve_schema_type(type_name: str | None) -> type[schema.StrictBaseModel]:
    if type_name is None:
        raise ValueError("Channel binding is missing a type name")
    try:
        return getattr(schema, type_name)
    except AttributeError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Unknown schema type '{type_name}'") from exc


def _resolve_input(binding: PipelineChannelBinding, context: PipelineExecutionContext) -> Any:
    if binding.source is ChannelSource.DEFAULT:
        return None
    return context.get_channel(binding.channel_name)


def _load_geography(path: Path) -> schema.Geography:
    return readers.read_json_model(path, schema.Geography)


def _load_financial_params(path: Path) -> schema.FinancialParams:
    return readers.read_json_model(path, schema.FinancialParams)


def _load_load_profile(path: Path) -> schema.LoadProfile8760:
    return readers.read_parquet_load_profile(path, source="pipeline_entry")


_ENTRY_LOADERS: Dict[type[schema.StrictBaseModel], Any] = {
    schema.Geography: _load_geography,
    schema.FinancialParams: _load_financial_params,
    schema.LoadProfile8760: _load_load_profile,
    schema.SyncTimeGrid: lambda path: readers.read_json_model(path, schema.SyncTimeGrid),
    schema.BatteryState: lambda path: readers.read_json_model(path, schema.BatteryState),
    schema.MockForecastConfig: lambda path: readers.read_json_model(path, schema.MockForecastConfig),
    schema.GuidanceConfig: lambda path: readers.read_json_model(path, schema.GuidanceConfig),
    schema.DynamicSimConfig: lambda path: readers.read_json_model(path, schema.DynamicSimConfig),
}


def _load_price_trajectory(path: Path) -> schema.PriceTrajectory:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "series" in payload:
        series = payload["series"]
        timestamps = [
            datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
            if isinstance(item["timestamp"], str)
            else item["timestamp"]
            for item in series
        ]
        timestamps = [
            ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
            for ts in timestamps
        ]
        values = [float(item["value"]) for item in series]
        return schema.PriceTrajectory(
            time_index=timestamps,
            values=values,
            currency=payload["currency"],
            unit=payload["unit"],
            source=payload.get("source"),
        )
    return readers.read_json_model(path, schema.PriceTrajectory)


_ENTRY_LOADERS[schema.PriceTrajectory] = _load_price_trajectory
