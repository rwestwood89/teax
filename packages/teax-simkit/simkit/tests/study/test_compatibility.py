"""Compatibility binding immutability (INV-E), order-sensitive strategy_config (D8, MF-2), and
invariant 50's carrier across CONSTRAINT-SEMANTICS Item 3."""
from __future__ import annotations

import dataclasses

import pytest

from simkit.evaluation.evaluator import PreparedEvaluator
from simkit.study.failures import IncompatibleStore
from simkit.study.identity import digest_of
from simkit.study.store import StudyStore

from .conftest import compat_with_strategy_config


def test_matching_reopen_succeeds(tmp_path):
    db = tmp_path / "study.db"
    compat = compat_with_strategy_config("cfg-v1")
    StudyStore.create_or_open(db, compat).close()
    StudyStore.create_or_open(db, compat).close()  # no raise


def test_incompatible_reopen_fails(tmp_path):
    db = tmp_path / "study.db"
    compat = compat_with_strategy_config("cfg-v1")
    StudyStore.create_or_open(db, compat).close()
    mutated = compat_with_strategy_config("cfg-v2")
    with pytest.raises(IncompatibleStore):
        StudyStore.create_or_open(db, mutated)


def test_grid_reorder_is_new_lineage(tmp_path):  # MF-2, D8, INV-G
    db = tmp_path / "study.db"
    ordered_ab = digest_of([["a", [1.0, 2.0]], ["b", [3.0, 4.0]]])
    ordered_ba = digest_of([["b", [3.0, 4.0]], ["a", [1.0, 2.0]]])
    assert ordered_ab != ordered_ba  # same variables, different declared order

    StudyStore.create_or_open(db, compat_with_strategy_config(ordered_ab)).close()
    with pytest.raises(IncompatibleStore):
        StudyStore.create_or_open(db, compat_with_strategy_config(ordered_ba))


# ---------------------------------------------------------------------------
# Invariant 50 — the transition across CONSTRAINT-SEMANTICS Item 3
# ---------------------------------------------------------------------------


def _compat_with_evidence_schema_version(version: str):
    """The baseline binding with ONE field varied: the one that actually carries the item."""
    return dataclasses.replace(
        compat_with_strategy_config("cfg-v1"), evidence_schema_version=version
    )


def test_reopening_a_store_across_the_evidence_bump_raises():
    """The carrier is `evidence_schema_version`, and the test varies THAT field specifically.

    Rev 1 of the design assumed a catalog or report schema move would change
    `model_contract_fingerprint`. It does not, for the packages that could have a store: that
    fingerprint is codegen's `semantic_fingerprint` over five inputs, this item adds no catalog
    field, and `CATALOG_SCHEMA_VERSION` stayed at 3.0.0 — so for an already-constraint-bearing
    package whose channel set does not move, it is byte-identical across the item.

    `evidence_schema_version` is the field that does move (`v1` -> `v2`), because the report
    tree inside the evidence artifact gained a required `coverage` block, renamed
    `assessed_count`, and replaced its headline vocabulary.

    Varying that field specifically is the point, and the design said why: a test that varied
    only the model-contract fingerprint could pass today and silently stop proving anything the
    moment that fingerprint stopped moving. This one cannot.
    """
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as scratch:
        db = Path(scratch) / "study.db"
        StudyStore.create_or_open(db, _compat_with_evidence_schema_version("v1")).close()
        with pytest.raises(IncompatibleStore):
            StudyStore.create_or_open(db, _compat_with_evidence_schema_version("v2"))


def test_the_same_evidence_schema_version_reopens_cleanly(tmp_path):
    """The control. Without it the test above could pass because reopening never works."""
    db = tmp_path / "study.db"
    StudyStore.create_or_open(db, _compat_with_evidence_schema_version("v1")).close()
    StudyStore.create_or_open(db, _compat_with_evidence_schema_version("v1")).close()


def test_the_evaluator_stamps_the_version_this_item_moved_to():
    """The binding is only a real gate if the evaluator actually stamps the new value.

    A store bound to `v1` and an evaluator still producing `v1` would make the refusal above
    unreachable in practice, which is the way an archive-and-begin transition silently becomes
    a no-op.
    """
    assert PreparedEvaluator.EVIDENCE_SCHEMA_VERSION == "v2"
