"""Throwaway S6 machinery: a crash-safe study lifecycle over a fake evaluator.

This is a SPIKE probe, not production code. It exists only to de-risk the
concept's study layer: three-layer identity (proposal / candidate / attempt),
atomic case commit, the artifact staging protocol, resume idempotency scoped to
(study_id, candidate_id), and the store's compatibility binding.

The evaluator here is deliberately tiny and deterministic. S6's scope says the
lifecycle machinery is the risk; the evaluator is fake by design and matches the
S5 shape (typed inputs -> immutable evidence). A real S4-package evaluator could
drop into `FakeEvaluator`'s place without touching the runner or store.

It uses only the Python standard library so the probe reproduces with plain
`python3` (no teax/simkit import needed for the fake-evaluator pass).

Runnable as a subprocess child so the driver can inject a hard `os._exit` crash
at an exact point and then resume in a fresh process:

    python3 study_lifecycle.py run --db PATH [--crash-at PHASE:CANDIDATE_ID]

`PHASE` is `mid_staging` (crash with the artifact tmp truncated, final absent) or
`before_commit` (crash with the artifact durable but the case row not yet
committed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


# --------------------------------------------------------------------------
# Canonical serialization + identity
# --------------------------------------------------------------------------

def canonical_bytes(obj: Any) -> bytes:
    """Deterministic JSON bytes: sorted keys, no incidental whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_of(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


# --------------------------------------------------------------------------
# Compatibility binding (bound once at store creation)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Compatibility:
    study_id: str
    executable_fingerprint: str
    model_contract_fingerprint: str
    study_definition_fingerprint: str
    input_schema_version: str
    evidence_schema_version: str
    strategy_identity: str
    strategy_config: str

    def as_row(self) -> tuple:
        return (
            1,
            self.study_id,
            self.executable_fingerprint,
            self.model_contract_fingerprint,
            self.study_definition_fingerprint,
            self.input_schema_version,
            self.evidence_schema_version,
            self.strategy_identity,
            self.strategy_config,
        )


class IncompatibleStore(Exception):
    """Raised when opening a store whose bound fingerprints differ."""


# --------------------------------------------------------------------------
# Evaluator protocol (S5 shape) + a fake, deterministic implementation
# --------------------------------------------------------------------------

class ExecutionFailed(Exception):
    """The model could not complete an evaluation (a terminal case state)."""


class RetryableError(Exception):
    """A transient infrastructure failure; retry with a new attempt_id."""


class AssessmentFailed(Exception):
    """Policy/objective extraction failed; evidence is still preserved."""


@dataclass(frozen=True)
class Evidence:
    """Immutable evidence envelope, matching the S5 evaluator return shape."""

    outputs: Mapping[str, Any]
    report: Mapping[str, Any]

    def to_json(self) -> dict:
        return {"outputs": dict(self.outputs), "report": dict(self.report)}


class FakeEvaluator:
    """Deterministic evaluator covering every outcome S6 must exercise.

    `kind` in the canonical inputs selects the outcome. A real evaluator would
    ignore `kind` and actually run the sealed package; the lifecycle around it is
    identical.
    """

    def evaluate(self, inputs: Mapping[str, Any], attempt_number: int) -> Evidence:
        kind = inputs["kind"]
        x = inputs["x"]

        if kind == "exec_fail":
            raise ExecutionFailed("model diverged")

        if kind == "retry_once":
            # Terminal only if we never get a second try; the runner retries.
            if attempt_number < 2:
                raise RetryableError("transient staging backend hiccup")
            return Evidence(
                outputs={"y": x * 2.0},
                report={"headline": "all-satisfied",
                        "constraints": [{"id": "c_pos", "status": "satisfied"}]},
            )

        if kind == "all_satisfied":
            return Evidence(
                outputs={"y": x * 2.0},
                report={"headline": "all-satisfied",
                        "constraints": [{"id": "c_pos", "status": "satisfied",
                                         "margin": x}]},
            )

        if kind == "violation":
            return Evidence(
                outputs={"y": x * 2.0},
                report={"headline": "violation",
                        "constraints": [{"id": "c_budget", "status": "violated",
                                         "margin": -x}]},
            )

        if kind == "indeterminate":
            # A non-finite operand: represented as null (JSON-stable) with an
            # explicit indeterminate status, never a real float NaN.
            return Evidence(
                outputs={"y": None},
                report={"headline": "indeterminate",
                        "constraints": [{"id": "c_ratio", "status": "indeterminate",
                                         "operand": None}]},
            )

        if kind == "zero_assertions":
            return Evidence(
                outputs={"y": x * 2.0},
                report={"headline": "not-assessed", "constraints": []},
            )

        if kind == "assess_fail":
            # Evaluation SUCCEEDS and returns evidence. The poison marker only
            # trips the policy downstream, so the case is assessment_failed with
            # its evidence preserved.
            return Evidence(
                outputs={"y": x * 2.0, "poison": True},
                report={"headline": "all-satisfied",
                        "constraints": [{"id": "c_pos", "status": "satisfied"}]},
            )

        raise ExecutionFailed(f"unknown kind {kind!r}")


class DeterministicPolicy:
    """Maps evidence -> a disposition. Never mutates evidence."""

    def assess(self, evidence: Evidence) -> dict:
        if evidence.outputs.get("poison"):
            raise AssessmentFailed("objective extraction failed on poisoned output")
        headline = evidence.report["headline"]
        disposition = {
            "all-satisfied": "feasible",
            "violation": "infeasible",
            "indeterminate": "indeterminate",
            "not-assessed": "not-assessed",
        }[headline]
        return {"disposition": disposition, "headline": headline}


# --------------------------------------------------------------------------
# Prepared-candidates strategy (ignores feedback, by design)
# --------------------------------------------------------------------------

class PreparedCandidateStrategy:
    identity = "prepared-candidates/v1"

    def __init__(self, proposals: list[dict]) -> None:
        self.proposals = proposals

    def config_fingerprint(self) -> str:
        return digest_of(self.proposals)

    def propose(self, study_id: str) -> Iterable[tuple[str, dict]]:
        for index, raw in enumerate(self.proposals):
            yield f"{study_id}:p{index:04d}", raw

    def observe(self, feedback: Any) -> None:  # noqa: D401 - deliberately inert
        # A prepared list ignores feedback. S6 does not claim feedback crash
        # semantics (that is S7); this method exists only to keep the runner
        # order honest.
        return None


def validate_and_canonicalize(raw: Mapping[str, Any]) -> Optional[dict]:
    """Return canonical inputs for a valid proposal, or None if invalid.

    Domain rule: `kind` known and `x` a finite number in [0, 100].
    """
    known = {
        "all_satisfied", "violation", "indeterminate", "zero_assertions",
        "assess_fail", "exec_fail", "retry_once",
    }
    kind = raw.get("kind")
    x = raw.get("x")
    if kind not in known:
        return None
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        return None
    if not (0.0 <= float(x) <= 100.0):
        return None
    return {"kind": kind, "x": float(x)}


# --------------------------------------------------------------------------
# Crash controller
# --------------------------------------------------------------------------

class CrashController:
    """Injects a hard os._exit at an exact (phase, candidate_id)."""

    def __init__(self, spec: Optional[str]) -> None:
        self.phase: Optional[str] = None
        self.candidate_id: Optional[str] = None
        if spec:
            phase, candidate_id = spec.split(":", 1)
            self.phase = phase
            self.candidate_id = candidate_id

    def maybe_crash(self, phase: str, candidate_id: str) -> None:
        if phase == self.phase and candidate_id == self.candidate_id:
            sys.stdout.flush()
            sys.stderr.flush()
            # Hard exit: skips all Python finally/atexit/buffer flushing, the way
            # a killed process would. Anything durable at this point survived
            # because it was fsync'd before we got here.
            os._exit(137)


# --------------------------------------------------------------------------
# Store: SQLite + content-addressed artifact staging
# --------------------------------------------------------------------------

def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class StudyStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.root = db_path.parent
        self.artifacts_dir = self.root / "artifacts"
        self.staging_dir = self.root / "staging"
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.row_factory = sqlite3.Row

    # -- lifecycle -----------------------------------------------------------

    @classmethod
    def create_or_open(cls, db_path: Path, compat: Compatibility) -> "StudyStore":
        exists = db_path.exists()
        store = cls(db_path)
        if not exists:
            store._init_schema()
            store._bind_compatibility(compat)
        else:
            store._check_compatibility(compat)
        store.artifacts_dir.mkdir(exist_ok=True)
        store.staging_dir.mkdir(exist_ok=True)
        return store

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE compatibility (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                study_id TEXT NOT NULL,
                executable_fingerprint TEXT NOT NULL,
                model_contract_fingerprint TEXT NOT NULL,
                study_definition_fingerprint TEXT NOT NULL,
                input_schema_version TEXT NOT NULL,
                evidence_schema_version TEXT NOT NULL,
                strategy_identity TEXT NOT NULL,
                strategy_config TEXT NOT NULL
            );
            CREATE TABLE proposals (
                proposal_id TEXT PRIMARY KEY,
                raw_json TEXT NOT NULL,
                valid INTEGER NOT NULL,
                reject_reason TEXT,
                candidate_id TEXT
            );
            CREATE TABLE attempts (
                attempt_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                proposal_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                outcome TEXT NOT NULL
            );
            CREATE TABLE cases (
                commit_order INTEGER PRIMARY KEY AUTOINCREMENT,
                study_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                proposal_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                state TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                evidence_digest TEXT NOT NULL,
                assessment_json TEXT,
                UNIQUE (study_id, candidate_id)
            );
            """
        )
        self.conn.commit()

    def _bind_compatibility(self, compat: Compatibility) -> None:
        self.conn.execute(
            "INSERT INTO compatibility VALUES (?,?,?,?,?,?,?,?,?)", compat.as_row()
        )
        self.conn.commit()

    def _check_compatibility(self, compat: Compatibility) -> None:
        row = self.conn.execute("SELECT * FROM compatibility").fetchone()
        bound = Compatibility(
            study_id=row["study_id"],
            executable_fingerprint=row["executable_fingerprint"],
            model_contract_fingerprint=row["model_contract_fingerprint"],
            study_definition_fingerprint=row["study_definition_fingerprint"],
            input_schema_version=row["input_schema_version"],
            evidence_schema_version=row["evidence_schema_version"],
            strategy_identity=row["strategy_identity"],
            strategy_config=row["strategy_config"],
        )
        if bound != compat:
            raise IncompatibleStore(
                f"store bound to {bound} but opened with {compat}"
            )

    @property
    def study_id(self) -> str:
        return self.conn.execute(
            "SELECT study_id FROM compatibility"
        ).fetchone()["study_id"]

    # -- proposals -----------------------------------------------------------

    def record_proposal(
        self,
        proposal_id: str,
        raw: Mapping[str, Any],
        valid: bool,
        candidate_id: Optional[str],
        reason: Optional[str],
    ) -> None:
        # Append-only; idempotent under resume via INSERT OR IGNORE.
        self.conn.execute(
            "INSERT OR IGNORE INTO proposals VALUES (?,?,?,?,?)",
            (proposal_id, json.dumps(raw, sort_keys=True), int(valid), reason, candidate_id),
        )
        self.conn.commit()

    # -- attempts ------------------------------------------------------------

    def next_attempt_number(self, candidate_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM attempts WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        return row["n"] + 1

    def record_attempt(
        self, attempt_id: str, candidate_id: str, proposal_id: str,
        attempt_number: int, outcome: str,
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO attempts VALUES (?,?,?,?,?)",
            (attempt_id, candidate_id, proposal_id, attempt_number, outcome),
        )
        self.conn.commit()

    # -- cases ---------------------------------------------------------------

    def has_case(self, candidate_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM cases WHERE study_id = ? AND candidate_id = ?",
            (self.study_id, candidate_id),
        ).fetchone()
        return row is not None

    def _stage_artifact(
        self, attempt_id: str, evidence_json: dict, crash: CrashController,
        candidate_id: str,
    ) -> str:
        """Content-addressed staging: write tmp, fsync, atomic rename.

        A reader can never see a half-written file at the final path because the
        final path only appears via an atomic rename of a fully-fsync'd tmp.
        """
        payload = canonical_bytes(evidence_json)
        digest = hashlib.sha256(payload).hexdigest()
        final_path = self.artifacts_dir / f"{digest}.json"
        if final_path.exists():
            # Deterministic evidence already durably staged (resume path).
            return digest

        tmp = self.staging_dir / f"{attempt_id}.tmp"
        with open(tmp, "wb") as handle:
            half = len(payload) // 2
            handle.write(payload[:half])
            handle.flush()
            os.fsync(handle.fileno())
            # Crash mid-staging: tmp is truncated, final path absent.
            crash.maybe_crash("mid_staging", candidate_id)
            handle.write(payload[half:])
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, final_path)  # atomic
        _fsync_dir(self.artifacts_dir)
        return digest

    def commit_case(
        self,
        *,
        candidate_id: str,
        proposal_id: str,
        attempt_id: str,
        state: str,
        inputs: Mapping[str, Any],
        evidence_json: dict,
        assessment: Optional[dict],
        crash: CrashController,
    ) -> str:
        # 1. Stage the artifact durably (outside any DB transaction).
        digest = self._stage_artifact(attempt_id, evidence_json, crash, candidate_id)

        # 2. Artifact is durable; the case row is not yet committed.
        crash.maybe_crash("before_commit", candidate_id)

        # 3. One DB transaction inserts the case referencing the durable digest.
        #    UNIQUE(study_id, candidate_id) backstops idempotency.
        with self.conn:
            self.conn.execute(
                "INSERT INTO cases "
                "(study_id, candidate_id, proposal_id, attempt_id, state, "
                " inputs_json, evidence_digest, assessment_json) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    self.study_id, candidate_id, proposal_id, attempt_id, state,
                    json.dumps(inputs, sort_keys=True), digest,
                    json.dumps(assessment, sort_keys=True) if assessment else None,
                ),
            )
        return digest

    def ordered_cases(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM cases ORDER BY commit_order"
        ).fetchall()
        return [dict(row) for row in rows]

    def referenced_digests(self) -> set[str]:
        return {
            row["evidence_digest"]
            for row in self.conn.execute("SELECT evidence_digest FROM cases")
        }

    def close(self) -> None:
        self.conn.close()


# --------------------------------------------------------------------------
# Runner: the one fixed order from the concept
# --------------------------------------------------------------------------

RETRY_LIMIT = 3


class StudyRunner:
    def __init__(
        self, store: StudyStore, strategy: PreparedCandidateStrategy,
        evaluator: FakeEvaluator, policy: DeterministicPolicy,
        crash: CrashController,
    ) -> None:
        self.store = store
        self.strategy = strategy
        self.evaluator = evaluator
        self.policy = policy
        self.crash = crash

    def run(self) -> None:
        study_id = self.store.study_id
        for index, (proposal_id, raw) in enumerate(self.strategy.propose(study_id)):
            canonical = validate_and_canonicalize(raw)
            if canonical is None:
                # Invalid proposal: a ProposalRecord, never a candidate/case.
                self.store.record_proposal(
                    proposal_id, raw, valid=False, candidate_id=None,
                    reason="failed validation/domain",
                )
                continue

            candidate_id = f"{study_id}:c{index:04d}"
            self.store.record_proposal(
                proposal_id, raw, valid=True, candidate_id=candidate_id, reason=None,
            )

            # Resume idempotency: scoped to (study_id, candidate_id).
            if self.store.has_case(candidate_id):
                continue

            self._evaluate_candidate(candidate_id, proposal_id, canonical)
            self.strategy.observe(feedback=None)

    def _evaluate_candidate(
        self, candidate_id: str, proposal_id: str, inputs: Mapping[str, Any],
    ) -> None:
        for _ in range(RETRY_LIMIT):
            attempt_number = self.store.next_attempt_number(candidate_id)
            attempt_id = f"{candidate_id}:a{attempt_number}"
            self.store.record_attempt(
                attempt_id, candidate_id, proposal_id, attempt_number, "started",
            )

            # -- evaluate --
            try:
                evidence = self.evaluator.evaluate(inputs, attempt_number)
            except RetryableError:
                self.store.record_attempt(
                    attempt_id, candidate_id, proposal_id, attempt_number,
                    "retryable_failed",
                )
                continue  # new attempt_id, same candidate_id
            except ExecutionFailed as error:
                failure = {"failure": {"phase": "evaluate", "cause": str(error)}}
                self.store.commit_case(
                    candidate_id=candidate_id, proposal_id=proposal_id,
                    attempt_id=attempt_id, state="execution_failed",
                    inputs=inputs, evidence_json=failure, assessment=None,
                    crash=self.crash,
                )
                self.store.record_attempt(
                    attempt_id, candidate_id, proposal_id, attempt_number,
                    "execution_failed",
                )
                return

            # -- assess --
            try:
                assessment = self.policy.assess(evidence)
            except AssessmentFailed as error:
                # Evidence is preserved; only the disposition is a failure.
                self.store.commit_case(
                    candidate_id=candidate_id, proposal_id=proposal_id,
                    attempt_id=attempt_id, state="assessment_failed",
                    inputs=inputs, evidence_json=evidence.to_json(),
                    assessment={"failure": str(error)}, crash=self.crash,
                )
                self.store.record_attempt(
                    attempt_id, candidate_id, proposal_id, attempt_number,
                    "assessment_failed",
                )
                return

            # -- completed --
            self.store.commit_case(
                candidate_id=candidate_id, proposal_id=proposal_id,
                attempt_id=attempt_id, state="completed",
                inputs=inputs, evidence_json=evidence.to_json(),
                assessment=assessment, crash=self.crash,
            )
            self.store.record_attempt(
                attempt_id, candidate_id, proposal_id, attempt_number, "committed",
            )
            return

        raise RuntimeError(f"retry limit exhausted for {candidate_id}")


# --------------------------------------------------------------------------
# Fixed study definition shared by the driver and every child process
# --------------------------------------------------------------------------

# Index -> proposal. Order is meaningful and stable.
PROPOSALS: list[dict] = [
    {"kind": "all_satisfied", "x": 10.0},    # 0 -> completed / feasible
    {"kind": "violation", "x": 20.0},        # 1 -> completed / infeasible
    {"kind": "indeterminate", "x": 30.0},    # 2 -> completed / indeterminate
    {"kind": "all_satisfied", "x": 999.0},   # 3 -> INVALID (x out of domain)
    {"kind": "exec_fail", "x": 40.0},        # 4 -> execution_failed case
    {"kind": "assess_fail", "x": 50.0},      # 5 -> assessment_failed case
    {"kind": "zero_assertions", "x": 60.0},  # 6 -> completed / not-assessed
    {"kind": "all_satisfied", "x": 15.0},    # 7 -> replicate A
    {"kind": "all_satisfied", "x": 15.0},    # 8 -> replicate B (identical inputs)
    {"kind": "retry_once", "x": 70.0},       # 9 -> completed after a retry (a2)
]

STUDY_ID = "study-s6-fake"


def default_compatibility() -> Compatibility:
    strategy = PreparedCandidateStrategy(PROPOSALS)
    return Compatibility(
        study_id=STUDY_ID,
        executable_fingerprint="exe-fingerprint-A",
        model_contract_fingerprint="contract-fingerprint-A",
        study_definition_fingerprint=digest_of(PROPOSALS),
        input_schema_version="input-v1",
        evidence_schema_version="evidence-v1",
        strategy_identity=strategy.identity,
        strategy_config=strategy.config_fingerprint(),
    )


def run_study(db_path: Path, crash_spec: Optional[str]) -> None:
    compat = default_compatibility()
    store = StudyStore.create_or_open(db_path, compat)
    runner = StudyRunner(
        store,
        PreparedCandidateStrategy(PROPOSALS),
        FakeEvaluator(),
        DeterministicPolicy(),
        CrashController(crash_spec),
    )
    try:
        runner.run()
    finally:
        store.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--db", required=True)
    run_parser.add_argument("--crash-at", default=None)
    args = parser.parse_args(argv)

    if args.cmd == "run":
        run_study(Path(args.db), args.crash_at)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
