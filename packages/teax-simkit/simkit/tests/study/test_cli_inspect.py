"""Phase 5: `teax-study inspect` renders the query as JSON lines; the
optional `budget`/`retention` interpretation (D9)."""
from __future__ import annotations

import json

from simkit.study import cli as study_cli
from simkit.study.identity import mint_candidate_id

from .conftest import GRID_STUDY_ID, write_grid_config


def run_cli(argv: list[str]) -> int:
    return study_cli.main([str(a) for a in argv])


def test_inspect_emits_one_json_line_per_case(tmp_path, capsys):
    cfg = write_grid_config(tmp_path, budgets=[1000.0, 4000.0, 6000.0])
    db = tmp_path / "s.db"
    assert run_cli(["create", "--config", cfg, "--store", db]) == 0
    assert run_cli(["run", "--config", cfg, "--store", db]) == 0
    capsys.readouterr()  # discard create/run output

    assert run_cli(["inspect", "--config", cfg, "--store", db]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert len(lines) == 3
    for record in lines:
        assert "state" in record and "executable_fingerprint" in record


def test_inspect_filters_by_disposition(tmp_path, capsys):
    cfg = write_grid_config(tmp_path, budgets=[1000.0, 4000.0, 6000.0])
    db = tmp_path / "s.db"
    run_cli(["create", "--config", cfg, "--store", db])
    run_cli(["run", "--config", cfg, "--store", db])
    capsys.readouterr()

    run_cli(["inspect", "--config", cfg, "--store", db, "--disposition", "reject"])
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines and all(record["disposition"] == "reject" for record in lines)


def test_inspect_without_a_store_fails_loudly(tmp_path, capsys):
    cfg = write_grid_config(tmp_path)
    rc = run_cli(["inspect", "--config", cfg, "--store", tmp_path / "missing.db"])
    assert rc == 1
    assert "missing.db" in capsys.readouterr().err


def test_budget_below_grid_size_stops_early(tmp_path):
    cfg_path = write_grid_config(tmp_path, budgets=[1000.0, 4000.0, 6000.0])
    import yaml

    raw = yaml.safe_load(cfg_path.read_text())
    raw["budget"] = 2
    cfg_path.write_text(yaml.safe_dump(raw))

    db = tmp_path / "s.db"
    assert run_cli(["create", "--config", cfg_path, "--store", db]) == 0
    assert run_cli(["run", "--config", cfg_path, "--store", db]) == 0

    from simkit.study.store import StudyStore

    store = StudyStore(db)
    try:
        cases = store.ordered_cases()
        assert len(cases) == 2
        assert cases[0]["candidate_id"] == mint_candidate_id(GRID_STUDY_ID, 0)
    finally:
        store.close()


def test_retention_gc_after_runs_without_error(tmp_path):
    cfg_path = write_grid_config(tmp_path, budgets=[1000.0, 4000.0, 6000.0])
    import yaml

    raw = yaml.safe_load(cfg_path.read_text())
    raw["retention"] = "gc_after"
    cfg_path.write_text(yaml.safe_dump(raw))

    db = tmp_path / "s.db"
    assert run_cli(["create", "--config", cfg_path, "--store", db]) == 0
    assert run_cli(["run", "--config", cfg_path, "--store", db]) == 0

    from simkit.study.store import StudyStore

    store = StudyStore(db)
    try:
        assert len(store.ordered_cases()) == 3
    finally:
        store.close()
