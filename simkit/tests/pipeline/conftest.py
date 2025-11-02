from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import pytest
import yaml


@pytest.fixture
def sample_pipeline_yaml_path() -> Path:
    """Return the path to the demo pipeline YAML contract."""
    return Path(__file__).resolve().parents[1] / "fixtures" / "pipeline_configs" / "demo_linear_alt.yaml"


@pytest.fixture
def sample_pipeline_spec(sample_pipeline_yaml_path: Path) -> Dict[str, Any]:
    """Load the demo pipeline YAML into a dictionary for tests."""
    payload = yaml.safe_load(sample_pipeline_yaml_path.read_text(encoding="utf-8"))
    metadata = payload.setdefault("metadata", {})
    metadata.setdefault("run_description", "Demo linear pipeline for regression coverage")
    metadata.setdefault("output_folder", "pipeline_result_bundle")
    return payload
