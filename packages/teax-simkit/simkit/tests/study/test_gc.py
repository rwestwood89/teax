"""Safe GC: orphan tmps only, never a replicate-shared artifact (L2-1, L3-5)."""
from __future__ import annotations

import pytest

from simkit.study.failures import StudyLocked
from simkit.study.store import StudyStore

from .conftest import compat_with_strategy_config


def test_gc_refuses_while_lease_live(tmp_path):
    db = tmp_path / "study.db"
    store = StudyStore.create_or_open(db, compat_with_strategy_config("cfg-v1"))
    store.acquire_lease()
    with pytest.raises(StudyLocked):
        store.gc()
    store.close()


def test_gc_orphans_only(tmp_path):
    db = tmp_path / "study.db"
    store = StudyStore.create_or_open(db, compat_with_strategy_config("cfg-v1"))
    store.acquire_lease()

    shared_evidence = {"outputs": {"y": 1.0}}
    d1 = store.commit_case(
        candidate_id="cand-A", proposal_id="p0000", attempt_id="cand-A:a1",
        state="completed", inputs={"x": 1.0}, evidence_json=shared_evidence,
    )
    d2 = store.commit_case(
        candidate_id="cand-B", proposal_id="p0001", attempt_id="cand-B:a1",
        state="completed", inputs={"x": 1.0}, evidence_json=shared_evidence,
    )
    assert d1 == d2  # deliberate replicate: identical inputs share one artifact

    lease_dir = store.staging_dir / store.lease_id
    orphan = lease_dir / "cand-Z:a1.tmp"
    orphan.write_bytes(b"partial-garbage")

    store.release_lease()

    report = store.gc()
    assert report == {"tmps_collected": 1, "artifacts_collected": 0}
    assert not orphan.exists()
    assert (store.artifacts_dir / f"{d1}.json").exists()  # shared artifact kept

    store.close()
