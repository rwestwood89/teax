"""Prepared list/grid strategies: determinism (B1, INV-G) and D8 order-sensitivity."""
from __future__ import annotations

import json
import subprocess
import sys

from simkit.study.strategy import GridStrategy, PreparedListStrategy


def _dump_grid_proposals() -> list:
    result = subprocess.run(
        [sys.executable, "-m", "simkit.tests.study._grid_dump"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def test_grid_determinism_pin():  # INV-G, "two processes"
    seq1 = _dump_grid_proposals()
    seq2 = _dump_grid_proposals()
    assert seq1 == seq2  # byte-identical across two fresh processes
    assert len(seq1) == 6  # 3 x 2 domain product
    assert seq1[0][1] == {"plant_budget": 3000.0, "plant_width": 2.0}
    assert seq1[-1][1] == {"plant_budget": 9000.0, "plant_width": 3.0}


def test_proposal_determinism_idempotent():  # L3-3
    proposals = [{"kind": "ok", "x": 1.0}, {"kind": "bad", "x": 999.0}]  # incl an invalid entry
    a = list(PreparedListStrategy(proposals).propose("study-x"))
    b = list(PreparedListStrategy(proposals).propose("study-x"))
    assert a == b


def test_grid_config_is_order_sensitive():  # D8, MF-2
    grid_ab = GridStrategy([("a", [1, 2]), ("b", [3, 4])])
    grid_ba = GridStrategy([("b", [3, 4]), ("a", [1, 2])])
    assert grid_ab.config() == [["a", [1, 2]], ["b", [3, 4]]]
    assert grid_ab.config_fingerprint() != grid_ba.config_fingerprint()
