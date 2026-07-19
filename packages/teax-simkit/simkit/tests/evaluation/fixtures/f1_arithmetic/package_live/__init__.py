from simkit.core.registry_builder import create_registry
from simkit.core.pipeline_registry import PipelineModuleRegistry

from f1_arithmetic_constraints.modules.constraints.constraintreportaggregatormodule import ConstraintReportAggregatorModule
from f1_arithmetic_constraints.modules.toy_plant.fixturef1divisioncheckconstraintmodule import FixtureF1DivisionCheckConstraintModule
from f1_arithmetic_constraints.modules.toy_plant.fixturef2powercheckconstraintmodule import FixtureF2PowerCheckConstraintModule
from f1_arithmetic_constraints.modules.toy_plant.fixturef3nestedcheckconstraintmodule import FixtureF3NestedCheckConstraintModule

from f1_arithmetic_constraints.schemas.constraint_types import ConstraintEvaluation as ConstraintEvaluation, ConstraintReport as ConstraintReport
from f1_arithmetic_constraints.schemas.toy_plant_params import ToyPlantParams as ToyPlantParams



def create_f1_arithmetic_constraints_registry() -> PipelineModuleRegistry:
    """Create registry for all modules using auto-introspection.

    Pure auto-registration pattern:
    - All modules (single-output and multi-output) use create_registry()
    - TEAx introspection handles RootModel[T] and BaseModel fields correctly

    ADR-003: Uses module_type_override to register modules with namespaced
    module types (e.g., "fusionphysics_powerbalance.AlphaNeutronSplitModule")
    while keeping Python class names unchanged (e.g., "AlphaNeutronSplitModule").
    """
    return create_registry(
        [            ConstraintReportAggregatorModule,            FixtureF1DivisionCheckConstraintModule,            FixtureF2PowerCheckConstraintModule,            FixtureF3NestedCheckConstraintModule,        ],
        module_type_override={            ConstraintReportAggregatorModule: "constraints.ConstraintReportAggregatorModule",            FixtureF1DivisionCheckConstraintModule: "toy_plant.FixtureF1DivisionCheckConstraintModule",            FixtureF2PowerCheckConstraintModule: "toy_plant.FixtureF2PowerCheckConstraintModule",            FixtureF3NestedCheckConstraintModule: "toy_plant.FixtureF3NestedCheckConstraintModule",        },
    )


# Custom schema types for TEAx pipeline registration
# Use with: execute_pipeline(..., custom_schema_types=CUSTOM_SCHEMA_TYPES)
CUSTOM_SCHEMA_TYPES = [    ToyPlantParams,    ConstraintEvaluation,    ConstraintReport,]
