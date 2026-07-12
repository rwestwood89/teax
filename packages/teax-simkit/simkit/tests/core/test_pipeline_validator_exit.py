"""ExitPoint validation tests for persistence type contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import RootModel

from simkit.config.pipeline_schema import (
    ChannelSource,
    PipelineChannelBinding,
    PipelineModuleSpec,
    PipelineSpecification,
)
from simkit.core.base import ModuleBase, ModuleResult
from simkit.core.pipeline import execute_pipeline
from simkit.core.pipeline_registry import ModuleDescriptor, PipelineModuleRegistry
from simkit.core.pipeline_validator import PipelineValidationError, PipelineValidator
from simkit.core.registry_builder import create_registry
from simkit.io.output_router import OutputRouter, WriteHandler, create_default_router
from simkit.io.writers import write_json_payload
from simkit.tests.core.toy_modules import ToyInput


class ObservableProducerModule(ModuleBase[ToyInput, RootModel[float]]):
    """Producer whose run count proves validation happens before execution."""

    name = "observable_producer"
    version = "v1.0"
    run_count = 0

    def validate_and_fill_default(self, value: float) -> ToyInput:
        return ToyInput(value=value)

    def run(self, value: float) -> ModuleResult[RootModel[float]]:
        type(self).run_count += 1
        validated = self.validate_and_fill_default(value)
        return ModuleResult(data=RootModel[float](validated.value))


def _registry_with_output_type(output_type: type) -> PipelineModuleRegistry:
    registry = PipelineModuleRegistry()
    registry.register(
        "ScalarProducer",
        ModuleDescriptor(
            module_type="ScalarProducer",
            factory=lambda: object(),
            required_inputs={},
            optional_inputs={},
            outputs={"value": output_type},
            version="v1.0",
        ),
    )
    return registry


def _spec_with_exit_declaration(
    producer_type_name: str,
    exit_type_name: str,
) -> PipelineSpecification:
    return PipelineSpecification(
        modules={
            "entry": PipelineModuleSpec(
                key="entry",
                module_type="EntryPoint",
            ),
            "producer": PipelineModuleSpec(
                key="producer",
                module_type="ScalarProducer",
                outputs={
                    "value": PipelineChannelBinding(
                        type_name=producer_type_name,
                        channel_name="value",
                        source=ChannelSource.MODULE,
                    )
                },
            ),
            "exit": PipelineModuleSpec(
                key="exit",
                module_type="ExitPoint",
                outputs={
                    "value": PipelineChannelBinding(
                        type_name=exit_type_name,
                        channel_name="value",
                        source=ChannelSource.MODULE,
                        destination_filename="value.json",
                    )
                },
            ),
        }
    )


@pytest.mark.parametrize(
    ("producer_type", "type_name"),
    ((float, "float"), (RootModel[float], "RootModel[float]")),
)
def test_exit_binding_accepts_truthful_producer_type(
    producer_type: type,
    type_name: str,
):
    validator = PipelineValidator(
        _registry_with_output_type(producer_type),
        create_default_router(),
    )

    graph = validator.validate(_spec_with_exit_declaration(type_name, type_name))

    assert graph is not None


@pytest.mark.parametrize(
    ("producer_type", "producer_name", "declared_name"),
    (
        (float, "float", "bool"),
        (RootModel[float], "RootModel[float]", "float"),
        (float, "float", "RootModel[float]"),
    ),
)
def test_exit_binding_rejects_resolvable_type_mismatch(
    producer_type: type,
    producer_name: str,
    declared_name: str,
):
    validator = PipelineValidator(
        _registry_with_output_type(producer_type),
        create_default_router(),
    )

    with pytest.raises(
        PipelineValidationError,
        match="ExitPoint output type does not match producer channel type",
    ) as exc_info:
        validator.validate(_spec_with_exit_declaration(producer_name, declared_name))

    assert exc_info.value.details == {
        "output": "value",
        "declared_type": declared_name,
        "producer_type": producer_name,
        "hint": f"Declare the output as '{producer_name}' to match channel 'value'",
    }


def test_exit_binding_skips_type_check_when_producer_type_is_unresolvable():
    router = OutputRouter(
        {
            "DeclaredOutput": WriteHandler(
                fn=write_json_payload,
                extension=".json",
            )
        }
    )
    spec = PipelineSpecification(
        modules={
            "entry": PipelineModuleSpec(
                key="entry",
                module_type="EntryPoint",
                outputs={
                    "value": PipelineChannelBinding(
                        type_name="UnregisteredInput",
                        channel_name="value",
                        source=ChannelSource.ENTRY,
                    )
                },
            ),
            "exit": PipelineModuleSpec(
                key="exit",
                module_type="ExitPoint",
                outputs={
                    "value": PipelineChannelBinding(
                        type_name="DeclaredOutput",
                        channel_name="value",
                        source=ChannelSource.MODULE,
                        destination_filename="value.json",
                    )
                },
            ),
        }
    )

    graph = PipelineValidator(PipelineModuleRegistry(), router).validate(spec)

    assert graph is not None


def test_unknown_exit_type_fails_before_any_module_runs(
    tmp_path: Path,
):
    input_path = tmp_path / "input.json"
    input_path.write_text('{"value": 3.0}', encoding="utf-8")
    spec_path = tmp_path / "unknown_exit.yaml"
    spec_path.write_text(
        f"""
modules:
  entry:
    module_type: EntryPoint
    inputs:
      input_value: ToyInput {input_path}
  producer:
    module_type: ObservableProducerModule
    inputs:
      value: float input_value.value
    outputs:
      root: RootModel[float] result
  exit:
    module_type: ExitPoint
    outputs:
      result: UnknownOutput result.json
""".strip(),
        encoding="utf-8",
    )
    ObservableProducerModule.run_count = 0

    with pytest.raises(
        PipelineValidationError,
        match="ExitPoint output type has no registered write handler",
    ):
        execute_pipeline(
            spec_path,
            output_dir=tmp_path / "outputs",
            registry=create_registry([ObservableProducerModule]),
            custom_schema_types=[ToyInput],
        )

    assert ObservableProducerModule.run_count == 0
