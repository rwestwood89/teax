"""First proof point (INV-B, INV-C): the store survives both crash seams."""
from __future__ import annotations

import hashlib

from simkit.study.store import StudyStore

from ._store_child import default_compatibility, evidence_digest_for
from .conftest import artifact_present_and_valid, run_store_child


def test_store_seam_before_commit(tmp_path):
    db = tmp_path / "study.db"
    rc = run_store_child(db, crash_at="before_commit:cand-A")
    assert rc != 0  # genuine process death

    store = StudyStore.create_or_open(db, default_compatibility())
    try:
        assert not store.has_case("cand-A")  # INV-C: no dangling case
    finally:
        store.close()
    assert artifact_present_and_valid(db, evidence_digest_for("cand-A"))  # INV-B: durable orphan


def test_store_seam_mid_staging(tmp_path):
    db = tmp_path / "study.db"
    rc = run_store_child(db, crash_at="mid_staging:cand-B")
    assert rc != 0

    digest = evidence_digest_for("cand-B")
    final_path = db.parent / "artifacts" / f"{digest}.json"
    assert not final_path.exists()  # final path absent

    staging_tmps = list((db.parent / "staging").glob("*/*.tmp"))
    assert len(staging_tmps) >= 1
    # The truncated tmp's bytes do not hash to the target digest.
    assert all(hashlib.sha256(tmp.read_bytes()).hexdigest() != digest for tmp in staging_tmps)

    store = StudyStore.create_or_open(db, default_compatibility())
    try:
        assert not store.has_case("cand-B")
        assert store.has_case("cand-A")  # earlier candidate already committed
    finally:
        store.close()

    # Resume: fresh process reproduces the uninterrupted run.
    rc = run_store_child(db, crash_at=None)
    assert rc == 0
    assert artifact_present_and_valid(db, digest)
    store = StudyStore.create_or_open(db, default_compatibility())
    try:
        assert store.has_case("cand-B")
        assert store.has_case("cand-C")
    finally:
        store.close()
