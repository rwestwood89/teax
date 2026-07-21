"""Phase 2 acceptance round-trip (INV-4): create -> run -> crash -> resume,
over the real evaluator, compared against an uninterrupted reference run.

The de-risk test for B1 (the config rebuilds a byte-identical `StudyDefinition`
across processes, so resume binds instead of forking a lineage) and D8 (the
crash seam is deterministic).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from simkit.study import cli as study_cli
from simkit.study.identity import mint_candidate_id
from simkit.study.store import StudyStore

from .conftest import GRID_STUDY_ID, write_grid_config


def run_cli(argv: list[str], *, subprocess_: bool = False) -> int:
    args = [str(a) for a in argv]
    if subprocess_:
        result = subprocess.run([sys.executable, "-m", "simkit.study.cli", *args])
        return result.returncode
    return study_cli.main(args)


def identity_cols(store: StudyStore) -> list[tuple]:
    return [
        (row["candidate_id"], row["state"], row["evidence_digest"], row["inputs_json"])
        for row in store.ordered_cases()
    ]


def test_resume_reproduces_uninterrupted_cases(tmp_path: Path) -> None:
    cfg = write_grid_config(tmp_path, budgets=[1000.0, 4000.0, 6000.0])
    mid = mint_candidate_id(GRID_STUDY_ID, 1)  # crash on the 2nd grid point

    a_db = tmp_path / "a.db"
    assert run_cli(["create", "--config", cfg, "--store", a_db]) == 0
    rc = run_cli(
        ["run", "--config", cfg, "--store", a_db, "--crash-at", f"before_commit:{mid}"],
        subprocess_=True,
    )
    assert rc == 137
    assert run_cli(["resume", "--config", cfg, "--store", a_db]) == 0

    b_db = tmp_path / "b.db"
    assert run_cli(["create", "--config", cfg, "--store", b_db]) == 0
    assert run_cli(["run", "--config", cfg, "--store", b_db]) == 0

    resumed = StudyStore(a_db)
    reference = StudyStore(b_db)
    assert identity_cols(resumed) == identity_cols(reference)
    assert len(identity_cols(reference)) == 3


def test_resumed_run_is_idempotent(tmp_path: Path) -> None:
    cfg = write_grid_config(tmp_path, budgets=[1000.0, 4000.0, 6000.0])
    db = tmp_path / "s.db"
    assert run_cli(["create", "--config", cfg, "--store", db]) == 0
    assert run_cli(["run", "--config", cfg, "--store", db]) == 0
    before = identity_cols(StudyStore(db))
    assert run_cli(["run", "--config", cfg, "--store", db]) == 0
    after = identity_cols(StudyStore(db))
    assert before == after
