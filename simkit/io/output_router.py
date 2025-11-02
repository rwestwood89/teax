"""Output routing infrastructure for ExitPoint artifacts."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, MutableMapping

from ..config import environment, schema
from ..config.pipeline_schema import PipelineChannelBinding
from . import writers


class OutputRouterError(Exception):
    """Raised when output routing fails due to configuration or IO issues."""


@dataclass(frozen=True)
class WriteHandler:
    fn: Callable[[Any, Path], Path]
    extension: str


@dataclass(frozen=True)
class OutputRouterResult:
    run_dir: Path
    manifest: schema.RunManifest
    manifest_path: Path


class OutputRouter:
    """Routes ExitPoint outputs to filesystem artifacts and records manifests."""

    def __init__(
        self,
        type_handlers: Mapping[str, WriteHandler],
        *,
        manifest_writer: Callable[[Any, Path], Path] | None = None,
    ) -> None:
        self._type_handlers: Dict[str, WriteHandler] = dict(type_handlers)
        self._manifest_writer = manifest_writer or writers.write_json_payload

    def register_handler(self, type_name: str, handler: WriteHandler) -> None:
        self._type_handlers[type_name] = handler

    def has_handler(self, type_name: str) -> bool:
        return type_name in self._type_handlers

    def write_outputs(
        self,
        exit_bindings: Mapping[str, PipelineChannelBinding],
        channel_values: Mapping[str, Any],
        *,
        base_output_dir: Path | None = None,
        run_name: str | None = None,
        pipeline_metadata: object | None = None,
    ) -> OutputRouterResult:
        resolution = environment.resolve_output_dir(preferred=base_output_dir, run_name=run_name)
        run_dir, short_id = self._prepare_run_directory(resolution.base_dir, resolution.run_name)

        artifacts: list[schema.RunArtifactRecord] = []
        used_filenames: set[str] = set()

        for alias, binding in exit_bindings.items():
            destination = binding.destination_filename
            if not destination:
                raise OutputRouterError(f"ExitPoint binding '{alias}' is missing a destination filename")
            if destination in used_filenames:
                raise OutputRouterError(f"Destination filename '{destination}' declared more than once")
            used_filenames.add(destination)

            type_name = binding.type_name
            if type_name is None:
                raise OutputRouterError(f"ExitPoint binding '{alias}' is missing a type declaration")

            handler = self._type_handlers.get(type_name)
            if handler is None:
                raise OutputRouterError(f"No writer registered for type '{type_name}'")
            if handler.extension and not destination.endswith(handler.extension):
                raise OutputRouterError(
                    f"Destination filename '{destination}' does not match expected extension '{handler.extension}'"
                )

            channel_name = binding.channel_name
            payload = channel_values.get(channel_name)
            if payload is None:
                artifacts.append(
                    schema.RunArtifactRecord(
                        channel=channel_name,
                        type_name=type_name,
                        relative_path=None,
                        produced=False,
                    )
                )
                continue

            target_path = run_dir / destination
            handler.fn(payload, target_path)

            artifacts.append(
                schema.RunArtifactRecord(
                    channel=channel_name,
                    type_name=type_name,
                    relative_path=destination,
                    produced=True,
                )
            )

        metadata_payload = None
        if pipeline_metadata is not None:
            if hasattr(pipeline_metadata, "model_dump"):
                metadata_payload = pipeline_metadata.model_dump()
            elif isinstance(pipeline_metadata, Mapping):
                metadata_payload = dict(pipeline_metadata)
            else:
                raise OutputRouterError(
                    "pipeline_metadata must be a mapping or provide a model_dump() method"
                )

        manifest = schema.RunManifest(
            run_name=resolution.run_name,
            run_directory=run_dir.name,
            base_output_dir=str(resolution.base_dir),
            short_id=short_id,
            metadata=metadata_payload,
            artifacts=artifacts,
        )
        manifest_path = run_dir / "manifest.json"
        self._manifest_writer(manifest, manifest_path)

        return OutputRouterResult(run_dir=run_dir, manifest=manifest, manifest_path=manifest_path)

    def _prepare_run_directory(self, base_dir: Path, run_name: str) -> tuple[Path, str]:
        base_dir.mkdir(parents=True, exist_ok=True)
        short_id = uuid.uuid4().hex[:8]
        run_dir = base_dir / f"{run_name}-{short_id}"
        while run_dir.exists():  # Extremely unlikely, but rotate if collision occurs
            short_id = uuid.uuid4().hex[:8]
            run_dir = base_dir / f"{run_name}-{short_id}"
        run_dir.mkdir(parents=False, exist_ok=False)
        return run_dir, short_id


def create_default_router() -> OutputRouter:
    """Create an OutputRouter populated with default schema type handlers."""

    handlers: MutableMapping[str, WriteHandler] = {
        schema.RateInfo.__name__: WriteHandler(fn=writers.write_json_model, extension=".json"),
        schema.BatteryConfig.__name__: WriteHandler(fn=writers.write_json_model, extension=".json"),
        schema.CostBreakdown.__name__: WriteHandler(fn=writers.write_json_model, extension=".json"),
        schema.FinancialResults.__name__: WriteHandler(fn=writers.write_json_model, extension=".json"),
        schema.BatteryTelemetry8760.__name__: WriteHandler(fn=writers.write_parquet_telemetry, extension=".parquet"),
        schema.MockForecastSeries.__name__: WriteHandler(
            fn=writers.write_mock_forecast_series,
            extension=".json",
        ),
        schema.SyncGuidanceSeries.__name__: WriteHandler(
            fn=writers.write_sync_guidance_series,
            extension=".json",
        ),
        schema.SyncTelemetrySeries.__name__: WriteHandler(
            fn=writers.write_sync_telemetry_series,
            extension=".parquet",
        ),
    }
    return OutputRouter(type_handlers=handlers)
