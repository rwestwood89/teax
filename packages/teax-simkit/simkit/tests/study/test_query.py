"""Phase 4: `StudyQuery` — both axes (states x verdicts), the catalog join,
`executable_fingerprint` on every result (INV-5), and the CLI's new-lineage
message on a refused resume.
"""
from __future__ import annotations

import pytest

from simkit.study import cli as study_cli
from simkit.study.identity import mint_candidate_id
from simkit.study.policy import DispositionPolicy, ObjectivePolicy, ObjectiveSpec
from simkit.study.query import StudyQuery

from .conftest import COST_CH, FIXTURE_DIR, NamedFaultEvaluator, STUDY_ID, run_study, write_grid_config

# Item 8: the query reads codegen's embedded catalog straight from the package dir's
# model_contract.json — there is no standalone constraint_catalog.json. The constraint_id is the
# real generated id (with its occurrence hash suffix), the key the runtime report also uses.
AFFORDABLE = "toy_plant__demo_plant__affordable__c122240f4b148939"


@pytest.fixture
def built_store(tmp_path, prepared):
    """Runs the fixed PROPOSALS with the disposition-diverse policy
    (mirrors `test_runner_matrix.py`) — real states/verdicts diversity,
    including a genuine `assessment_failed` case."""
    policy = DispositionPolicy(reject_candidate_ids=frozenset({mint_candidate_id(STUDY_ID, 5)}))
    store = run_study(tmp_path, prepared, NamedFaultEvaluator(prepared), policy)
    yield store
    store.close()


@pytest.fixture
def objective_store(tmp_path, prepared):
    """The real `ObjectivePolicy` over the same PROPOSALS, for
    disposition-vocabulary-specific assertions (reject/feed-strategy)."""
    policy = ObjectivePolicy((ObjectiveSpec(COST_CH, "minimize"),), {})
    store = run_study(tmp_path, prepared, NamedFaultEvaluator(prepared), policy)
    yield store
    store.close()


def test_three_states_times_three_verdicts_filterable(built_store):
    query = StudyQuery(built_store, FIXTURE_DIR)
    all_cases = query.cases()
    assert {c.state for c in all_cases} == {"completed", "execution_failed", "assessment_failed"}
    headlines = {c.headline for c in all_cases if c.state == "completed"}
    assert headlines == {"satisfied", "violated", "indeterminate", "not_assessed"}

    completed = query.cases(state="completed")
    assert completed and all(c.state == "completed" for c in completed)
    assessment_failed = query.cases(state="assessment_failed")
    assert assessment_failed and all(c.state == "assessment_failed" for c in assessment_failed)
    execution_failed = query.cases(state="execution_failed")
    assert execution_failed and all(c.state == "execution_failed" for c in execution_failed)


def test_catalog_join_names_failing_instance(built_store):
    query = StudyQuery(built_store, FIXTURE_DIR)
    matches = query.cases(constraint=AFFORDABLE)
    assert matches
    view = matches[0].catalog[AFFORDABLE]
    # Read straight from codegen's embedded catalog — no reconstruction. These are the real
    # generated values, not the hand-authored fixture's (which fabricated membership_kind="assert";
    # the true extracted value here is None). This is a definition-typed usage, so the new
    # definition→usage join FK is populated (F1) — the field TEAx used to recover by predicate-text.
    assert view.source_form == "definition_typed"
    assert view.owner_qn == "toy_plant::'Toy Plant'"
    assert view.definition_qn == "toy_library::'Cost Within Budget'"
    assert view.predicate_ir
    assert view.is_negated is False


def test_every_result_carries_executable_fingerprint(built_store):
    query = StudyQuery(built_store, FIXTURE_DIR)
    cases = query.cases()
    assert cases
    fingerprints = {c.executable_fingerprint for c in cases}
    assert fingerprints == {query._store_fingerprint}


def test_disposition_and_output_filters(objective_store):
    query = StudyQuery(objective_store, FIXTURE_DIR)
    rejected = query.cases(disposition="reject")
    assert rejected and all(c.disposition == "reject" for c in rejected)
    with_cost = query.cases(output=COST_CH)
    assert with_cost and all(COST_CH in c.outputs for c in with_cost)


def test_incompatible_store_yields_new_lineage_message(tmp_path, capsys):
    cfg = write_grid_config(tmp_path, budgets=[1000.0, 4000.0, 6000.0])
    db = tmp_path / "s.db"
    assert study_cli.main(["create", "--config", str(cfg), "--store", str(db)]) == 0

    edited_cfg = write_grid_config(tmp_path, budgets=[1000.0, 4000.0, 6000.0], edit="fixed")
    rc = study_cli.main(["run", "--config", str(edited_cfg), "--store", str(db)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "lineage" in err.lower()
    assert "Traceback" not in err
