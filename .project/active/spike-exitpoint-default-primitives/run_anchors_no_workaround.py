"""Spike probe: run fusion-tea's run_anchors.py with the T-1/T-2 router
workaround DELETED — the exact deletion the contract's acceptance criteria
describe.

Loads the original harness source, string-replaces run_pipeline()'s router
construction with a defaults-only execute_pipeline call, and executes it
with __file__ pointing at the original so all relative paths resolve.
Fails loudly if the harness source has drifted and the replace misses.

Run: cd ~/1cfe/fusion-tea/exploration/ife_e2e && \
     ../pipeline_spike/.venv-exec/bin/python \
     ~/1cfe/teax/.project/active/spike-exitpoint-default-primitives/run_anchors_no_workaround.py
"""
from pathlib import Path

HARNESS = Path("/home/reid/1cfe/fusion-tea/exploration/ife_e2e/run_anchors.py")

OLD = '''    router = create_output_router_with_json_schemas(["RootModel[float]"])
    router.register_handler(
        "float",
        WriteHandler(fn=lambda value, path: Path(path).write_text(json.dumps(value)),
                     extension=".json"),
    )
    result = execute_pipeline(
        PIPELINE,
        output_dir=E2E / "outputs" / "osiris",
        registry=create_ife_tea_registry(),
        output_router=router,
        custom_schema_types=CUSTOM_SCHEMA_TYPES,
    )'''

NEW = '''    result = execute_pipeline(
        PIPELINE,
        output_dir=E2E / "outputs" / "osiris",
        registry=create_ife_tea_registry(),
        custom_schema_types=CUSTOM_SCHEMA_TYPES,
    )'''

src = HARNESS.read_text()
assert OLD in src, "run_anchors.py source drifted; update OLD block"
patched = src.replace(OLD, NEW)
assert "output_router" not in patched.split("def run_pipeline")[1].split("def ")[0], \
    "router still referenced in run_pipeline"

code = compile(patched, str(HARNESS), "exec")
exec(code, {"__name__": "__main__", "__file__": str(HARNESS)})
