from simkit.core.registry_builder import create_registry
from simkit.core.pipeline_registry import PipelineModuleRegistry

from zero_channel.modules.zero_library.limit_calc import Limit_CalcModule
from zero_channel.modules.zero_library.value_calc import Value_CalcModule
from zero_channel.modules.constraints.constraintreportaggregatormodule import ConstraintReportAggregatorModule
from zero_channel.modules.zero_plant.zeroplantwithinconstraintmodule import ZeroplantWithinConstraintModule

from zero_channel.schemas.constraint_types import ConstraintEvaluation as ConstraintEvaluation, ConstraintReport as ConstraintReport

from zero_channel.primitives import Float


def create_zero_channel_registry() -> PipelineModuleRegistry:
    """Create registry for all modules using auto-introspection.

    Pure auto-registration pattern:
    - All modules (single-output and multi-output) use create_registry()
    - TEAx introspection handles RootModel[T] and BaseModel fields correctly

    ADR-003: Uses module_type_override to register modules with namespaced
    module types (e.g., "fusionphysics_powerbalance.AlphaNeutronSplitModule")
    while keeping Python class names unchanged (e.g., "AlphaNeutronSplitModule").
    """
    return create_registry(
        [            ConstraintReportAggregatorModule,            Limit_CalcModule,            Value_CalcModule,            ZeroplantWithinConstraintModule,        ],
        module_type_override={            ConstraintReportAggregatorModule: "constraints.ConstraintReportAggregatorModule",            Limit_CalcModule: "zero_library.Limit_CalcModule",            Value_CalcModule: "zero_library.Value_CalcModule",            ZeroplantWithinConstraintModule: "zero_plant.ZeroplantWithinConstraintModule",        },
    )


# Custom schema types for TEAx pipeline registration
# Use with: execute_pipeline(..., custom_schema_types=CUSTOM_SCHEMA_TYPES)
CUSTOM_SCHEMA_TYPES = [    ConstraintEvaluation,    ConstraintReport,    Float,]
