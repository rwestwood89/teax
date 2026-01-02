from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Dict

import pytest
import yaml

from simkit.config.pipeline_schema import (
    ChannelSource,
    PipelineChannelBinding,
    PipelineModuleSpec,
    PipelineSpecification,
)
from simkit.config import battery_schema
from simkit.core.pipeline_registry import ModuleDescriptor, PipelineModuleRegistry
from simkit.core.pipeline_validator import PipelineValidationError, PipelineValidator
from simkit.core.base import ModuleBase
from simkit.io.readers import read_pipeline_spec
from simkit.io.output_router import OutputRouter, WriteHandler, create_default_router
from simkit.io import writers


def _write_spec(tmp_path: Path, payload: Dict) -> Path:
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


@pytest.fixture
def registry() -> PipelineModuleRegistry:
    return PipelineModuleRegistry.from_static_modules()


@pytest.fixture
def output_router() -> OutputRouter:
    return create_default_router()


def test_registry_includes_synchronous_sim(registry: PipelineModuleRegistry):
    descriptor = registry.get("SynchronousSim")
    assert descriptor.module_type == "SynchronousSim"
    assert sorted(descriptor.outputs) == [
        "forecasts",
        "guidances",
        "synchronous_sim",
        "telemetry",
    ]


def test_pipeline_dag_builder_orders_modules(sample_pipeline_yaml_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    graph = PipelineValidator(registry, output_router).validate(spec)
    order = list(graph.topological_order)

    assert order[0] == "entry_point"
    assert order.index("exit_point") > order.index("project_analyzer")


def _clone_spec(spec: PipelineSpecification) -> PipelineSpecification:
    return PipelineSpecification.model_construct(
        modules=dict(spec.modules),
        metadata=spec.metadata,
        source_path=spec.source_path,
    )


def _clone_module(module: PipelineModuleSpec) -> PipelineModuleSpec:
    return PipelineModuleSpec.model_construct(
        key=module.key,
        module_type=module.module_type,
        inputs=dict(module.inputs),
        outputs=dict(module.outputs),
    )


def test_validator_rejects_unregistered_module(sample_pipeline_spec: Dict, tmp_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    broken_spec = deepcopy(sample_pipeline_spec)
    broken_spec["modules"]["rate_data"]["module_type"] = "UnknownModule"
    path = _write_spec(tmp_path, broken_spec)
    spec = read_pipeline_spec(path)

    with pytest.raises(PipelineValidationError, match="not registered"):  # _resolve_descriptor() raises
        PipelineValidator(registry, output_router).validate(spec)


def test_validator_rejects_missing_dependency(sample_pipeline_yaml_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    modules = dict(spec.modules)
    project_analyzer = _clone_module(modules["project_analyzer"])
    broken_inputs = dict(project_analyzer.inputs)
    broken_inputs["rate_info"] = PipelineChannelBinding(
        type_name="RateInfo",
        channel_name="missing_rate",
        source=ChannelSource.MODULE,
    )
    modules["project_analyzer"] = PipelineModuleSpec.model_construct(
        key=project_analyzer.key,
        module_type=project_analyzer.module_type,
        inputs=broken_inputs,
        outputs=project_analyzer.outputs,
    )
    broken_spec = PipelineSpecification.model_construct(
        modules=modules,
        metadata=spec.metadata,
        source_path=spec.source_path,
    )

    with pytest.raises(PipelineValidationError, match="Unresolved channels"):
        PipelineValidator(registry, output_router).validate(broken_spec)  # missing_channels in PipelineDagBuilder.build()


def test_validator_rejects_output_field_mismatch(sample_pipeline_yaml_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    broken_spec = _clone_spec(spec)
    rate_module = _clone_module(broken_spec.modules["rate_data"])
    broken_spec.modules["rate_data"] = PipelineModuleSpec.model_construct(
        key=rate_module.key,
        module_type=rate_module.module_type,
        inputs=rate_module.inputs,
        outputs={
            "rate_info": rate_module.outputs["rate_info"],
            "extra": PipelineChannelBinding(
                type_name="RateInfo",
                channel_name="rate_info_extra",
                source=ChannelSource.MODULE,
            ),
        },
    )

    with pytest.raises(PipelineValidationError, match="Output bindings do not match"):
        PipelineValidator(registry, output_router).validate(broken_spec)


def test_validator_rejects_output_type_mismatch(sample_pipeline_yaml_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    broken_spec = _clone_spec(spec)
    rate_module = _clone_module(broken_spec.modules["rate_data"])
    broken_spec.modules["rate_data"] = PipelineModuleSpec.model_construct(
        key=rate_module.key,
        module_type=rate_module.module_type,
        inputs=rate_module.inputs,
        outputs={
            "rate_info": PipelineChannelBinding(
                type_name="Geography",
                channel_name="rate_info",
                source=ChannelSource.MODULE,
            )
        },
    )

    with pytest.raises(PipelineValidationError, match="expects type"):
        PipelineValidator(registry, output_router).validate(broken_spec)


def test_validator_rejects_missing_required_input(sample_pipeline_yaml_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    broken_spec = _clone_spec(spec)
    perf_module = _clone_module(broken_spec.modules["simple_performance_sim"])
    perf_module.inputs.pop("battery")
    broken_spec.modules["simple_performance_sim"] = perf_module

    with pytest.raises(PipelineValidationError, match="Missing required input"):
        PipelineValidator(registry, output_router).validate(broken_spec)


def test_validator_requires_optional_binding(sample_pipeline_yaml_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    broken_spec = _clone_spec(spec)
    analyzer = _clone_module(broken_spec.modules["project_analyzer"])
    analyzer.inputs.pop("financial_params")
    broken_spec.modules["project_analyzer"] = analyzer

    with pytest.raises(PipelineValidationError, match="Optional inputs must be explicitly bound"):
        PipelineValidator(registry, output_router).validate(broken_spec)


def test_validator_rejects_default_for_required_input(sample_pipeline_yaml_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    broken_spec = _clone_spec(spec)
    perf_module = _clone_module(broken_spec.modules["simple_performance_sim"])
    perf_module.inputs["battery"] = PipelineChannelBinding(
        type_name=None,
        channel_name="battery_default",
        source=ChannelSource.DEFAULT,
    )
    broken_spec.modules["simple_performance_sim"] = perf_module

    with pytest.raises(PipelineValidationError, match="Default binding supplied for a required input"):
        PipelineValidator(registry, output_router).validate(broken_spec)


def test_validator_rejects_unknown_input(sample_pipeline_yaml_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    broken_spec = _clone_spec(spec)
    rate_module = _clone_module(broken_spec.modules["rate_data"])
    rate_module.inputs["unknown"] = PipelineChannelBinding(
        type_name="Geography",
        channel_name="geo",
        source=ChannelSource.MODULE,
    )
    broken_spec.modules["rate_data"] = rate_module

    with pytest.raises(PipelineValidationError, match="Specification declares inputs not defined"):
        PipelineValidator(registry, output_router).validate(broken_spec)


def test_validator_rejects_self_dependency(tmp_path: Path):
    registry = PipelineModuleRegistry()
    registry.register(
        "Echo",
        ModuleDescriptor(
            module_type="Echo",
            factory=lambda: _StubModule(),
            required_inputs={"payload": battery_schema.Geography},
            optional_inputs={},
            outputs={"payload": battery_schema.Geography},
            version="v0",
        ),
    )
    router = create_default_router()
    router.register_handler("Geography", WriteHandler(fn=writers.write_json_model, extension=".json"))
    payload = {
        "modules": {
            "entry_point": {
                "module_type": "EntryPoint",
                "inputs": {"seed": "Geography input_configs/geographies/us_ca_pge.json"},
                "outputs": {"seed": "Geography seed"},
            },
            "echo": {
                "module_type": "Echo",
                "inputs": {"payload": "Geography payload"},
                "outputs": {"payload": "Geography payload"},
            },
            "exit_point": {
                "module_type": "ExitPoint",
                "inputs": {
                    "seed": "Geography seed",
                    "payload": "Geography payload",
                },
                "outputs": {"payload": "Geography payload.json"},
            },
        }
    }
    spec = read_pipeline_spec(_write_spec(tmp_path, payload))

    with pytest.raises(PipelineValidationError, match="cannot consume its own channel"):
        PipelineValidator(registry, router).validate(spec)


def test_validator_rejects_cycle(tmp_path: Path):
    registry = PipelineModuleRegistry()
    registry.register(
        "StubA",
        ModuleDescriptor(
            module_type="StubA",
            factory=lambda: _StubModule(),
            required_inputs={"foo": battery_schema.Geography, "baz": battery_schema.Geography},
            optional_inputs={},
            outputs={"bar": battery_schema.Geography},
            version="v0",
        ),
    )
    registry.register(
        "StubB",
        ModuleDescriptor(
            module_type="StubB",
            factory=lambda: _StubModule(),
            required_inputs={"bar": battery_schema.Geography},
            optional_inputs={},
            outputs={"baz": battery_schema.Geography, "payload": battery_schema.Geography},
            version="v0",
        ),
    )
    router = create_default_router()
    router.register_handler("Geography", WriteHandler(fn=writers.write_json_model, extension=".json"))

    payload = {
        "modules": {
            "entry_point": {
                "module_type": "EntryPoint",
                "inputs": {"foo": "Geography input_configs/geographies/us_ca_pge.json"},
            },
            "stub_a": {
                "module_type": "StubA",
                "inputs": {
                    "foo": "Geography foo",
                    "baz": "Geography baz",
                },
                "outputs": {"bar": "Geography bar"},
            },
            "stub_b": {
                "module_type": "StubB",
                "inputs": {"bar": "Geography bar"},
                "outputs": {
                    "baz": "Geography baz",
                    "payload": "Geography payload",
                },
            },
            "exit_point": {
                "module_type": "ExitPoint",
                "outputs": {
                    "payload": "Geography payload.json",
                },
            },
        }
    }
    path = _write_spec(tmp_path, payload)
    spec = read_pipeline_spec(path)

    with pytest.raises(PipelineValidationError, match="cycle"):
        PipelineValidator(registry, router).validate(spec)  # CycleError in PipelineDagBuilder.build() from the graphlib package


def test_validator_requires_exit_filenames(sample_pipeline_yaml_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter) -> None:
    spec = read_pipeline_spec(sample_pipeline_yaml_path)
    exit_module = spec.modules["exit_point"].model_copy()
    broken_outputs = dict(exit_module.outputs)
    broken_outputs["telemetry"] = broken_outputs["telemetry"].model_copy(
        update={"destination_filename": None}
    )
    modules = dict(spec.modules)
    modules["exit_point"] = exit_module.model_copy(update={"outputs": broken_outputs})
    broken_spec = PipelineSpecification.model_construct(
        modules=modules,
        metadata=spec.metadata,
        source_path=spec.source_path,
    )

    with pytest.raises(PipelineValidationError, match="destination filenames"):
        PipelineValidator(registry, output_router).validate(broken_spec)


def test_validator_rejects_duplicate_entry(tmp_path: Path, registry: PipelineModuleRegistry, output_router: OutputRouter):
    entry_binding = PipelineChannelBinding(
        type_name="Geography",
        channel_name="foo",
        source=ChannelSource.ENTRY,
    )
    entry = PipelineModuleSpec(
        key="entry_point",
        module_type="EntryPoint",
        inputs={"foo": PipelineChannelBinding(
            type_name="Geography",
            channel_name="foo",
            source=ChannelSource.ENTRY,
            artifact_path=Path("input_configs/geographies/us_ca_pge.json"),
        )},
        outputs={"foo": entry_binding},
    )
    entry_two = PipelineModuleSpec(
        key="entry_point_alt",
        module_type="EntryPoint",
        inputs={"bar": PipelineChannelBinding(
            type_name="Geography",
            channel_name="bar",
            source=ChannelSource.ENTRY,
            artifact_path=Path("input_configs/geographies/us_ca_pge.json"),
        )},
        outputs={"bar": PipelineChannelBinding(
            type_name="Geography",
            channel_name="bar",
            source=ChannelSource.ENTRY,
        )},
    )
    exit_module = PipelineModuleSpec(
        key="exit_point",
        module_type="ExitPoint",
        inputs={},
        outputs={"foo": PipelineChannelBinding(
            type_name="Geography",
            channel_name="foo",
            source=ChannelSource.MODULE,
            destination_filename="foo.json",
        )},
    )

    spec = PipelineSpecification.model_construct(
        modules={
            "entry_point": entry,
            "entry_point_alt": entry_two,
            "exit_point": exit_module,
        }
    )

    with pytest.raises(PipelineValidationError, match="EntryPoint"):
        PipelineValidator(registry, output_router).validate(spec)


class _StubModule(ModuleBase):  # pragma: no cover - execution delegated to later phases
    name = "stub"
    version = "v0"

    def validate_and_fill_default(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    def run(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError
