"""Fenced single-writer lease (D4, MF-1, INV-F)."""
from __future__ import annotations

import time

import pytest

from simkit.study.failures import StudyLeaseLost, StudyLocked
from simkit.study.store import StudyStore

from .conftest import compat_with_strategy_config


def force_dead(store: StudyStore) -> None:
    """Simulate a stalled/dead owner: stop its heartbeat and age it past TTL."""
    store._stop_heartbeat()
    store.conn.execute(
        "UPDATE runner_lease SET heartbeat_at = ? WHERE singleton = 1",
        (time.time() - store.LEASE_TTL_SECONDS - 1,),
    )


def test_second_live_runner_refused(tmp_path):
    db = tmp_path / "study.db"
    compat = compat_with_strategy_config("cfg-v1")
    a = StudyStore.create_or_open(db, compat)
    a.acquire_lease()
    b = StudyStore.create_or_open(db, compat)
    with pytest.raises(StudyLocked):
        b.acquire_lease()
    a.close()
    b.close()


def test_lease_fence_blocks_reclaimed_writer(tmp_path):
    db = tmp_path / "study.db"
    compat = compat_with_strategy_config("cfg-v1")
    a = StudyStore.create_or_open(db, compat)
    a.acquire_lease()

    force_dead(a)

    b = StudyStore.create_or_open(db, compat)
    b.acquire_lease()  # b mints a new lease_id, reclaiming the dead one
    assert b.lease_id != a.lease_id

    with pytest.raises(StudyLeaseLost):
        a.commit_case(
            candidate_id="cand-X",
            proposal_id="p0000",
            attempt_id="cand-X:a1",
            state="completed",
            inputs={"x": 1.0},
            evidence_json={"outputs": {"y": 1.0}},
        )
    assert not b.has_case("cand-X")  # a's fenced write never landed

    a.close()
    b.close()
