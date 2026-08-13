"""Lifecycle Item 11 — constraint evidence durability coordinates.

Grounds the invariants against real generated packages:

- INV-A: a constraint-free package (no ``constraint_report`` channel, valid
  EntryPoint) yields empty constraint evidence on BOTH routes — no ``KeyError``
  (the 46a RED, now green).
- INV-H: a package whose catalog declares constraints but whose report channel
  is absent raises ``CorruptConstraintEvidence`` loudly (corruption != emptiness).
- INV-C/INV-D: the sealed evidence chain (report tree, responses, outputs) cannot
  be mutated — so policy cannot corrupt authoritative or persisted evidence.
- INV-F/INV-I (C1): a real output-write failure stamps ``OUTPUT_WRITE`` via the
  positive executor signal; an entry-load failure keeps ``MODULE_EXECUTION`` and
  is never over-stamped ``OUTPUT_WRITE``.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from simkit.evaluation.evaluator import FileBackedEvaluator, PreparedEvaluator
from simkit.evaluation.evidence import CorruptConstraintEvidence
from simkit.evaluation.failure import EvaluationFailed, EvaluationPhase
from simkit.evaluation.package_load import ProvisionalPackageLoader
from simkit.study.bridge import CandidateBridge

FIXTURES = Path(__file__).parent / "fixtures"
CFREE_DIR = FIXTURES / "constraint_free" / "package_live"
CFREE_SPEC = CFREE_DIR / "pipelines" / "pipeline.yaml"
CFREE_ENTRY = CFREE_DIR / "inputs" / "constraint_free_plant_params.json"

F1_DIR = FIXTURES / "f1_arithmetic" / "package_live"
F1_SPEC = F1_DIR / "pipelines" / "pipeline.yaml"
F1_CASE = FIXTURES / "f1_arithmetic" / "cases" / "safe_satisfied.json"


def _cfree_loader(tmp_path: Path) -> ProvisionalPackageLoader:
    loader = ProvisionalPackageLoader(
        package_dir=CFREE_DIR, package_name="constraint_free", link_root=tmp_path / "links"
    )
    loader.load()
    return loader


# ---------------------------------------------------------------------------
# INV-A — constraint-free -> empty evidence on both routes (46a, was KeyError)


def test_constraint_free_prepared_empty_evidence(tmp_path):
    loader = _cfree_loader(tmp_path)
    prepared = PreparedEvaluator(loader, CFREE_SPEC, expects_constraint_report=False)
    candidate = json.loads(CFREE_ENTRY.read_text())
    evidence = prepared.evaluate(CandidateBridge(prepared.entry_models).build(candidate))

    assert dict(evidence.responses) == {}
    assert evidence.report is None
    # The real calc output survives; only the constraint report is absent.
    assert evidence.outputs["constraint_free_plant__freePlant__area_calc__area"] == 12.0


def test_constraint_free_file_backed_empty_evidence(tmp_path):
    loader = _cfree_loader(tmp_path)
    fb = FileBackedEvaluator(
        loader, CFREE_DIR, tmp_path / "work", tmp_path / "out",
        expects_constraint_report=False,
    )
    entry = tmp_path / "entry.json"
    entry.write_bytes(CFREE_ENTRY.read_bytes())
    evidence = fb.evaluate(entry)

    assert dict(evidence.responses) == {}
    assert evidence.report is None
    assert evidence.outputs["constraint_free_plant__freePlant__area_calc__area"] == 12.0


# ---------------------------------------------------------------------------
# INV-H — constraint-bearing catalog + absent channel = corruption, not empty


def test_absent_channel_with_catalog_expectation_raises_corruption(tmp_path):
    """The catalog authority says constraints exist (``expects_constraint_report``
    True) but the report channel is absent — a dropped channel. Loud raise, not a
    silent ``unconstrained`` case."""
    loader = _cfree_loader(tmp_path)
    prepared = PreparedEvaluator(loader, CFREE_SPEC, expects_constraint_report=True)
    candidate = json.loads(CFREE_ENTRY.read_text())
    with pytest.raises(CorruptConstraintEvidence, match="constraint_report"):
        prepared.evaluate(CandidateBridge(prepared.entry_models).build(candidate))


# ---------------------------------------------------------------------------
# INV-C/INV-D — the sealed evidence chain is immutable (report, responses, outputs)


def _f1_prepared(tmp_path) -> PreparedEvaluator:
    loader = ProvisionalPackageLoader(
        package_dir=F1_DIR, package_name="f1_arithmetic_constraints", link_root=tmp_path / "l"
    )
    loader.load()
    return PreparedEvaluator(loader, F1_SPEC, expects_constraint_report=True)


def test_sealed_evidence_chain_cannot_be_mutated(tmp_path):
    prepared = _f1_prepared(tmp_path)
    case = json.loads(F1_CASE.read_text())
    evidence = prepared.evaluate({"toy_plant_params": prepared.entry_models["toy_plant_params"](**case)})

    # Report is a real, non-empty tree here (satisfied case).
    assert evidence.report is not None and evidence.report["results"]

    with pytest.raises((TypeError, AttributeError)):
        evidence.responses["headline"] = "violated"
    with pytest.raises((TypeError, AttributeError)):
        evidence.outputs["injected"] = 0.0  # read-only mapping: add-key blocked too
    with pytest.raises((TypeError, AttributeError)):
        evidence.report["results"][0]["status"] = "satisfied"
    with pytest.raises((TypeError, AttributeError)):
        evidence.report["results"][0]["margin"] = 999.0
    with pytest.raises((TypeError, AttributeError)):
        evidence.report["results"] += ({},)  # list-container append attempt


# ---------------------------------------------------------------------------
# INV-F / INV-I (C1) — OUTPUT_WRITE emitted honestly, never over-emitted


def test_output_write_failure_stamps_output_write(tmp_path):
    """A clean run whose persistence fails (unwritable output dir) stamps
    OUTPUT_WRITE via the positive executor signal — a bare OSError, no
    OutputRouterError, so only the flag catches it."""
    loader = ProvisionalPackageLoader(
        package_dir=F1_DIR, package_name="f1_arithmetic_constraints", link_root=tmp_path / "l"
    )
    loader.load()
    ro_output = tmp_path / "ro_out"
    ro_output.mkdir()
    fb = FileBackedEvaluator(
        loader, F1_DIR, tmp_path / "work", ro_output, expects_constraint_report=True
    )
    entry = tmp_path / "entry.json"
    entry.write_bytes(F1_CASE.read_bytes())
    os.chmod(ro_output, stat.S_IRUSR | stat.S_IXUSR)  # read-only: write phase fails
    try:
        with pytest.raises(EvaluationFailed) as caught:
            fb.evaluate(entry)
    finally:
        os.chmod(ro_output, stat.S_IRWXU)
    assert caught.value.failure.phase == EvaluationPhase.OUTPUT_WRITE
    # No module failed — an honest null module key on a write failure.
    assert caught.value.failure.module_or_channel is None


def test_entry_load_failure_not_over_emitted_as_output_write(tmp_path):
    """A malformed entry on the file-backed route fails during entry load
    (``in_output_write`` False) — MODULE_EXECUTION, never OUTPUT_WRITE. This is
    the coordinate that would have caught the C1 misclassification."""
    loader = ProvisionalPackageLoader(
        package_dir=F1_DIR, package_name="f1_arithmetic_constraints", link_root=tmp_path / "l"
    )
    loader.load()
    fb = FileBackedEvaluator(
        loader, F1_DIR, tmp_path / "work", tmp_path / "out",
        expects_constraint_report=True,
    )
    entry = tmp_path / "entry.json"
    entry.write_text("{ this is not valid json")
    with pytest.raises(EvaluationFailed) as caught:
        fb.evaluate(entry)
    assert caught.value.failure.phase == EvaluationPhase.MODULE_EXECUTION
    assert caught.value.failure.phase != EvaluationPhase.OUTPUT_WRITE


# ---------------------------------------------------------------------------
# INV-B — excluded-only -> exact not_assessed surface, distinct from empty

EXCL_DIR = FIXTURES / "excluded_only" / "package_live"
EXCL_SPEC = EXCL_DIR / "pipelines" / "pipeline.yaml"
EXCL_ENTRY = EXCL_DIR / "inputs" / "excl_plant_params.json"


def test_excluded_only_reads_partial_coverage_distinct_from_constraint_free(tmp_path):
    """An excluded-only package emits a real report, and it now says what it did not assess.

    The model authors one `assert constraint` whose predicate the executable profile refuses
    (`non_numerical`), so it produces zero eligible entries. It is still an **asserted gate the
    author wrote**, so CONSTRAINT-SEMANTICS Item 3 keeps it in the feasibility denominator as
    an unassessed one: `applicable_gate_total 1, assessed 0, unassessed 1` -> headline
    `partial_coverage`.

    Before that item this read `not_assessed`, which conflated "one gate, refused by the
    profile" with "no applicable gate at all" — the second of the two zero-input branches
    collapsing into the first. The distinction is the point: a design search must be able to
    tell a candidate nobody checked from a candidate with nothing to check.

    Structurally still distinct from constraint-free empty evidence, which is the other half
    of this test: a present report and a headline, not `{}` / `None`.
    """
    loader = ProvisionalPackageLoader(
        package_dir=EXCL_DIR, package_name="excl_only", link_root=tmp_path / "links"
    )
    loader.load()
    prepared = PreparedEvaluator(loader, EXCL_SPEC, expects_constraint_report=True)
    candidate = json.loads(EXCL_ENTRY.read_text())
    evidence = prepared.evaluate(CandidateBridge(prepared.entry_models).build(candidate))

    assert evidence.responses["headline"] == "partial_coverage"
    assert evidence.report is not None  # a real report, unlike constraint-free
    assert evidence.report["assessed_entry_count"] == 0
    assert list(evidence.report["results"]) == []
    # The account is what carries the distinction the headline alone cannot.
    assert dict(evidence.report["coverage"]) == {
        "authored_usage_total": 1,
        "applicable_gate_total": 1,
        "assessed_gate_count": 0,
        "unassessed_gate_count": 1,
        "inapplicable_gate_count": 0,
        "unassessed_reasons": {"non_numerical": 1},
        "coverage_state": "partial",
    }


def test_the_nested_coverage_block_is_unmutable_through_evidence(tmp_path):
    """Invariant 41 over the block this item added — at BOTH levels of nesting.

    `ModelEvidence._freeze` recurses mappings at attach, so `coverage` and the
    `unassessed_reasons` histogram inside it are each a `MappingProxyType`. The obligation was a
    test, not a mechanism: nothing reachable from `ModelEvidence.report["coverage"]` may be
    mutable, and a nested block is exactly where a recursion bug would hide.

    Asserted at both levels deliberately. A `_freeze` that stopped recursing one level down
    would still pass a top-level-only check while leaving the histogram writable — and the
    histogram is the field that says *why* gates went unassessed.
    """
    loader = ProvisionalPackageLoader(
        package_dir=EXCL_DIR, package_name="excl_only", link_root=tmp_path / "links"
    )
    loader.load()
    prepared = PreparedEvaluator(loader, EXCL_SPEC, expects_constraint_report=True)
    candidate = json.loads(EXCL_ENTRY.read_text())
    evidence = prepared.evaluate(CandidateBridge(prepared.entry_models).build(candidate))

    coverage = evidence.report["coverage"]

    # Level 1: the block itself.
    with pytest.raises(TypeError):
        coverage["assessed_gate_count"] = 99
    with pytest.raises(TypeError):
        coverage["a_field_nobody_defined"] = 1
    with pytest.raises(TypeError):
        del coverage["coverage_state"]

    # Level 2: the histogram inside it.
    with pytest.raises(TypeError):
        coverage["unassessed_reasons"]["non_numerical"] = 0
    with pytest.raises(TypeError):
        coverage["unassessed_reasons"]["invented_reason"] = 1

    # And the report tree above it, so the block cannot be swapped out wholesale.
    with pytest.raises(TypeError):
        evidence.report["coverage"] = {}

    # Nothing above actually changed anything.
    assert coverage["assessed_gate_count"] == 0
    assert dict(coverage["unassessed_reasons"]) == {"non_numerical": 1}
