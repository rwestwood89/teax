"""Consumer harness for the generated heater_tea package.

DIFFERENT FROM TODAY — this file is the whole point of the contract change.
Persistence is two arguments; the harness owns no serialization knowledge.
"""
from pathlib import Path

from simkit.core.pipeline import execute_pipeline

from heater_tea import create_heater_tea_registry, CUSTOM_SCHEMA_TYPES

HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# TODAY (deleted): every consumer of a generated package carries this block,
# copied from fusion-tea's run_anchors.py:119-132 —
#
#   router = create_output_router_with_json_schemas(["RootModel[float]"])
#   router.register_handler("float", WriteHandler(
#       fn=lambda value, path: Path(path).write_text(json.dumps(value)),
#       extension=".json"))
#   result = execute_pipeline(..., output_router=router, ...)
#
# It exists only to teach TEAx how to write its own channel values, and it
# still can't cover int/str/bool without three more lambdas.
# ---------------------------------------------------------------------------

result = execute_pipeline(
    HERE / "pipelines" / "heater.yaml",
    output_dir=HERE / "outputs",
    registry=create_heater_tea_registry(),
    custom_schema_types=CUSTOM_SCHEMA_TYPES,   # domain schemas only; no router
)

# In-memory channel values are unchanged either way: bare 157.5 for the
# decomposed float field, Float(0.87) for the single-output wrapper.
print(result.outputs["heater__cost_calc__lcoe_usd_mwh"])          # 157.5
print(result.outputs["heater__efficiency_calc__efficiency"].root)  # 0.87
