"""CandidateBridge: Shape A entry-model construction, against the real entry source."""
from __future__ import annotations

from simkit.study.bridge import CandidateBridge

from .conftest import ENTRY_CH, FIXED


def test_bridge_builds_entry_model(prepared):  # Shape A
    bridge = CandidateBridge(ENTRY_CH, prepared.entry_models[ENTRY_CH])
    entry = bridge.build({"toy_plant__Toy_Plant__plant_budget": 6000.0, **FIXED})
    assert set(entry) == {ENTRY_CH}
    prepared._source.validate(entry)  # must not raise ENTRY_VALIDATION


def test_bridge_defaults_unselected(prepared):
    bridge = CandidateBridge(ENTRY_CH, prepared.entry_models[ENTRY_CH])
    entry = bridge.build({"toy_plant__Toy_Plant__plant_budget": 6000.0})
    model = entry[ENTRY_CH]
    assert model.toy_plant__Toy_Plant__plant_length == 4.0  # modeled default retained
    assert model.toy_plant__Toy_Plant__plant_budget == 6000.0
