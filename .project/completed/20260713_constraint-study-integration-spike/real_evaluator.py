"""S5-style prepared-pipeline evaluator over S4's sealed generated package.

THROWAWAY SPIKE CODE. This is the seam the Item-0 integration spike exists to
exercise: a real evaluator (S5 shape: typed in-memory entry, prepare-once,
fresh context per case) over S4's real sealed package, presenting exactly the
interface S6's StudyRunner calls (`evaluate(inputs, attempt_number) -> Evidence`).

Nothing here is production. It ports S5's prepared-mapping scaffolding (the
prototype was throwaway too) and adds a candidate->typed-entry bridge plus a
projection from the generated report into S6's generic `Evidence` envelope.

Environment: run under a licensed host venv with simkit on the path, e.g.
    PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit \
      /home/reid/1cfe/fusion-tea/.venv/bin/python ...
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from pydantic import BaseModel

# --- sealed package location (S4 probe A output) --------------------------
S4_OUT = Path(
    "/home/reid/1cfe/sysml-codegen/.project/active/"
    "spike-vertical-slice-constraint-execution/out"
)
PACKAGE_DIR = S4_OUT / "package_live"
PACKAGE_NAME = "wi014_s4"

# S6's Evidence envelope + failure taxonomy live in study_lifecycle; import the
# real ones so the projection targets exactly what the runner/policy consume.
S6_DIR = Path(
    "/home/reid/1cfe/teax/.project/active/spike-crash-safe-study-lifecycle"
)
if str(S6_DIR) not in sys.path:
    sys.path.insert(0, str(S6_DIR))
from study_lifecycle import Evidence, ExecutionFailed  # noqa: E402


# --------------------------------------------------------------------------
# Seal verification (inlined; the study side must not import codegen)
# --------------------------------------------------------------------------

def verify_seal(out_dir: Path = PACKAGE_DIR) -> str:
    seal_path = out_dir / "contracts" / "package_contract.json"
    seal = json.loads(seal_path.read_text())
    for rel, expected in seal["artifact_hashes"].items():
        actual = hashlib.sha256((out_dir / rel).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"seal violation: {rel} hash mismatch")
    extras = {
        str(p.relative_to(out_dir))
        for p in out_dir.rglob("*")
        if p.is_file() and p != seal_path and "__pycache__" not in p.parts
    } - set(seal["artifact_hashes"])
    if extras:
        raise RuntimeError(f"seal violation: unhashed files present: {sorted(extras)}")
    return seal["executable_fingerprint"]


_PKG_ROOT = Path(__file__).resolve().parent / "_pkg"


def load_package():
    # The package's internal imports are `from wi014_s4. ...`, so it must be
    # importable under that name. package_live is the on-disk dir; expose it as
    # wi014_s4 via a symlink (the seal still verifies against package_live).
    _PKG_ROOT.mkdir(exist_ok=True)
    link = _PKG_ROOT / PACKAGE_NAME
    if not link.exists():
        link.symlink_to(PACKAGE_DIR, target_is_directory=True)
    if str(_PKG_ROOT) not in sys.path:
        sys.path.insert(0, str(_PKG_ROOT))
    return importlib.import_module(PACKAGE_NAME)


# --------------------------------------------------------------------------
# S5-style prepared mapping pipeline (ported from the S5 throwaway probe)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class MappingEntrySource:
    """Strict, already-typed values keyed by EntryPoint channel ID."""

    expected_types: Mapping[str, type[BaseModel]]

    @classmethod
    def from_spec(cls, specification: Any, schema_types: Mapping[str, type]) -> "MappingEntrySource":
        entry = next(m for m in specification.modules.values() if m.is_entry)
        expected: dict[str, type[BaseModel]] = {}
        for binding in entry.outputs.values():
            expected_type = schema_types.get(binding.type_name)
            if expected_type is None:
                raise TypeError(
                    f"Entry channel {binding.channel_name!r} has unknown type {binding.type_name!r}"
                )
            expected[binding.channel_name] = expected_type
        return cls(expected_types=MappingProxyType(expected))

    def validate(self, values: Mapping[str, Any]) -> Mapping[str, BaseModel]:
        expected_keys = set(self.expected_types)
        supplied_keys = set(values)
        missing = sorted(expected_keys - supplied_keys)
        extra = sorted(supplied_keys - expected_keys)
        if missing or extra:
            raise ValueError(f"Entry mapping key mismatch: missing={missing}, extra={extra}")
        validated: dict[str, BaseModel] = {}
        for channel_name, expected_type in self.expected_types.items():
            value = values[channel_name]
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"Entry channel {channel_name!r} expects {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )
            validated[channel_name] = value
        return MappingProxyType(validated)


def _build_prepared(package):
    from simkit.core.pipeline import (
        _build_entry_loaders,
        _build_schema_type_registry,
        entry_point_validate,
    )
    from simkit.core.pipeline_executor import (
        PipelineExecutionContext,
        SerialPipelineExecutor,
    )
    from simkit.io.output_router import create_output_router_with_json_schemas

    custom_types = list(package.CUSTOM_SCHEMA_TYPES)
    schema_types = _build_schema_type_registry(custom_types)
    entry_loaders = _build_entry_loaders(custom_types)
    registry = getattr(package, f"create_{PACKAGE_NAME}_registry")()
    spec = entry_point_validate(PACKAGE_DIR / "pipelines" / "pipeline.yaml")

    # The validator requires a write handler for every ExitPoint output type even
    # when persist_outputs is off, so the custom generated types (ConstraintEvaluation,
    # ConstraintReport) need JSON handlers registered on the router.
    router = create_output_router_with_json_schemas(
        [t.__name__ for t in custom_types], include_builtins=True
    )

    class MappingContext(PipelineExecutionContext):
        def __init__(self, reg, entry_values):
            super().__init__(reg)
            self.entry_values = entry_values

    class MappingExecutor(SerialPipelineExecutor):
        """Real executor with only file-backed EntryPoint loading replaced."""

        def _execute_entry(self, module_spec, spec, context):
            for binding in module_spec.outputs.values():
                context.set_channel(
                    binding.channel_name, context.entry_values[binding.channel_name]
                )

    executor = MappingExecutor(
        registry,
        output_router=router,
        schema_type_registry=dict(schema_types),
        entry_loaders=dict(entry_loaders),
    )
    graph = executor.build_graph(spec)
    source = MappingEntrySource.from_spec(spec, schema_types)
    return executor, graph, registry, source, MappingContext


# --------------------------------------------------------------------------
# Exit-channel IDs (from the generated pipeline.yaml)
# --------------------------------------------------------------------------

AREA_CH = "toy_plant__demo_plant__area_calc__area"
COST_CH = "toy_plant__demo_plant__cost_calc__cost"
EVAL_CH = "toy_plant__demo_plant__affordable__evaluation"
REPORT_CH = "constraint_report"
ENTRY_CH = "toy_plant_params"

# Generated report headline vocabulary (underscore) -> S6 policy vocabulary (hyphen).
HEADLINE_TO_POLICY = {
    "all_satisfied": "all-satisfied",
    "violation": "violation",
    "indeterminate": "indeterminate",
    "not_assessed": "not-assessed",
}


def _json_safe(x: Any) -> Any:
    """Keep evidence artifacts valid, stable JSON: non-finite floats -> tag."""
    if isinstance(x, float) and not math.isfinite(x):
        return {"__nonfinite__": "nan" if math.isnan(x) else ("inf" if x > 0 else "-inf")}
    return x


def _to_float(v: Any) -> float:
    """Bridge the JSON-clean proposal value to a real (possibly non-finite) float."""
    if isinstance(v, str):
        return float(v)  # "nan" / "inf" / "-inf" materialize here, in-memory only
    return float(v)


class RealPreparedEvaluator:
    """S5-shaped evaluator over S4's sealed package, S6 evaluator interface.

    Prepares the pipeline once; each `evaluate` runs a fresh context. The
    `attempt_number` argument is accepted to match S6's `FakeEvaluator` signature
    but is unused: the real prepared pipeline is deterministic and stateless per
    case (this signature gap is a named finding).
    """

    # Fixed design attributes; only plant_budget varies per candidate.
    FIXED = {
        "toy_plant__Toy_Plant__plant_length": 4.0,
        "toy_plant__Toy_Plant__plant_unit_cost": 250.0,
        "toy_plant__Toy_Plant__plant_width": 3.0,
    }

    def __init__(self) -> None:
        self.fingerprint = verify_seal()
        self.package = load_package()
        self.ToyPlantParams = self.package.ToyPlantParams
        (self.executor, self.graph, self.registry,
         self.source, self.MappingContext) = _build_prepared(self.package)
        self.eval_count = 0

    # -- S6 evaluator interface ------------------------------------------
    def evaluate(self, inputs: Mapping[str, Any], attempt_number: int) -> Evidence:
        budget = _to_float(inputs["budget"])
        params = self.ToyPlantParams(
            toy_plant__Toy_Plant__plant_budget=budget, **self.FIXED
        )
        try:
            validated = self.source.validate({ENTRY_CH: params})
            context = self.MappingContext(self.registry, validated)
            result = self.executor.run(self.graph, context, persist_outputs=False)
        except Exception as error:  # a module raising is a real execution failure
            raise ExecutionFailed(f"{type(error).__name__}: {error}") from error
        self.eval_count += 1
        return self._project(result)

    # -- generated report -> generic Evidence ----------------------------
    def _project(self, result) -> Evidence:
        outs = dict(result.outputs)
        report = outs[REPORT_CH]
        outputs = {
            "area": outs[AREA_CH].root,
            "cost": outs[COST_CH].root,
        }
        projected_report = {
            "headline": HEADLINE_TO_POLICY[report.headline],
            "assessed_count": report.assessed_count,
            "catalog_fingerprint": report.catalog_fingerprint,
            "constraints": [
                {
                    "id": r.constraint_id,
                    "status": r.status,
                    "actual_value": r.actual_value,
                    "margin": _json_safe(r.margin) if r.margin is not None else None,
                    "observed": {k: _json_safe(v) for k, v in r.observed.items()},
                }
                for r in report.results
            ],
        }
        return Evidence(outputs=outputs, report=projected_report)
