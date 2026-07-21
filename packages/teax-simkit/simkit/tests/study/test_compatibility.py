"""Compatibility binding immutability (INV-E) and order-sensitive strategy_config (D8, MF-2)."""
from __future__ import annotations

import pytest

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
