from simkit.core.registry_builder import create_registry
from simkit.core.pipeline_registry import PipelineModuleRegistry

from constraint_free.modules.constraint_free_library.area_calc import Area_CalcModule

from constraint_free.schemas.constraint_free_plant_params import ConstraintFreePlantParams as ConstraintFreePlantParams

from constraint_free.primitives import Float


def create_constraint_free_registry() -> PipelineModuleRegistry:
    """Create registry for all modules using auto-introspection.

    Pure auto-registration pattern:
    - All modules (single-output and multi-output) use create_registry()
    - TEAx introspection handles RootModel[T] and BaseModel fields correctly

    ADR-003: Uses module_type_override to register modules with namespaced
    module types (e.g., "fusionphysics_powerbalance.AlphaNeutronSplitModule")
    while keeping Python class names unchanged (e.g., "AlphaNeutronSplitModule").
    """
    return create_registry(
        [            Area_CalcModule,        ],
        module_type_override={            Area_CalcModule: "constraint_free_library.Area_CalcModule",        },
    )


# Custom schema types for TEAx pipeline registration
# Use with: execute_pipeline(..., custom_schema_types=CUSTOM_SCHEMA_TYPES)
CUSTOM_SCHEMA_TYPES = [    ConstraintFreePlantParams,    Float,]
