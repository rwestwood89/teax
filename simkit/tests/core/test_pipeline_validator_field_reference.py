"""Unit tests for field reference validation in pipeline validator."""
import pytest
from pydantic import computed_field
from simkit.config.schema import StrictBaseModel
from simkit.config.pipeline_schema import (
    PipelineSpecification,
    PipelineModuleSpec,
    PipelineChannelBinding,
    ChannelSource,
)
from simkit.core.pipeline_validator import PipelineValidator, PipelineValidationError
from simkit.core.pipeline_registry import PipelineModuleRegistry, ModuleDescriptor
from simkit.core.base import ModuleBase, ModuleResult
from simkit.io.output_router import OutputRouter


# Test schema models
class TestBlanketConfig(StrictBaseModel):
    material: str
    thickness_m: float


class TestFusionParams(StrictBaseModel):
    p_fusion: float
    blanket_config: TestBlanketConfig
    optional_blanket: TestBlanketConfig | None = None
    _private_field: str = "secret"

    @computed_field
    @property
    def p_electric(self) -> float:
        return self.p_fusion * 0.4


class TestOutput(StrictBaseModel):
    result: float


# Test modules
class TestModuleWithBlanket(ModuleBase[TestBlanketConfig, TestOutput]):
    name = "test_blanket_module"
    version = "v1.0"

    def validate_and_fill_default(self, **kwargs) -> TestBlanketConfig:
        return TestBlanketConfig(**kwargs)

    def run(self, **kwargs) -> ModuleResult[TestOutput]:
        return ModuleResult(data=TestOutput(result=1.0))


class TestModuleProducingFusionParams(ModuleBase[TestBlanketConfig, TestFusionParams]):
    name = "test_fusion_producer"
    version = "v1.0"

    def validate_and_fill_default(self, **kwargs) -> TestBlanketConfig:
        return TestBlanketConfig(**kwargs)

    def run(self, **kwargs) -> ModuleResult[TestFusionParams]:
        blanket = TestBlanketConfig(material="steel", thickness_m=0.5)
        return ModuleResult(
            data=TestFusionParams(p_fusion=100.0, blanket_config=blanket)
        )


@pytest.fixture
def test_output_router():
    """Create a test output router with handlers for test types."""
    # Dummy write handler
    def dummy_handler(data, path):
        pass

    type_handlers = {
        "TestBlanketConfig": dummy_handler,
        "TestFusionParams": dummy_handler,
        "TestOutput": dummy_handler,
    }
    router = OutputRouter(type_handlers=type_handlers, in_memory=True)
    return router


@pytest.fixture
def test_registry():
    """Create a test registry with test modules."""
    def _factory(module_cls):
        def factory():
            return module_cls()
        return factory

    registry = PipelineModuleRegistry()
    registry.register(
        "TestModuleWithBlanket",
        ModuleDescriptor(
            module_type="TestModuleWithBlanket",
            factory=_factory(TestModuleWithBlanket),
            required_inputs={"blanket_config": TestBlanketConfig},
            optional_inputs={},
            outputs={"output": TestOutput},
            version="v1.0",
        ),
    )
    registry.register(
        "TestModuleProducingFusionParams",
        ModuleDescriptor(
            module_type="TestModuleProducingFusionParams",
            factory=_factory(TestModuleProducingFusionParams),
            required_inputs={"blanket_config": TestBlanketConfig},
            optional_inputs={},
            outputs={"fusion_params": TestFusionParams},
            version="v1.0",
        ),
    )
    return registry


def create_spec_with_field_reference(
    parent_channel: str,
    parent_type: str,
    field_path: str,
    expected_type: str,
) -> PipelineSpecification:
    """Helper to create a pipeline spec with a field reference."""
    modules = {
        "entry_point": PipelineModuleSpec(
            key="entry_point",
            module_type="EntryPoint",
            inputs={},
            outputs={
                "blanket_input": PipelineChannelBinding(
                    type_name="TestBlanketConfig",
                    channel_name="blanket_input",
                    source=ChannelSource.ENTRY,
                )
            },
        ),
        "producer": PipelineModuleSpec(
            key="producer",
            module_type="TestModuleProducingFusionParams",
            inputs={
                "blanket_config": PipelineChannelBinding(
                    type_name="TestBlanketConfig",
                    channel_name="blanket_input",
                    source=ChannelSource.MODULE,
                )
            },
            outputs={
                "fusion_params": PipelineChannelBinding(
                    type_name=parent_type,
                    channel_name=parent_channel,
                    source=ChannelSource.MODULE,
                )
            },
        ),
        "test_module": PipelineModuleSpec(
            key="test_module",
            module_type="TestModuleWithBlanket",
            inputs={
                "blanket_config": PipelineChannelBinding(
                    type_name=expected_type,
                    channel_name=parent_channel,
                    field_path=field_path,
                    source=ChannelSource.MODULE,
                )
            },
            outputs={
                "output": PipelineChannelBinding(
                    type_name="TestOutput",
                    channel_name="output",
                    source=ChannelSource.MODULE,
                )
            },
        ),
        "exit_point": PipelineModuleSpec(
            key="exit_point",
            module_type="ExitPoint",
            inputs={},
            outputs={
                "output": PipelineChannelBinding(
                    type_name="TestOutput",
                    channel_name="output",
                    source=ChannelSource.MODULE,
                    destination_filename="output.json",
                )
            },
        ),
    }
    return PipelineSpecification(modules=modules)


