"""Reproduce the sealed F1 arithmetic fixture through production generators."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from datetime import datetime, timezone
from pathlib import Path

import yaml

PACKAGE_NAME = "f1_arithmetic_constraints"
SYSML_SHA = "512786c7dfab44fba7a0185d09e845b7494c702d"
AGENTIC_SHA = "4ed2a0728ea49298666415cd389d9a6173a81a3e"
LOCK_SHA256 = "b457136b857974c655094b86496dc88809b2dc405146340aa5f02ebb8a284c05"
EXPECTED_CONSTRAINT_ORDER = (
    "f1_division_check",
    "f2_power_check",
    "f3_nested_check",
)
EXPECTED_MODULE_ORDER = (
    "entry_fusion",
    *EXPECTED_CONSTRAINT_ORDER,
    "constraint_report_aggregator",
    "exit_point",
)
DESIGN_ATTRIBUTE_DEFAULTS = {
    "toy_plant__Toy_Plant__division_a": "2.0",
    "toy_plant__Toy_Plant__division_b": "1.0",
    "toy_plant__Toy_Plant__power_a": "2.0",
    "toy_plant__Toy_Plant__power_b": "2.0",
    "toy_plant__Toy_Plant__nested_a": "2.0",
    "toy_plant__Toy_Plant__nested_b": "1.0",
}


def _run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_root(module_file: str) -> Path:
    return Path(module_file).resolve().parents[2]


def _preflight() -> dict[str, object]:
    import agentic_mbse
    import jinja2
    import pydantic
    import sysml_codegen
    import yaml as yaml_module

    if sys.implementation.name != "cpython" or platform.python_version() != "3.12.11":
        raise RuntimeError("fixture generation requires CPython 3.12.11")
    environment_dir = Path(sys.executable).absolute().parent.parent
    if environment_dir.name != "environment":
        raise RuntimeError(
            f"interpreter must be inside the fresh generation environment, got {sys.executable}"
        )
    if os.environ.get("PYTHONPATH"):
        raise RuntimeError("PYTHONPATH must be unset during fixture generation")

    sysml_root = _source_root(sysml_codegen.__file__)
    agentic_root = _source_root(agentic_mbse.__file__)
    generation_root = environment_dir.parent
    if sysml_root != generation_root / "sysml-codegen":
        raise RuntimeError(f"sysml-codegen import is not from the detached worktree: {sysml_root}")
    if agentic_root != generation_root / "agentic-mbse":
        raise RuntimeError(f"agentic-mbse import is not from the detached worktree: {agentic_root}")

    for root, expected in ((sysml_root, SYSML_SHA), (agentic_root, AGENTIC_SHA)):
        actual = _run("git", "rev-parse", "HEAD", cwd=root)
        if actual != expected:
            raise RuntimeError(f"source revision mismatch for {root}: {actual}")
        if _run("git", "status", "--porcelain", "--untracked-files=no", cwd=root):
            raise RuntimeError(f"tracked source worktree is dirty: {root}")

    lock_path = sysml_root / "uv.lock"
    if _sha256(lock_path) != LOCK_SHA256:
        raise RuntimeError("pinned sysml-codegen uv.lock hash mismatch")
    versions = {
        "sysml-codegen": importlib.metadata.version("sysml-codegen"),
        "agentic-mbse": importlib.metadata.version("agentic-mbse"),
        "Jinja2": jinja2.__version__,
        "Pydantic": pydantic.__version__,
        "PyYAML": yaml_module.__version__,
    }
    expected_versions = {
        "sysml-codegen": "0.1.0",
        "agentic-mbse": "0.1.0",
        "Jinja2": "3.1.6",
        "Pydantic": "2.12.5",
        "PyYAML": "6.0.3",
    }
    if versions != expected_versions:
        raise RuntimeError(f"locked generation dependency mismatch: {versions}")
    uv_version = _run("uv", "--version")
    if uv_version != "uv 0.10.0":
        raise RuntimeError(f"fixture generation requires uv 0.10.0, got {uv_version}")

    distributions = sorted(
        (dist.metadata["Name"], dist.version)
        for dist in importlib.metadata.distributions()
        if dist.metadata["Name"]
    )
    identity = {
        "uv_version": uv_version,
        "lock_sha256": LOCK_SHA256,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "cache_tag": sys.implementation.cache_tag,
        "platform": sysconfig.get_platform(),
        "sysml_codegen_sha": SYSML_SHA,
        "agentic_mbse_sha": AGENTIC_SHA,
        "versions": versions,
        "distributions": distributions,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    identity["environment_fingerprint"] = hashlib.sha256(encoded).hexdigest()
    return identity


def _reference(name: str):
    from agentic_mbse.sysml.expression_facts import FeatureReferenceFact, OperandTypeFact
    from agentic_mbse.sysml.expression_ir import FeatureReferenceNode

    return FeatureReferenceNode(
        reference=FeatureReferenceFact(
            source_name=name, target=None, target_types=[], chain_segments=[]
        ),
        operand_type=OperandTypeFact(category="real", enumeration=None, unit=None),
    )


def _literal(value: float):
    from agentic_mbse.sysml.expression_facts import LiteralFact, OperandTypeFact
    from agentic_mbse.sysml.expression_ir import LiteralNode

    return LiteralNode(
        literal=LiteralFact(kind="LiteralRational", value=value, result_type="real"),
        operand_type=OperandTypeFact(category="real", enumeration=None, unit=None),
    )


def _operator(operator: str, *operands):
    from agentic_mbse.sysml.expression_ir import OperatorNode

    return OperatorNode(operator=operator, operands=list(operands), operand_type=None)


def _predicate_ir(kind: str) -> str:
    from agentic_mbse.sysml.expression_ir import serialize_expression

    if kind == "division":
        expression = _operator(">", _operator("/", _reference("a"), _reference("b")), _literal(0.0))
    elif kind == "power":
        expression = _operator(">", _operator("**", _reference("a"), _reference("b")), _literal(0.0))
    elif kind == "nested":
        expression = _operator(
            "and",
            _operator(">", _operator("/", _reference("a"), _reference("b")), _literal(0.0)),
            _operator(">", _reference("a"), _literal(-1.0)),
        )
    else:  # pragma: no cover - producer-owned closed set
        raise ValueError(kind)
    return serialize_expression(expression)


def _build_context():
    from agentic_mbse.sysml.constraint_facts import ConstraintFacts
    from sysml_codegen.analysis.constraint_lowering import extend_graph_with_constraints
    from sysml_codegen.analysis.parameter_groups import DesignAttributeData, ParameterGroupDeriver
    from sysml_codegen.generation.constraint_catalog import assemble_constraint_catalog
    from sysml_codegen.resolution.models import (
        ComputationGraph,
        ConcreteConstraint,
        ConcreteConstraintInput,
        ConstraintInputResolution,
    )

    specs = (
        ("f1_division_check", "division", "division_a", "division_b"),
        ("f2_power_check", "power", "power_a", "power_b"),
        ("f3_nested_check", "nested", "nested_a", "nested_b"),
    )
    constraints = []
    for constraint_id, kind, a_name, b_name in specs:
        inputs = [
            ConcreteConstraintInput(
                formal_name="a",
                resolution=ConstraintInputResolution.DESIGN_ATTRIBUTE,
                design_attribute_qn=f"toy_plant__Toy_Plant__{a_name}",
            ),
            ConcreteConstraintInput(
                formal_name="b",
                resolution=ConstraintInputResolution.DESIGN_ATTRIBUTE,
                design_attribute_qn=f"toy_plant__Toy_Plant__{b_name}",
            ),
        ]
        constraints.append(
            ConcreteConstraint(
                constraint_id=constraint_id,
                usage_qualified_name=f"f1_arithmetic::Fixture::{constraint_id}",
                source_local_identity=constraint_id,
                source_form="inline",
                owner_kind="part_def",
                owner_qualified_name="toy_plant::Toy_Plant",
                owner_instance_path="toy_plant__fixture",
                membership_kind="assert",
                is_negated=False,
                expected_value=True,
                predicate_ir=_predicate_ir(kind),
                inputs=inputs,
                evaluation_channel=f"{constraint_id}__evaluation",
                eligible=True,
            )
        )

    # The evaluator's existing file-backed scratch contract owns this exact
    # generated entry artifact name; use the production grouping input that
    # yields toy_plant_params.json rather than renaming generated output.
    source = Path("toy_plant.sysml")
    attributes = [
        DesignAttributeData(
            name=qualified_name.split("__")[-1],
            sysml_type="Real",
            default_value=default,
            unit=None,
            source_file=source,
            source_line=1,
            parent_part="toy_plant::Toy_Plant",
            qualified_name=qualified_name,
        )
        for qualified_name, default in DESIGN_ATTRIBUTE_DEFAULTS.items()
    ]
    deriver = ParameterGroupDeriver({source: attributes}, calc_usages=[], calc_defs=[])
    graph = ComputationGraph(modules=[], entry_point_groups=[], execution_order=[])
    graph = extend_graph_with_constraints(graph, constraints, deriver)
    facts = ConstraintFacts(definitions=[], usages=[], contexts=[], diagnostics=[])
    graph.constraint_catalog = assemble_constraint_catalog(constraints, facts)
    if tuple(module.name for module in graph.modules) != (
        *EXPECTED_CONSTRAINT_ORDER,
        "constraint_report_aggregator",
    ):
        raise RuntimeError("production graph module order mismatch")

    class _Context:
        computation_graph = graph

    return _Context()


def _generate(output: Path) -> None:
    from sysml_codegen.cli import (
        GenerationConfig,
        _check_duplicate_output_paths,
        _generate_backlog,
        _generate_entry_points,
        _generate_modules,
        _generate_pipeline,
        _generate_primitives,
        _generate_registry,
        _generate_schemas,
        _generate_stencils,
        _generate_tests,
        _get_template_env,
        _reconcile_params_coverage,
        _seal_package,
        _setup_output_directories,
    )

    context = _build_context()
    config = GenerationConfig(output_path=output, package_name=PACKAGE_NAME)
    _check_duplicate_output_paths(context.computation_graph.modules)
    _reconcile_params_coverage(context.computation_graph)
    _setup_output_directories(config)
    _generate_primitives(config)
    template_env = _get_template_env()
    _generate_schemas(context, config, template_env)
    _generate_modules(context, config, template_env)
    _generate_stencils(context, config, template_env)
    _generate_pipeline(context, config, template_env)
    _generate_registry(context, config, template_env)
    _generate_entry_points(context, config, template_env)
    _generate_backlog(context, config)
    _generate_tests(context, config, template_env)
    _seal_package(context, config)

    pipeline = yaml.safe_load((output / "pipelines" / "pipeline.yaml").read_text())
    if tuple(pipeline["modules"]) != EXPECTED_MODULE_ORDER:
        raise RuntimeError(f"generated YAML order mismatch: {tuple(pipeline['modules'])}")



def _write_generation_record(output: Path, identity: dict[str, object]) -> None:
    contract = json.loads((output / "contracts" / "package_contract.json").read_text())
    producer = Path(__file__).resolve()
    distributions = "\n".join(
        f"  - {name}=={version}" for name, version in identity["distributions"]
    )
    record = f"""# F1 Arithmetic Fixture Generation

