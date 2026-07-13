"""Phase 1 store-level test helpers (no runner/strategy/evaluator)."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from simkit.study.compatibility import Compatibility

HERE = Path(__file__).parent


def run_store_child(db: Path, crash_at: str | None = None) -> int:
    cmd = [sys.executable, "-m", "simkit.tests.study._store_child", "--db", str(db)]
    if crash_at:
        cmd += ["--crash-at", crash_at]
    result = subprocess.run(cmd)
    return result.returncode


def artifact_present_and_valid(db: Path, digest: str) -> bool:
    path = db.parent / "artifacts" / f"{digest}.json"
    if not path.exists():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == digest


def compat_with_strategy_config(strategy_config: str) -> Compatibility:
    return Compatibility(
        study_id="study-compat",
        executable_fingerprint="exe-fp-A",
        model_contract_fingerprint="contract-fp-A",
        study_definition_fingerprint="def-fp-A",
        input_schema_version="input-v1",
        evidence_schema_version="evidence-v1",
        strategy_identity="grid/v1",
        strategy_config=strategy_config,
    )
