"""INV1: the four isolation-clean evaluation modules import only from an
allowlist and construct with the generated package absent from sys.path.

Two legs, together giving the guard teeth (design.md#validation-approach):
(a) a static AST source scan — catches a sneaky import wherever it is
    written, including inside TYPE_CHECKING blocks;
(b) package-absent construction — catches a dynamic (importlib) dependency
    the static scan cannot see.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2] / "evaluation"
CLEAN_MODULES = ["evidence.py", "entry_source.py", "failure.py", "projection.py"]
ALLOWED_ROOTS = {"pydantic"}
STDLIB = set(sys.stdlib_module_names)


def _import_roots(node: ast.AST):
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield alias.name.split(".")[0]
    elif isinstance(node, ast.ImportFrom):
        if node.level and node.level > 0:
            # Relative import within simkit.evaluation itself.
            yield "simkit"
        elif node.module:
            yield node.module.split(".")[0]


def test_clean_modules_import_only_allowlist():
    for name in CLEAN_MODULES:
        source = (EVAL_DIR / name).read_text()
        tree = ast.parse(source, filename=name)
        for node in ast.walk(tree):
            for root in _import_roots(node):
                assert root in ALLOWED_ROOTS or root == "simkit" or root in STDLIB, (
                    f"{name} imports disallowed root {root!r}"
                )


_PACKAGE_ABSENT_SCRIPT = """
import sys
assert "wi014_s4" not in sys.modules, "wi014_s4 pre-imported before the test ran"

from simkit.evaluation import EvidenceProvenance, ModelEvidence

evidence = ModelEvidence(
    responses={"headline": "indeterminate"},
    outputs={"area": 12.0},
    provenance=EvidenceProvenance(
        executable_fingerprint="fp",
        evidence_schema_version="v1",
        evaluator_version="v1",
        input_digest="digest",
    ),
    report=object(),
)

assert evidence.responses["headline"] == "indeterminate"
assert "wi014_s4" not in sys.modules
"""


def test_construct_evidence_with_generated_package_absent():
    # Run in a fresh subprocess: within the test *session*, wi014_s4 may
    # already be in sys.modules (other evaluation tests load it via the
    # `prepared`/`file_backed` fixtures) — that says nothing about whether
    # these four modules themselves need it. Only a clean interpreter proves
    # that.
    result = subprocess.run(
        [sys.executable, "-c", _PACKAGE_ABSENT_SCRIPT],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
