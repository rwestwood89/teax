"""Validation utilities tying pipeline specs to registry metadata."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from ..config import schema
from ..config.pipeline_schema import (
    ChannelSource,
    PipelineChannelBinding,
    PipelineModuleSpec,
    PipelineSpecification,
)
from .pipeline_graph import PipelineDagBuilder, PipelineGraph, PipelineGraphError
from .pipeline_registry import ModuleDescriptor, PipelineModuleRegistry


class PipelineValidationError(Exception):
    """Raised when a pipeline specification fails validation."""

    def __init__(self, message: str, module: str | None = None, details: Dict[str, object] | None = None):
        super().__init__(message)
        self.module = module
        self.details = details or {}


@dataclass
class _ValidationContext:
    registry: PipelineModuleRegistry


class PipelineValidator:
    """Validates a pipeline specification against the module registry."""

    def __init__(self, registry: PipelineModuleRegistry) -> None:
        self._registry = registry
        self._builder = PipelineDagBuilder()

    def validate(self, spec: PipelineSpecification) -> PipelineGraph:
        self._assert_entry_exit(spec)
        for module in spec.modules.values():
            if module.is_entry:
                continue
            if module.is_exit:
                self._validate_exit_module(module)
                continue
            descriptor = self._resolve_descriptor(module)
            self._validate_outputs(module, descriptor)  # Make sure 1:1 mapping for output fields and types between registry and yaml
            self._validate_inputs(module, descriptor) # Similar validation, but allowing for optional inputs
        try:
            graph = self._builder.build(spec)
        except PipelineGraphError as exc:
            raise PipelineValidationError(str(exc)) from exc
        return graph

    def _assert_entry_exit(self, spec: PipelineSpecification) -> None:
        entries = [m for m in spec.modules.values() if m.is_entry]
        exits = [m for m in spec.modules.values() if m.is_exit]
        if len(entries) != 1:
            raise PipelineValidationError(
                f"Expected exactly one EntryPoint module, found {len(entries)}",
                details={"entries": [m.key for m in entries]},
            )
        if len(exits) != 1:
            raise PipelineValidationError(
                f"Expected exactly one ExitPoint module, found {len(exits)}",
                details={"exits": [m.key for m in exits]},
            )

    def _resolve_descriptor(self, module: PipelineModuleSpec) -> ModuleDescriptor:
        module_type = module.module_type
        if not self._registry.has(module_type):
            raise PipelineValidationError(
                f"Module type '{module_type}' is not registered",
                module=module.key,
            )
        return self._registry.get(module_type)

    def _validate_exit_module(self, module: PipelineModuleSpec) -> None:
        if not module.outputs:
            raise PipelineValidationError(
                "ExitPoint module must declare at least one output",
                module=module.key,
            )
        seen_filenames: set[str] = set()
        for field, binding in module.outputs.items():
            if binding.destination_filename is None:
                raise PipelineValidationError(
                    "ExitPoint output bindings must declare destination filenames",
                    module=module.key,
                    details={"output": field},
                )
            if binding.channel_name != field:
                raise PipelineValidationError(
                    "ExitPoint output channel names must match their binding keys",
                    module=module.key,
                    details={"output": field, "channel": binding.channel_name},
                )
            if binding.destination_filename in seen_filenames:
                raise PipelineValidationError(
                    "ExitPoint outputs declare duplicate destination filenames",
                    module=module.key,
                    details={"filename": binding.destination_filename},
                )
            seen_filenames.add(binding.destination_filename)
            type_name = binding.type_name
            if type_name is None:
                raise PipelineValidationError(
                    "ExitPoint outputs must declare a type",
                    module=module.key,
                    details={"output": field},
                )
            if not hasattr(schema, type_name):
                raise PipelineValidationError(
                    "ExitPoint output references unknown schema type",
                    module=module.key,
                    details={"output": field, "type": type_name},
                )

    def _validate_outputs(self, module: PipelineModuleSpec, descriptor: ModuleDescriptor) -> None:
        expected = set(descriptor.outputs.keys())
        actual = set(module.outputs.keys())
        if expected != actual:
            raise PipelineValidationError(
                "Output bindings do not match registry metadata",
                module=module.key,
                details={"expected": sorted(expected), "actual": sorted(actual)},
            )
        for field, binding in module.outputs.items():
            expected_type = descriptor.outputs[field]
            self._assert_type(binding, expected_type, module.key, field, "output")

    def _validate_inputs(self, module: PipelineModuleSpec, descriptor: ModuleDescriptor) -> None:
        expected_inputs = set(descriptor.required_inputs) | set(descriptor.optional_inputs)
        actual_inputs = set(module.inputs.keys())
        missing_required = set(descriptor.required_inputs) - actual_inputs
        if missing_required:
            raise PipelineValidationError(
                "Missing required input bindings",
                module=module.key,
                details={"missing": sorted(missing_required)},
            )
        missing_optional = set(descriptor.optional_inputs) - actual_inputs
        if missing_optional:
            raise PipelineValidationError(
                "Optional inputs must be explicitly bound or defaulted",
                module=module.key,
                details={"missing_optional": sorted(missing_optional)},
            )

        unknown_inputs = actual_inputs - expected_inputs
        if unknown_inputs:
            raise PipelineValidationError(
                "Specification declares inputs not defined by registry",
                module=module.key,
                details={"unknown": sorted(unknown_inputs)},
            )

        for field, binding in module.inputs.items():
            expected_type = (
                descriptor.required_inputs.get(field)
                or descriptor.optional_inputs.get(field)
            )
            if expected_type is None:
                continue  # already handled unknown inputs
            if binding.source is ChannelSource.DEFAULT:
                if field not in descriptor.optional_inputs:
                    raise PipelineValidationError(
                        "Default binding supplied for a required input",
                        module=module.key,
                        details={"input": field},
                    )
            else:
                self._assert_type(binding, expected_type, module.key, field, "input")

    def _assert_type(
        self,
        binding: PipelineChannelBinding,
        expected_type: type[schema.StrictBaseModel],
        module_key: str,
        field: str,
        binding_kind: str,
    ) -> None:
        if binding.type_name is None:
            return
        expected_name = expected_type.__name__
        if binding.type_name != expected_name:
            raise PipelineValidationError(
                f"{binding_kind.capitalize()} '{field}' expects type {expected_name}, "
                f"but binding declares {binding.type_name}",
                module=module_key,
                details={"field": field, "expected": expected_name, "declared": binding.type_name},
            )
