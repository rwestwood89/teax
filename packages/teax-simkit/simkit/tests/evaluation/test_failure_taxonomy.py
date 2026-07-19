"""Phase 4: the failure taxonomy is distinguishable and bound to real raise
sites (design.md#implementation-notes phase→failure map), and an
`indeterminate` verdict is evidence, never a failure (INV5, SC3).
"""
from __future__ import annotations

import dataclasses

import pytest
from pydantic import BaseModel

from simkit.core.base import ModuleBase, ModuleResult
from simkit.evaluation import EvaluationFailed, EvaluationPhase

from .conftest import ENTRY_CH, FIXED


class _BrokenAreaModule(ModuleBase):
    """A stand-in module whose run() always raises — exercises module_execution."""

    name = "broken_area"
    version = "test-only"

    def run(self, **kwargs) -> ModuleResult:
        raise RuntimeError("simulated module failure")


def test_module_exception_is_module_execution(prepared):  # SC3 (a)
    registry = prepared._registry
    module_type = "toy_library.Panel_AreaModule"
    original = registry.get(module_type)
    registry._modules[module_type] = dataclasses.replace(original, factory=_BrokenAreaModule)
    try:
        params = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=5000.0, **FIXED)
        with pytest.raises(EvaluationFailed) as excinfo:
            prepared.evaluate({ENTRY_CH: params})
        assert excinfo.value.failure.phase is EvaluationPhase.MODULE_EXECUTION
        assert excinfo.value.failure.module_or_channel == "toy_plant__demo_plant__area_calc"
        assert excinfo.value.failure.cause == "RuntimeError: simulated module failure"
        assert excinfo.value.failure.retryable is False
        assert excinfo.value.failure.partial_artifacts == ()
    finally:
        registry._modules[module_type] = original


def test_entry_rejection_is_entry_validation(prepared):  # SC3 (b) — different phase
    class WrongModel(BaseModel):
        pass

    with pytest.raises(EvaluationFailed) as excinfo:
        prepared.evaluate({ENTRY_CH: WrongModel()})
    assert excinfo.value.failure.phase is EvaluationPhase.ENTRY_VALIDATION
    assert excinfo.value.failure.retryable is False
    assert excinfo.value.failure.phase is not EvaluationPhase.MODULE_EXECUTION


def test_indeterminate_is_evidence_not_failure(prepared):  # SC3 (c) / INV5
    params = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=float("nan"), **FIXED)
    evidence = prepared.evaluate({ENTRY_CH: params})  # returns, does not raise
    assert evidence.responses["headline"] == "indeterminate"


def test_every_raised_failure_is_terminal(prepared):  # D4
    class WrongModel(BaseModel):
        pass

    with pytest.raises(EvaluationFailed) as excinfo:
        prepared.evaluate({ENTRY_CH: WrongModel()})
    assert excinfo.value.failure.retryable is False
