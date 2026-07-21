"""Phase 2: B3 (non-finite reaches the verdict), B4 (execute_entry override
contract), INV2 (pre-execution rejection), INV6 (no persisted output), and
fresh-context-per-case isolation — all against the real sealed package.
"""
from __future__ import annotations

import math

import pytest
from pydantic import BaseModel

from simkit.evaluation import EvaluationFailed, EvaluationPhase

from .conftest import AREA_CH, COST_CH, ENTRY_CH, FIXED


def test_nonfinite_budget_reaches_indeterminate_verdict(prepared):  # B3, spec SC5
    params = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=float("nan"), **FIXED)
    evidence = prepared.evaluate({ENTRY_CH: params})
    assert evidence.responses["headline"] == "indeterminate"
    assert math.isfinite(evidence.outputs[AREA_CH])
    assert math.isfinite(evidence.outputs[COST_CH])


def test_satisfied_and_violated_verdicts(prepared):
    satisfied = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=5000.0, **FIXED)
    violated = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=2500.0, **FIXED)
    assert prepared.evaluate({ENTRY_CH: satisfied}).responses["headline"] == "satisfied"
    assert prepared.evaluate({ENTRY_CH: violated}).responses["headline"] == "violated"


def test_execute_entry_override_seeds_channels(prepared):  # B4 mitigation
    params = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=5000.0, **FIXED)
    evidence = prepared.evaluate({ENTRY_CH: params})
    assert evidence.outputs[AREA_CH] == pytest.approx(12.0)
    assert evidence.outputs[COST_CH] == pytest.approx(3000.0)


def test_invalid_typed_input_rejected_before_any_module_runs(prepared):  # INV2 / S5
    class WrongModel(BaseModel):
        pass

    with pytest.raises(EvaluationFailed) as excinfo:
        prepared.evaluate({ENTRY_CH: WrongModel()})
    assert excinfo.value.failure.phase is EvaluationPhase.ENTRY_VALIDATION


def test_no_output_directory_in_no_persist_mode(prepared, tmp_path, monkeypatch):  # INV6 / S5
    monkeypatch.chdir(tmp_path)
    params = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=5000.0, **FIXED)
    prepared.evaluate({ENTRY_CH: params})
    assert not any(tmp_path.iterdir())


def test_fresh_context_per_case_no_channel_bleed(prepared):  # S5 isolation
    a = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=5000.0, **FIXED)
    b = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=2500.0, **FIXED)
    first = prepared.evaluate({ENTRY_CH: a})
    second = prepared.evaluate({ENTRY_CH: b})
    assert first.responses["headline"] == "satisfied"
    assert second.responses["headline"] == "violated"
