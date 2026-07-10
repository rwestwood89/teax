"""Generated package registry for heater_tea."""
from simkit.core.registry_builder import create_registry
from simkit.core.pipeline_registry import PipelineModuleRegistry

from heater_tea.modules.efficiency_calc import EfficiencyCalcModule
from heater_tea.modules.cost_calc import CostCalcModule

from heater_tea.schemas.heater_params import HeaterParams as HeaterParams
from heater_tea.schemas.cost_breakdown import CostBreakdown as CostBreakdown

# ---------------------------------------------------------------------------
# DIFFERENT FROM TODAY: no `from heater_tea.primitives import Float` here.
# Today, codegen's _collect_exit_point_primitive_types() scans single-output
# exit channels and appends Float/Int/String/Bool to CUSTOM_SCHEMA_TYPES so
# that TEAx's auto-router gains a "RootModel[float]" write handler. Under the
# new contract those eight handlers ship in TEAx's default router, so the
# wrapper import and collection machinery disappear from generated packages.
# ---------------------------------------------------------------------------


def create_heater_tea_registry() -> PipelineModuleRegistry:
    """Create registry for all modules using auto-introspection. UNCHANGED."""
    return create_registry([EfficiencyCalcModule, CostCalcModule])


# Custom schema types for TEAx pipeline registration. UNCHANGED mechanism,
# SHORTER contents: domain-named schemas only — no primitive wrappers.
# (Today this list would also carry `Float`; the plain `float` channels of
# CostCalcOutput could not be expressed here at all — floats aren't
# BaseModels — which is why the old contract was unclosable from this side.)
CUSTOM_SCHEMA_TYPES = [HeaterParams, CostBreakdown]
