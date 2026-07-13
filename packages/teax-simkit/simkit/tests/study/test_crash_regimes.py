"""Full Appendix B oracle: S6 crash regimes + cross-candidate invariants,
against the real evaluator via the production runner.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from simkit.study.identity import mint_attempt_id, mint_candidate_id
from simkit.study.policy import DispositionPolicy
from simkit.study.store import StudyStore

from .conftest import STUDY_ID, artifact_present_and_valid, build_definition

CAND = lambda i: mint_candidate_id(STUDY_ID, i)  # noqa: E731

# Fields that define a logical case. attempt_id and commit_order are
# deliberately excluded: a resumed run legitimately commits the crashed
# candidate on a later attempt, and the row's autoincrement id differs
# across processes.
CASE_KEYS = (
    "candidate_id", "proposal_id", "state", "inputs_json",
    "evidence_digest", "failure_json", "assessment_json",
)


def child_run(db: Path, link_root: Path, crash_at: str | None = None) -> int:
    cmd = [
        sys.executable, "-m", "simkit.tests.study._study_child",
        "--db", str(db), "--link-root", str(link_root),
    ]
    if crash_at:
        cmd += ["--crash-at", crash_at]
    return subprocess.run(cmd).returncode


def logical_cases(store: StudyStore) -> list[dict]:
    return [{k: row[k] for k in CASE_KEYS} for row in store.ordered_cases()]


def open_store(db: Path, prepared) -> StudyStore:
    definition = build_definition(prepared, DispositionPolicy())
    return StudyStore.create_or_open(db, definition.compatibility())


def test_crash_before_commit(tmp_path, prepared):
    link_root = tmp_path / "link_root"
    db = tmp_path / "before_commit" / "study.db"
    db.parent.mkdir()

    rc = child_run(db, link_root, crash_at=f"before_commit:{CAND(0)}")
    assert rc != 0  # genuine process death

    store = open_store(db, prepared)
    try:
        assert not store.has_case(CAND(0))  # INV-C: no dangling case at the crash
    finally:
        store.close()


def test_crash_mid_staging(tmp_path, prepared):
    link_root = tmp_path / "link_root"
    db = tmp_path / "mid_staging" / "study.db"
    db.parent.mkdir()

    rc = child_run(db, link_root, crash_at=f"mid_staging:{CAND(6)}")
    assert rc != 0

    store = open_store(db, prepared)
    try:
        assert not store.has_case(CAND(6))
        staging_tmps = list(store.staging_dir.glob("*/*.tmp"))
        assert len(staging_tmps) >= 1  # orphan tmp, final path absent
    finally:
        store.close()


def test_resume_identical(tmp_path, prepared):
    link_root = tmp_path / "link_root"

    baseline_db = tmp_path / "baseline" / "study.db"
    baseline_db.parent.mkdir()
    assert child_run(baseline_db, link_root, crash_at=None) == 0
    baseline_store = open_store(baseline_db, prepared)
    try:
        baseline_logical = logical_cases(baseline_store)
    finally:
        baseline_store.close()

    resumed_db = tmp_path / "resumed" / "study.db"
    resumed_db.parent.mkdir()
    rc = child_run(resumed_db, link_root, crash_at=f"before_commit:{CAND(0)}")
    assert rc != 0
    rc = child_run(resumed_db, link_root, crash_at=None)  # resume, fresh process
    assert rc == 0

    resumed_store = open_store(resumed_db, prepared)
    try:
        assert logical_cases(resumed_store) == baseline_logical
        rows = [c for c in resumed_store.ordered_cases() if c["candidate_id"] == CAND(0)]
        assert len(rows) == 1  # committed once
        assert rows[0]["attempt_id"] == mint_attempt_id(CAND(0), 2)  # on the post-crash attempt
    finally:
        resumed_store.close()


def test_no_dangling_artifact(tmp_path, prepared):  # both crash legs
    link_root = tmp_path / "link_root"
    for name, seam in (("bc", f"before_commit:{CAND(0)}"), ("ms", f"mid_staging:{CAND(6)}")):
        db = tmp_path / name / "study.db"
        db.parent.mkdir()
        assert child_run(db, link_root, crash_at=seam) != 0
        assert child_run(db, link_root, crash_at=None) == 0

        store = open_store(db, prepared)
        try:
            digests = store.referenced_digests()
            assert digests  # at least the completed cases reference something
            assert all(artifact_present_and_valid(db, digest) for digest in digests)
        finally:
            store.close()


def test_no_double_commit(tmp_path, prepared):  # end-to-end
    link_root = tmp_path / "link_root"
    db = tmp_path / "resume" / "study.db"
    db.parent.mkdir()
    assert child_run(db, link_root, crash_at=f"before_commit:{CAND(0)}") != 0
    assert child_run(db, link_root, crash_at=None) == 0

    store = open_store(db, prepared)
    try:
        candidate_ids = [c["candidate_id"] for c in store.ordered_cases()]
        assert len(candidate_ids) == len(set(candidate_ids))
    finally:
        store.close()


def test_replicates_share_artifact(tmp_path, prepared):
    link_root = tmp_path / "link_root"
    db = tmp_path / "replicates" / "study.db"
    db.parent.mkdir()
    assert child_run(db, link_root, crash_at=None) == 0

    store = open_store(db, prepared)
    try:
        by_candidate = {c["candidate_id"]: c for c in store.ordered_cases()}
        replicate_a, replicate_b = by_candidate[CAND(7)], by_candidate[CAND(8)]
        assert replicate_a["candidate_id"] != replicate_b["candidate_id"]
        assert replicate_a["inputs_json"] == replicate_b["inputs_json"]
        assert replicate_a["evidence_digest"] == replicate_b["evidence_digest"]
    finally:
        store.close()
