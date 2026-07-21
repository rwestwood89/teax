"""Phase 1: `StudyConfig` semantic fingerprint (D2/B1, config round-trip)."""
from __future__ import annotations

from simkit.study.config import load_study_config

from .conftest import write_grid_config


def test_semantic_fingerprint_stable_across_reload(tmp_path):
    cfg_path = write_grid_config(tmp_path)
    fp1 = load_study_config(cfg_path).semantic_fingerprint()
    fp2 = load_study_config(cfg_path).semantic_fingerprint()
    assert fp1 == fp2


def test_fingerprint_ignores_filesystem_locations(tmp_path):
    base = load_study_config(write_grid_config(tmp_path)).semantic_fingerprint()
    moved = load_study_config(
        write_grid_config(tmp_path, package_dir="/elsewhere")
    ).semantic_fingerprint()
    assert base == moved


def test_fingerprint_shifts_on_each_shaping_field(tmp_path):
    base = load_study_config(write_grid_config(tmp_path)).semantic_fingerprint()
    # entry_model dropped from the study fingerprint (Item 9): the channel/model
    # binding now lives in model_contract_fingerprint, not the study config.
    for edit in ["study_id", "grid_order", "grid_domain", "fixed", "policy", "budget"]:
        edited = load_study_config(write_grid_config(tmp_path, edit=edit)).semantic_fingerprint()
        assert edited != base, f"fingerprint did not shift for edit={edit!r}"
