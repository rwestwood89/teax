"""Item 8 INV-6 tripwire: no product path reconstructs catalog identity (spec SC-2, design.md:308).

Scoped to the *reconstruction* anti-pattern (design review F5), not a blanket QN-split ban:
codegen's embedded catalog now carries source form, owner QN, definition QN, and the def→usage
join directly, so a consumer must never recover them by

  - splitting a qualified-name string on ``::`` / ``__`` to derive owner/definition/short name,
  - substring-searching serialized ``predicate_ir`` text to recover a definition link, or
  - hardcoding a ``source_form`` literal.

This scans teax's study/evaluation *product* source (tests and fixtures excluded — a fixture may
legitimately author any shape). The reconstruction was fusion's deleted materializer and teax's old
``_Catalog`` source-record join (now the embedded-catalog reader ``_EmbeddedCatalog``, renamed per
audit F-B); this guard fails loudly if either idiom reappears.
"""
from __future__ import annotations

import re
from pathlib import Path

SIMKIT = Path(__file__).resolve().parents[2]  # .../simkit
PRODUCT_DIRS = [SIMKIT / "study", SIMKIT / "evaluation"]

# QN reconstruction: splitting on the codegen qualified-name separators to recover identity.
_QN_SPLIT = re.compile(r"""\.(?:r?split)\(\s*['"](?:::|__)['"]""")
# Predicate-text search: probing predicate_ir string content to recover a link.
_PREDICATE_TEXT_SEARCH = re.compile(r"""in\s+.*predicate_ir|predicate_ir.*\.(?:find|index|split)\(""")
# Hardcoded source form: a literal assignment/binding of a source_form value.
_HARDCODED_SOURCE_FORM = re.compile(r"""source_form\s*=\s*['"](?:inline|definition_typed)['"]""")


def _product_py_files() -> list[Path]:
    files: list[Path] = []
    for root in PRODUCT_DIRS:
        for path in root.rglob("*.py"):
            if "tests" in path.parts or "fixtures" in path.parts:
                continue
            files.append(path)
    return files


def test_no_qn_string_reconstruction_in_product_source():
    offenders = [
        f"{p}:{i}" for p in _product_py_files()
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if _QN_SPLIT.search(line)
    ]
    assert not offenders, f"QN-splitting reconstruction reappeared: {offenders}"


def test_no_predicate_text_search_in_product_source():
    offenders = [
        f"{p}:{i}" for p in _product_py_files()
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if _PREDICATE_TEXT_SEARCH.search(line)
    ]
    assert not offenders, f"predicate-text search reconstruction reappeared: {offenders}"


def test_no_hardcoded_source_form_in_product_source():
    offenders = [
        f"{p}:{i}" for p in _product_py_files()
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if _HARDCODED_SOURCE_FORM.search(line)
    ]
    assert not offenders, f"hardcoded source_form reappeared: {offenders}"


def test_scan_actually_covers_the_rewired_modules():
    """Guard the guard: the scan must reach the modules the rewire touched, or it proves nothing."""
    scanned = {p.name for p in _product_py_files()}
    assert {"query.py", "config.py", "model_contract.py"} <= scanned
