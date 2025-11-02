from __future__ import annotations

from pathlib import Path

import pytest

from simkit.config import environment as env


def test_resolve_output_dir_defaults_when_env_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYRONDO_OUTPUT_DIR", raising=False)
    monkeypatch.setattr(env, "_PROJECT_ROOT", tmp_path)

    result = env.resolve_output_dir()

    expected_base = (tmp_path / "run_data" / "outputs").resolve()
    assert result.base_dir == expected_base
    assert result.run_name == "pipeline-run"


def test_resolve_output_dir_prefers_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    override = tmp_path / "custom"
    monkeypatch.setenv("PYRONDO_OUTPUT_DIR", str(override))

    result = env.resolve_output_dir()

    assert result.base_dir == override.resolve()
    assert result.run_name == "pipeline-run"


def test_resolve_output_dir_prefers_argument(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PYRONDO_OUTPUT_DIR", str(tmp_path / "ignored"))
    preferred = tmp_path / "preferred"

    result = env.resolve_output_dir(preferred=preferred, run_name=" Demo Linear ")

    assert result.base_dir == preferred.resolve()
    assert result.run_name == "demo-linear"


def test_resolve_output_dir_sanitizes_run_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(env, "_PROJECT_ROOT", tmp_path)

    result = env.resolve_output_dir(run_name="!!!")

    assert result.run_name == "pipeline-run"
