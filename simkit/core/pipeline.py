"""Async demo pipeline orchestrating module execution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Mapping

from dataclasses import replace

from ..config import schema
from ..config.pipeline_schema import PipelineSpecification
from ..io import readers
from ..io.output_router import create_default_router
from .pipeline_executor import PipelineExecutionContext, RunResult, SerialPipelineExecutor
from .pipeline_registry import PipelineModuleRegistry
from .pipeline_validator import PipelineValidationError

if TYPE_CHECKING:
    from ..io.output_router import OutputRouter

def _config_hash(payload: Dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def entry_point_validate(spec_path: str | Path) -> PipelineSpecification:
    """Normalize and load the pipeline specification."""

    resolved = Path(spec_path).expanduser()
    if resolved.is_dir():
        raise ValueError("Pipeline specification path must point to a file")
    if not resolved.exists():
        raise FileNotFoundError(f"Pipeline specification missing: {resolved}")
    specification = readers.read_pipeline_spec(resolved)
    if specification.source_path is None:
        specification = specification.model_copy(update={"source_path": resolved})
    return specification


def _build_pipeline_metadata(specification: PipelineSpecification) -> schema.PipelineRunMetadata:
    spec_metadata = specification.metadata
    spec_path_str = str(specification.source_path) if specification.source_path else ""
    return schema.PipelineRunMetadata(
        spec_path=spec_path_str,
        run_description=spec_metadata.run_description if spec_metadata else None,
        output_folder=spec_metadata.output_folder if spec_metadata else None,
    )


def _build_provenance(
    specification: PipelineSpecification,
    module_versions: Mapping[str, str],
    run_metadata: schema.PipelineRunMetadata,
) -> schema.Provenance:
    config_payload = specification.model_dump(mode="json")
    return schema.Provenance(
        config_hash=_config_hash(config_payload),
        module_versions=dict(module_versions),
        notes=run_metadata.run_description or "Async demo pipeline v0.1",
        output_folder=run_metadata.output_folder,
    )


def execute_pipeline(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
    registry: PipelineModuleRegistry | None = None,
    output_router: OutputRouter | None = None,
) -> RunResult:
    """Execute pipeline with optional custom module registry and output router.

    Args:
        spec_path: Path to pipeline YAML specification
        output_dir: Optional output directory (defaults to temp dir)
        registry: Optional custom module registry. If None, uses built-in TEAx modules.
        output_router: Optional custom output router. If None, uses default router with
                      built-in schema handlers.

    Returns:
        RunResult with execution outputs, metadata, and provenance

    Example:
        >>> # Execute with built-in modules and schemas (backward compatible)
        >>> result = execute_pipeline("demo_pipeline.yaml", "outputs/")

        >>> # Execute with custom modules and schemas
        >>> from simkit.core.registry_builder import create_registry
        >>> from simkit.io.output_router import create_output_router_with_json_schemas
        >>>
        >>> registry = create_registry([MyCustomModule])
        >>> router = create_output_router_with_json_schemas(["MyCustomSchema"])
        >>> result = execute_pipeline(
        ...     "custom_pipeline.yaml",
        ...     "outputs/",
        ...     registry=registry,
        ...     output_router=router,
        ... )
    """
    specification = entry_point_validate(spec_path)

    # Use custom registry if provided, otherwise default to builtins
    if registry is None:
        registry = PipelineModuleRegistry.from_static_modules()

    # Use custom router if provided, otherwise default to builtins
    router = output_router or create_default_router()
    executor = SerialPipelineExecutor(registry, output_router=router)
    context = PipelineExecutionContext(registry)

    graph = executor.build_graph(specification)
    try:
        metadata = specification.metadata
        run_name_hint = None
        if metadata and metadata.output_folder:
            run_name_hint = metadata.output_folder
        elif metadata and metadata.run_description:
            run_name_hint = metadata.run_description
        elif specification.source_path is not None:
            run_name_hint = specification.source_path.stem

        base_output_dir = Path(output_dir) if output_dir is not None else None

        run_result = executor.run(
            graph,
            context,
            base_output_dir=base_output_dir,
            run_name=run_name_hint,
            pipeline_metadata=metadata,
        )
        produced_outputs = run_result.outputs
    except PipelineValidationError as exc:  # pragma: no cover
        raise RuntimeError(f"Pipeline execution failed: {exc}") from exc

    # TODO: I think we may want to just have the entire spec somewhere here
    pipeline_metadata = _build_pipeline_metadata(specification)
    provenance = _build_provenance(specification, run_result.module_versions, pipeline_metadata)
    # Also may want to dump these json files to the output directory as well
    return replace(
        run_result,
        pipeline_metadata=pipeline_metadata,
        provenance=provenance,
    )
