"""Phase 2 subprocess helper: dump a fixed grid's proposal sequence as JSON.

Runnable as: python -m simkit.tests.study._grid_dump
"""
from __future__ import annotations

import json

from simkit.study.strategy import GridStrategy

STUDY_ID = "study-grid-pin"


def build_grid() -> GridStrategy:
    return GridStrategy(
        [
            ("plant_budget", [3000.0, 6000.0, 9000.0]),
            ("plant_width", [2.0, 3.0]),
        ]
    )


def main() -> int:
    proposals = list(build_grid().propose(STUDY_ID))
    print(json.dumps(proposals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
