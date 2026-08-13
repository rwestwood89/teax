"""Failure routing (B4): execution_failed, assessment_failed, retry, and the
loud bridge-defect path — against the real evaluator + real failure taxonomy.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from simkit.study.definition import StudyDefinition
from simkit.study.failures import StudyBridgeDefect
from simkit.study.identity import digest_of, mint_attempt_id, mint_candidate_id
from simkit.study.policy import DispositionPolicy
from simkit.study.runner import StudyRunner
from simkit.study.store import StudyStore
from simkit.study.strategy import PreparedListStrategy

from .conftest import (
    ENTRY_CH,
    FlakyOnceStore,
    NamedFaultEvaluator,
    STUDY_ID,
    _budget_only,
    run_study,
    validate_proposal,
)


def test_execution_failed(tmp_path, prepared):  # named MODULE_EXECUTION fault
    store = run_study(tmp_path, prepared, NamedFaultEvaluator(prepared), DispositionPolicy())
    try:
        candidate_id = mint_candidate_id(STUDY_ID, 4)
        rows = [c for c in store.ordered_cases() if c["candidate_id"] == candidate_id]
        assert len(rows) == 1
        assert rows[0]["state"] == "execution_failed"
        assert rows[0]["evidence_digest"] is None  # D5
        assert rows[0]["failure_json"] is not None
    finally:
        store.close()


def test_assessment_failed(tmp_path, prepared):  # policy rejection, real evidence preserved
    reject = mint_candidate_id(STUDY_ID, 5)
    policy = DispositionPolicy(reject_candidate_ids=frozenset({reject}))
    store = run_study(tmp_path, prepared, NamedFaultEvaluator(prepared), policy)
    try:
        rows = [c for c in store.ordered_cases() if c["candidate_id"] == reject]
        assert len(rows) == 1
        assert rows[0]["state"] == "assessment_failed"
        assert rows[0]["evidence_digest"] is not None  # real evidence preserved, not a stub
    finally:
        store.close()


def test_retry_new_attempt(tmp_path, prepared):  # store-transient fault, one case on a2
    candidate_id = mint_candidate_id(STUDY_ID, 9)
    store = run_study(
        tmp_path, prepared, NamedFaultEvaluator(prepared), DispositionPolicy(),
        store_cls=FlakyOnceStore,
        configure_store=lambda s: setattr(s, "fail_once_for_candidate", candidate_id),
    )
    try:
        rows = [c for c in store.ordered_cases() if c["candidate_id"] == candidate_id]
        assert len(rows) == 1
        assert rows[0]["attempt_id"] == mint_attempt_id(candidate_id, 2)

        transitions = [
            dict(r)
            for r in store.conn.execute(
                "SELECT * FROM attempt_transitions WHERE candidate_id = ? ORDER BY transition_seq",
                (candidate_id,),
            )
        ]
        states = [(t["attempt_number"], t["state"]) for t in transitions]
        assert (1, "started") in states
        assert (1, "retryable_failed") in states
        assert (2, "started") in states
        assert (2, "committed") in states
    finally:
        store.close()


def _bridge_defect_definition(prepared, *, entry_models, validate, proposals):
    return StudyDefinition(
        study_id="study-bridge-defect",
        entry_models=entry_models,
        strategy=PreparedListStrategy(proposals),
        validate_proposal=validate,
        policy=DispositionPolicy(),
        executable_fingerprint=prepared.fingerprint,
        model_contract_fingerprint="model-contract-v1",
        input_schema_version="input-v1",
        evidence_schema_version=prepared.EVIDENCE_SCHEMA_VERSION,
        study_definition_fingerprint=digest_of(proposals),
    )


def test_bridge_defect_is_loud(tmp_path, prepared):  # a bad bridge raises StudyBridgeDefect, never a case
    # An entry model that declares none of the candidate's fields: every
    # selected field is unknown -> the bridge fails closed, routed loud.
    class WrongModel(BaseModel):
        pass

    proposals = [_budget_only(6000.0)]
    definition = _bridge_defect_definition(
        prepared, entry_models={ENTRY_CH: WrongModel},
        validate=validate_proposal, proposals=proposals,
    )
    db = tmp_path / "study.db"
    store = StudyStore.create_or_open(db, definition.compatibility())
    store.acquire_lease()
    try:
        with pytest.raises(StudyBridgeDefect):
            StudyRunner(store, definition, prepared).run()
        assert store.ordered_cases() == []
    finally:
        store.close()


def test_malformed_mapping_is_recorded_classified_failure(tmp_path, prepared):
    """Item 9 R1: a malformed field value reaching the bridge is a *classified*
    StudyBridgeDefect, not an uncaught crash. RED before the bridge.build call
    was relocated inside the runner's failure switch."""
    def passthrough(raw):
        return dict(raw)  # let a malformed value reach the bridge

    proposals = [{"toy_plant__demo_plant__plant_budget": "not-a-number"}]
    definition = _bridge_defect_definition(
        prepared, entry_models=prepared.entry_models,
        validate=passthrough, proposals=proposals,
    )
    db = tmp_path / "study.db"
    store = StudyStore.create_or_open(db, definition.compatibility())
    store.acquire_lease()
    try:
        with pytest.raises(StudyBridgeDefect):
            StudyRunner(store, definition, prepared).run()
        assert store.ordered_cases() == []  # never a case
    finally:
        store.close()
