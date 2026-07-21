from simkit.core.registry_builder import create_registry
from simkit.core.pipeline_registry import PipelineModuleRegistry

from excl_only.modules.excl_library.area_calc import Area_CalcModule
from excl_only.modules.constraints.constraintreportaggregatormodule import ConstraintReportAggregatorModule

from excl_only.schemas.constraint_types import ConstraintEvaluation as ConstraintEvaluation, ConstraintReport as ConstraintReport
from excl_only.schemas.excl_plant_params import ExclPlantParams as ExclPlantParams

from excl_only.primitives import Float


def create_excl_only_registry() -> PipelineModuleRegistry:
    """Create registry for all modules using auto-introspection.

    Pure auto-registration pattern:
    - All modules (single-output and multi-output) use create_registry()
    - TEAx introspection handles RootModel[T] and BaseModel fields correctly

    ADR-003: Uses module_type_override to register modules with namespaced
    module types (e.g., "fusionphysics_powerbalance.AlphaNeutronSplitModule")
    while keeping Python class names unchanged (e.g., "AlphaNeutronSplitModule").
    """
    return create_registry(
        [            ConstraintReportAggregatorModule,            Area_CalcModule,        ],
        module_type_override={            ConstraintReportAggregatorModule: "constraints.ConstraintReportAggregatorModule",            Area_CalcModule: "excl_library.Area_CalcModule",        },
    )


# Custom schema types for TEAx pipeline registration
# Use with: execute_pipeline(..., custom_schema_types=CUSTOM_SCHEMA_TYPES)
CUSTOM_SCHEMA_TYPES = [    ExclPlantParams,    ConstraintEvaluation,    ConstraintReport,    Float,]
