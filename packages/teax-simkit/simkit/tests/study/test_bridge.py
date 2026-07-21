"""CandidateBridge: complete typed mapping over zero, one, or many entry
channels (Lifecycle Item 9).

The real three-channel IFE package proves "many" end to end in the fusion
study; these unit tests prove the bridge *shape* — one (the toy fixture),
zero (empty channel set), synthetic many, and the field-level fail-closed
guards — without needing a generated package per shape.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from simkit.evaluation.entry_source import MappingEntrySource
from simkit.evaluation.failure import EvaluationFailed, EvaluationPhase
from simkit.study.bridge import CandidateBridge

from .conftest import ENTRY_CH, FIXED


# --- synthetic multi-channel models (globally-unique PQN-style field names) ---
class ChannelA(BaseModel):
    a__x: float = Field(default=1.0)
    a__y: float = Field(default=2.0)


class ChannelB(BaseModel):
    b__z: float = Field(default=3.0)


MANY = {"chan_a": ChannelA, "chan_b": ChannelB}


# --- ONE: the real single-channel toy fixture -------------------------------
def test_bridge_one_channel_builds_and_validates(prepared):
    bridge = CandidateBridge(prepared.entry_models)
    entry = bridge.build({"toy_plant__Toy_Plant__plant_budget": 6000.0, **FIXED})
    assert set(entry) == {ENTRY_CH}
    prepared._source.validate(entry)  # must not raise ENTRY_VALIDATION


def test_bridge_one_defaults_unselected(prepared):
    bridge = CandidateBridge(prepared.entry_models)
    entry = bridge.build({"toy_plant__Toy_Plant__plant_budget": 6000.0})
    model = entry[ENTRY_CH]
    assert model.toy_plant__Toy_Plant__plant_length == 4.0  # modeled default retained
    assert model.toy_plant__Toy_Plant__plant_budget == 6000.0


# --- MANY: candidate fields partition across channels; unselected default ----
def test_bridge_many_partitions_by_owning_channel():
    bridge = CandidateBridge(MANY)
    entry = bridge.build({"a__x": 10.0, "b__z": 30.0})
    assert set(entry) == {"chan_a", "chan_b"}
    assert entry["chan_a"].a__x == 10.0
    assert entry["chan_a"].a__y == 2.0  # unselected field keeps its default
    assert entry["chan_b"].b__z == 30.0


def test_bridge_many_omits_no_unrelated_channel():
    """A candidate touching only chan_a still yields a complete chan_b (inv 47)."""
    bridge = CandidateBridge(MANY)
    entry = bridge.build({"a__x": 10.0})
    assert set(entry) == {"chan_a", "chan_b"}  # chan_b present, all defaults
    assert entry["chan_b"].b__z == 3.0


# --- ZERO: empty channel set -> empty complete mapping, validates ------------
def test_bridge_zero_channels_builds_empty_mapping():
    bridge = CandidateBridge({})
    entry = bridge.build({})
    assert entry == {}
    # The evaluate seam validates an empty mapping completely: nothing
    # missing, nothing extra.
    source = MappingEntrySource(expected_types={})
    assert dict(source.validate(entry)) == {}


# --- field-level fail-closed guards -----------------------------------------
def test_bridge_unknown_field_fails_closed():
    bridge = CandidateBridge(MANY)
    with pytest.raises(EvaluationFailed) as exc:
        bridge.build({"not_a_declared_field": 1.0})
    assert exc.value.failure.phase == EvaluationPhase.ENTRY_VALIDATION


def test_bridge_malformed_value_fails_closed():
    bridge = CandidateBridge(MANY)
    with pytest.raises(EvaluationFailed) as exc:
        bridge.build({"a__x": "not-a-number"})
    assert exc.value.failure.phase == EvaluationPhase.ENTRY_VALIDATION


def test_bridge_defaultless_unselected_field_fails_closed():
    """A1 arm: a defaultless required field the candidate omits fails closed
    at baseline construction — never an invented value."""
    class Defaultless(BaseModel):
        req__field: float  # no default (an intended codegen output)

    bridge = CandidateBridge({"chan": Defaultless})
    with pytest.raises(EvaluationFailed) as exc:
        bridge.build({})
    assert exc.value.failure.phase == EvaluationPhase.ENTRY_VALIDATION


def test_bridge_ambiguous_field_across_channels_fails_at_construction():
    """A2 guard: a field two channels declare is a package-shape defect."""
    class Dup1(BaseModel):
        shared__f: float = Field(default=0.0)

    class Dup2(BaseModel):
        shared__f: float = Field(default=0.0)

    with pytest.raises(ValueError, match="ambiguous"):
        CandidateBridge({"c1": Dup1, "c2": Dup2})
