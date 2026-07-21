"""Phase 3: INV4 — in-memory and file-backed backends agree over the parity
equivalence class, including NaN-aware numeric-output equality.

F-budget's compared outputs (area, cost) are finite even though the verdict
is `indeterminate` (NaN is confined to the excluded opaque report). F-output
is what actually exercises NaN-aware equality: a non-finite input propagates
to a *compared* output on both legs (design.md#implementation-notes).
"""
from __future__ import annotations

import json
import math

import pytest

from .conftest import AREA_CH, COST_CH, ENTRY_CH, ENTRY_FIXTURES_DIR

CASES = {
    "satisfied": "satisfied",
    "violated": "violated",
    "F_budget": "f_budget",
    "F_output": "f_output",
}


def nan_aware_equal(a: float, b: float) -> bool:
    if a == b:
        return True
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isinf(a) and math.isinf(b):
        return (a > 0) == (b > 0)
    return False


def _load_raw(fixture_name: str) -> dict:
    return json.loads((ENTRY_FIXTURES_DIR / f"{fixture_name}.json").read_text())


@pytest.mark.parametrize("case", list(CASES))
def test_backends_agree(prepared, file_backed, case):
    fixture_name = CASES[case]
    raw = _load_raw(fixture_name)
    params = prepared.entry_models[ENTRY_CH](**raw)

    in_memory = prepared.evaluate({"toy_plant_params": params})
    file_result = file_backed.evaluate(ENTRY_FIXTURES_DIR / f"{fixture_name}.json")

    assert nan_aware_equal(in_memory.outputs[AREA_CH], file_result.outputs[AREA_CH])
    assert nan_aware_equal(in_memory.outputs[COST_CH], file_result.outputs[COST_CH])
    # verdict statuses string-exact; provenance/report excluded from the comparison
    assert in_memory.responses == file_result.responses


def test_f_output_exercises_nan_aware_rule_on_a_compared_output(prepared, file_backed):
    raw = _load_raw("f_output")
    params = prepared.entry_models[ENTRY_CH](**raw)

    in_memory = prepared.evaluate({"toy_plant_params": params})
    file_result = file_backed.evaluate(ENTRY_FIXTURES_DIR / "f_output.json")

    assert math.isnan(in_memory.outputs[AREA_CH])
    assert math.isnan(file_result.outputs[AREA_CH])
    assert math.isnan(in_memory.outputs[COST_CH])
    assert math.isnan(file_result.outputs[COST_CH])


def test_f_budget_compared_outputs_are_finite(prepared, file_backed):
    raw = _load_raw("f_budget")
    params = prepared.entry_models[ENTRY_CH](**raw)

    in_memory = prepared.evaluate({"toy_plant_params": params})
    file_result = file_backed.evaluate(ENTRY_FIXTURES_DIR / "f_budget.json")

    assert math.isfinite(in_memory.outputs[AREA_CH])
    assert math.isfinite(file_result.outputs[AREA_CH])
    assert in_memory.responses["headline"] == "indeterminate"
    assert file_result.responses["headline"] == "indeterminate"