def test_validate_field_exists(test_registry, test_output_router):
    """Validation passes when field exists in parent type."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="blanket_config",
        expected_type="TestBlanketConfig",
    )

    validator = PipelineValidator(test_registry, test_output_router)
    graph = validator.validate(spec)
    assert graph is not None


def test_validate_field_not_exists(test_registry, test_output_router):
    """Validation fails when field doesn't exist, lists available fields."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="missing_field",
        expected_type="TestBlanketConfig",
    )

    validator = PipelineValidator(test_registry, test_output_router)
    with pytest.raises(PipelineValidationError) as exc_info:
        validator.validate(spec)

    assert "has no field 'missing_field'" in str(exc_info.value)
    assert "Available fields:" in str(exc_info.value)
    assert "blanket_config" in exc_info.value.details["available_fields"]


def test_validate_type_mismatch(test_registry, test_output_router):
    """Validation fails when field type doesn't match binding declaration."""
    # Create a spec where we claim blanket_config is TestOutput (wrong type)
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="blanket_config",
        expected_type="TestOutput",  # Wrong type!
    )

    validator = PipelineValidator(test_registry, test_output_router)
    # The standard type assertion catches the mismatch before field reference validation
    with pytest.raises(PipelineValidationError, match="expects type TestBlanketConfig"):
        validator.validate(spec)


def test_validate_optional_field_allowed(test_registry, test_output_router):
    """Validation passes for Optional fields (runtime will check None)."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="optional_blanket",
        expected_type="TestBlanketConfig",
    )

    validator = PipelineValidator(test_registry, test_output_router)
    graph = validator.validate(spec)
    assert graph is not None


def test_validate_private_field_rejected(test_registry, test_output_router):
    """Validation fails for private fields (leading underscore)."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="_private_field",
        expected_type="str",
    )

    validator = PipelineValidator(test_registry, test_output_router)
    with pytest.raises(PipelineValidationError, match="Cannot extract private field"):
        validator.validate(spec)


def test_validate_computed_field_rejected(test_registry, test_output_router):
    """Validation fails for computed fields in Phase 1."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="p_electric",  # @computed_field
        expected_type="float",
    )

    validator = PipelineValidator(test_registry, test_output_router)
    with pytest.raises(PipelineValidationError, match="computed field"):
        validator.validate(spec)


def test_build_channel_type_map(test_registry, test_output_router):
    """Channel type map correctly tracks all output channels."""
    # Create a simple spec with entry and module outputs
    modules = {
        "entry_point": PipelineModuleSpec(
            key="entry_point",
            module_type="EntryPoint",
            inputs={},
            outputs={
                "blanket": PipelineChannelBinding(
                    type_name="TestBlanketConfig",
                    channel_name="blanket",
                    source=ChannelSource.ENTRY,
                )
            },
        ),
        "producer": PipelineModuleSpec(
            key="producer",
            module_type="TestModuleProducingFusionParams",
            inputs={
                "blanket_config": PipelineChannelBinding(
                    type_name="TestBlanketConfig",
                    channel_name="blanket",
                    source=ChannelSource.MODULE,
                )
            },
            outputs={
                "fusion_params": PipelineChannelBinding(
                    type_name="TestFusionParams",
                    channel_name="fusion_params_out",
                    source=ChannelSource.MODULE,
                )
            },
        ),
        "exit_point": PipelineModuleSpec(
            key="exit_point",
            module_type="ExitPoint",
            inputs={},
            outputs={
                "fusion_params": PipelineChannelBinding(
                    type_name="TestFusionParams",
                    channel_name="fusion_params_out",
                    source=ChannelSource.MODULE,
                    destination_filename="fusion_params.json",
                )
            },
        ),
    }
    spec = PipelineSpecification(modules=modules)

    validator = PipelineValidator(test_registry, test_output_router)
    channel_types = validator._build_channel_type_map(spec)

    # Verify regular module outputs tracked as type objects
    assert channel_types.get("fusion_params_out") == TestFusionParams
