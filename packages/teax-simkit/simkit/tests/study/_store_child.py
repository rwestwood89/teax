"""Phase 1 subprocess driver: store-only, no runner/strategy.

Commits a small fixed sequence of cases directly through the `StudyStore`
API so a driver can inject a hard `os._exit` crash at an exact seam and
resume in a fresh process. Runnable as:

    python -m simkit.tests.study._store_child --db PATH [--crash-at PHASE:CANDIDATE_ID]
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from simkit.study.compatibility import Compatibility
from simkit.study.crash import CrashController
from simkit.study.identity import canonical_bytes
from simkit.study.store import StudyStore

STUDY_ID = "study-p1"

# Index -> (candidate_id, inputs, evidence). Order is meaningful and stable.
CASES: list[tuple[str, dict, dict]] = [
    ("cand-A", {"kind": "a", "x": 1.0}, {"outputs": {"y": 2.0}}),
    ("cand-B", {"kind": "b", "x": 2.0}, {"outputs": {"y": 4.0}}),
    ("cand-C", {"kind": "c", "x": 3.0}, {"outputs": {"y": 6.0}}),
]


def default_compatibility() -> Compatibility:
    return Compatibility(
        study_id=STUDY_ID,
        executable_fingerprint="exe-fp-A",
        model_contract_fingerprint="contract-fp-A",
        study_definition_fingerprint="def-fp-A",
        input_schema_version="input-v1",
        evidence_schema_version="evidence-v1",
        strategy_identity="store-child/v1",
        strategy_config="config-v1",
    )


def evidence_digest_for(candidate_id: str) -> str:
    evidence = next(evidence for cid, _inputs, evidence in CASES if cid == candidate_id)
    return hashlib.sha256(canonical_bytes(evidence)).hexdigest()


def run(db_path: Path, crash_spec: str | None) -> None:
    store = StudyStore.create_or_open(db_path, default_compatibility())
    crash = CrashController(crash_spec)
    try:
        store.acquire_lease()
        for index, (candidate_id, inputs, evidence) in enumerate(CASES):
            proposal_id = f"p{index:04d}"
            store.record_proposal(
                proposal_id, inputs, valid=True, candidate_id=candidate_id, reason=None
            )
            if store.has_case(candidate_id):
                continue
            attempt_number = store.next_attempt_number(candidate_id)
            attempt_id = f"{candidate_id}:a{attempt_number}"
            store.record_transition(
                attempt_id=attempt_id, candidate_id=candidate_id, proposal_id=proposal_id,
                attempt_number=attempt_number, state="started",
            )
            store.commit_case(
                candidate_id=candidate_id, proposal_id=proposal_id, attempt_id=attempt_id,
                state="completed", inputs=inputs, evidence_json=evidence, crash=crash,
            )
            store.record_transition(
                attempt_id=attempt_id, candidate_id=candidate_id, proposal_id=proposal_id,
                attempt_number=attempt_number, state="committed",
            )
        store.release_lease()
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--crash-at", default=None)
    args = parser.parse_args(argv)
    run(Path(args.db), args.crash_at)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
