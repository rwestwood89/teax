"""Per-case outcomes against the real evaluator (B4): the four `completed`
verdict classes, invalid-proposal handling, and no-double-commit.
"""
from __future__ import annotations

import json

from simkit.study.identity import mint_candidate_id
from simkit.study.policy import DispositionPolicy

from .conftest import NamedFaultEvaluator, STUDY_ID, run_study


def test_completed_matrix(tmp_path, prepared):
    policy = DispositionPolicy(reject_candidate_ids=frozenset({mint_candidate_id(STUDY_ID, 5)}))
    store = run_study(tmp_path, prepared, NamedFaultEvaluator(prepared), policy)
    try:
        cases = store.ordered_cases()
        headlines = {
            c["candidate_id"]: json.loads(c["assessment_json"])["headline"]
            for c in cases
            if c["state"] == "completed"
        }
        assert set(headlines.values()) == {"satisfied", "violated", "indeterminate", "not_assessed"}
    finally:
        store.close()


def test_invalid_proposal_record(tmp_path, prepared):
    policy = DispositionPolicy()
    store = run_study(tmp_path, prepared, NamedFaultEvaluator(prepared), policy)
    try:
        invalid_candidate_id = mint_candidate_id(STUDY_ID, 3)
        assert not store.has_case(invalid_candidate_id)
        row = store.conn.execute(
            "SELECT * FROM proposals WHERE proposal_id = ?", (f"{STUDY_ID}:p0003",)
        ).fetchone()
        assert row is not None
        assert row["valid"] == 0
        assert row["candidate_id"] is None
    finally:
        store.close()


def test_no_double_commit(tmp_path, prepared):
    policy = DispositionPolicy(reject_candidate_ids=frozenset({mint_candidate_id(STUDY_ID, 5)}))
    store = run_study(tmp_path, prepared, NamedFaultEvaluator(prepared), policy)
    try:
        candidate_ids = [c["candidate_id"] for c in store.ordered_cases()]
        assert len(candidate_ids) == len(set(candidate_ids))
    finally:
        store.close()