This is a production-equivalent sealed fixture. Synthetic constraint facts enter production
`extend_graph_with_constraints` and `assemble_constraint_catalog`; all rendered package artifacts
then pass through the production schema, module, pipeline, registry, entry, contract, and seal APIs.

- Generated: `{datetime.now(timezone.utc).isoformat()}`
- Command: `generate_fixture.py --output {output} --package-name {PACKAGE_NAME} --overwrite`
- Package name: `{PACKAGE_NAME}`
- sysml-codegen SHA: `{SYSML_SHA}`
- agentic-mbse SHA: `{AGENTIC_SHA}`
- Producer SHA-256: `{_sha256(producer)}`
- uv version: `{identity['uv_version']}`
- Lockfile SHA-256: `{LOCK_SHA256}`
- Python: `{identity['python_implementation']} {identity['python_version']}`
- ABI/cache tag: `{identity['cache_tag']}`
- Platform: `{identity['platform']}`
- sysml-codegen distribution: `{identity['versions']['sysml-codegen']}`
- agentic-mbse distribution: `{identity['versions']['agentic-mbse']}`
- Jinja2: `{identity['versions']['Jinja2']}`
- Pydantic: `{identity['versions']['Pydantic']}`
- PyYAML: `{identity['versions']['PyYAML']}`
- Environment fingerprint: `{identity['environment_fingerprint']}`
- Graph constraint order: `{', '.join(EXPECTED_CONSTRAINT_ORDER)}`
- YAML module order: `{', '.join(EXPECTED_MODULE_ORDER)}`
- TEAx topological order: `{', '.join(EXPECTED_MODULE_ORDER)}`
- Executable fingerprint: `{contract['executable_fingerprint']}`

## Resolved distributions

{distributions}
"""
    (output.parent / "GENERATION.md").write_text(record, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package-name", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.package_name != PACKAGE_NAME:
        raise RuntimeError(f"package name must be {PACKAGE_NAME!r}")
    identity = _preflight()
    output = args.output.resolve()
    if output == Path(output.anchor) or output == output.parent:
        raise RuntimeError(f"refusing unsafe output path: {output}")
    if output.is_symlink():
        raise RuntimeError(f"refusing symlink output: {output}")
    if output.exists():
        if not args.overwrite:
            raise RuntimeError(f"output exists; pass --overwrite: {output}")
        shutil.rmtree(output)
    _generate(output)
    _write_generation_record(output, identity)


if __name__ == "__main__":
    main()
