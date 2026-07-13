"""Phase 4 subprocess driver: the production runner over the real evaluator.

Builds the real `PreparedEvaluator` + `StudyRunner` + `CrashController` and
runs the fixed `PROPOSALS` study (see `conftest.py`), mirroring S6's
`run --db --crash-at`. Runnable as:

    python -m simkit.tests.study._study_child --db PATH --link-root PATH [--crash-at PHASE:CAND]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from simkit.evaluation.evaluator import PreparedEvaluator
from simkit.evaluation.package_load import ProvisionalPackageLoader
from simkit.study.crash import CrashController
from simkit.study.identity import mint_candidate_id
from simkit.study.policy import DispositionPolicy
from simkit.study.runner import StudyRunner
from simkit.study.store import StudyStore

from .conftest import FIXTURE_DIR, SPEC_PATH, STUDY_ID, NamedFaultEvaluator, build_definition


def run(db_path: Path, link_root: Path, crash_spec: str | None) -> None:
    loader = ProvisionalPackageLoader(
        package_dir=FIXTURE_DIR, package_name="wi014_s4", link_root=link_root
    )
    prepared = PreparedEvaluator(loader, SPEC_PATH)
    policy = DispositionPolicy(reject_candidate_ids=frozenset({mint_candidate_id(STUDY_ID, 5)}))
    definition = build_definition(prepared, policy)

    store = StudyStore.create_or_open(db_path, definition.compatibility())
    crash = CrashController(crash_spec)
    try:
        store.acquire_lease()
        StudyRunner(store, definition, NamedFaultEvaluator(prepared), crash).run()
        store.release_lease()
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--link-root", required=True)
    parser.add_argument("--crash-at", default=None)
    args = parser.parse_args(argv)
    run(Path(args.db), Path(args.link_root), args.crash_at)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
