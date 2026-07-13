# Spike: Crash-Safe Study Lifecycle (S6, first-delivery scope)

## Summary of Findings

**[AGENT] Verdict: confirmed.** A `teax` study store built on SQLite plus a
content-addressed artifact-staging protocol survives hard process crashes
injected both *before case commit* and *mid artifact-staging*, and on resume
reproduces the uninterrupted run exactly. All five S6 pass criteria hold, proven
against a fake deterministic evaluator (the lifecycle machinery is the risk; the
evaluator is fake by design and matches the S5 evaluator shape).

The probe runs 10 prepared proposals through the full order — validate/canonicalize
→ evaluate → assess → stage artifact durably → atomically commit the case →
advance strategy — under three process regimes: uninterrupted, crash-before-commit
then resume, and crash-mid-staging then resume. Crashes are real `os._exit(137)`
child-process deaths (no Python `finally`/`atexit`/buffer-flush runs); resume is a
fresh process against the same DB and artifact directory. 58 invariant checks pass,
green and byte-order-stable across three repeats.

What each S6 pass criterion showed:

- **Resumed and uninterrupted runs produce identical ordered cases.** Both crash
  regimes reproduced the baseline's 9 committed cases in the same candidate order,
  compared on candidate/proposal/state/inputs/evidence-digest/assessment. The only
  intended difference is the `attempt_id` of the crash-injected candidate: the
  baseline commits it on attempt `a1`, the resumed run on `a2` — the crashed
  attempt is preserved in the append-only attempt history, exactly as the
  three-layer identity requires.
- **No logical candidate commits twice under `(study_id, candidate_id)`.** Enforced
  structurally by a `UNIQUE(study_id, candidate_id)` constraint on `cases`, and
  backed operationally by resume skipping any candidate that already has a committed
  case. The crash-before-commit target committed exactly once, on a new attempt.
- **No committed case references a missing or half-written artifact.** Every
  referenced digest resolves to a present file whose SHA-256 re-hashes to that
  digest. At the mid-staging crash the target's final artifact was *absent* and its
  case *uncommitted*; a truncated `.tmp` sat in staging as collectable garbage whose
  bytes do not hash to the digest — so no committed case ever pointed at it.
- **Invalid proposals persist as proposal records, never cases.** The out-of-domain
  proposal (`p0003`, `x=999`) is stored in `proposals` with `valid=0` and no
  `candidate_id`, and never reaches the evaluator or the `cases` table.
- **Opening the store with incompatible fingerprints fails.** Reopening a bound
  store with a mutated `executable_fingerprint` raises `IncompatibleStore`; a
  matching reopen still succeeds.

The tiny evaluator exercised every required outcome and each landed in the right
place: all-satisfied / violation / indeterminate / zero-assertions as three
distinct *completed* cases plus a not-assessed one; a terminal execution failure as
an `execution_failed` case; a policy failure as an `assessment_failed` case with its
real evidence preserved (not a stub); deliberate replicates as two distinct
candidates that share one content-addressed artifact; and a retryable failure as one
committed case reached on a new `attempt_id` (`a2`) with `a1` retained as
`retryable_failed`.

**Bounds of the claim (stated plainly):**
- The crash is `os._exit`, which skips Python-level cleanup but not OS-level
  fsync'd data. This proves the protocol does not depend on graceful shutdown and
  that durability rests on *fsync-before-return*. It does **not** simulate power
  loss or disk-cache loss; a block-layer fault-injection test is out of scope.
- This is the fake-evaluator pass, which is where S6's risk lives. Repeating the
  same lifecycle against S4's sealed generated package is deferred (cross-repo; also
  gated on merging teax's in-flight scalar ExitPoint work — the same S5 prerequisite).
  The evaluator interface matches S5's shape, so a real evaluator drops into
  `FakeEvaluator`'s place without touching the runner or store.

## Question / Goal

**[INHERITED: sysml-codegen constraint-execution concept, S6]** Assumption under
test: a `teax` study store can guarantee — across hard crashes injected before case
commit and mid artifact-staging — that (1) resumed and uninterrupted runs produce
identical ordered cases, (2) no logical candidate commits twice under
`(study_id, candidate_id)`, (3) no committed case references a missing/half-written
artifact, (4) invalid proposals persist as proposal records and never become cases,
and (5) opening the store with incompatible fingerprints fails.

Serves S6 in
`/home/reid/1cfe/sysml-codegen/.project/concepts/constraint-execution-and-design-space-studies-claude.md`.
S6 explicitly permits a fake evaluator for this pass and does **not** claim feedback
crash semantics (a prepared-candidates strategy ignores feedback; that is S7).

## Log

### 2026-07-12 — Context

- Read the concept's Study Layer section and Appendix B S6. Read the S5 findings
  and probe (`../spike-teax-typed-entry-scalar-continuity/`) to inherit the
  evaluator shape: prepare-once, then `evaluate(typed inputs) -> immutable evidence`.
- Confirmed the fake-evaluator pass needs no teax/simkit import — pure stdlib
  (`sqlite3`, `hashlib`, `os`, `subprocess`), so it reproduces with plain `python3`
  (Python 3.12.3, SQLite 3.45.1). This avoids the S5 cross-repo virtualenv setup for
  the part of S6 that is actually at risk.

### 2026-07-12 — Machinery written

Added `study_lifecycle.py` (throwaway): three-layer identity, a
`PreparedCandidateStrategy`, a `FakeEvaluator` covering all seven outcomes, a
`DeterministicPolicy`, a `StudyRunner` following the concept's fixed order, and a
`StudyStore` (SQLite `journal_mode=WAL`, `synchronous=FULL`) with content-addressed
artifact staging: write tmp → fsync → atomic `os.replace` → fsync dir → then a
single DB transaction inserts the case row referencing the durable digest.

Crash injection is a `CrashController` that calls `os._exit(137)` at an exact
`(phase, candidate_id)`. `mid_staging` crashes after fsync of a *half-written* tmp
and before the rename (final path absent). `before_commit` crashes after the
artifact is durable at its final path and before the DB transaction commits.

The module is runnable as a subprocess child (`run --db PATH [--crash-at ...]`) so
crashes are genuine process deaths.

### 2026-07-12 — Driver written and run

Added `probe_crash_safe_study.py`: runs baseline / crash-before-commit / crash-mid-
staging as real child processes, inspects the store at the crash point, resumes in a
fresh process, and checks 58 invariants including the incompatible-fingerprint open.

Command:

```bash
python3 .project/active/spike-crash-safe-study-lifecycle/probe_crash_safe_study.py
```

Observed: exit 0; `ok: true`; `failed: []`; all 58 checks true; 9 committed cases;
baseline candidate order `c0000,c0001,c0002,c0004,c0005,c0006,c0007,c0008,c0009`
(note `c0003` absent — that proposal is invalid). Both resume regimes reproduced
that exact order and logical-case content.

Key observed facts at the crash points:

- **before_commit:** `has_case(c0000)` false, yet the c0000 evidence artifact was
  present and hash-valid — proving *artifact durable before the case commits*.
  After resume, c0000 committed exactly once, on `attempt_id …:a2`.
- **mid_staging:** the c0006 final artifact was absent, no case existed, and a
  truncated `.tmp` was present whose bytes did not hash to the digest. After resume,
  the artifact was present and hash-valid and the case committed.

### 2026-07-12 — Determinism and crash-code checks

Command:

```bash
# two more full runs + a direct crash-child exit code
python3 .project/active/spike-crash-safe-study-lifecycle/probe_crash_safe_study.py   # x2
python3 .project/active/spike-crash-safe-study-lifecycle/study_lifecycle.py \
  run --db "$TMP/s.db" --crash-at "before_commit:study-s6-fake:c0000"
```

Observed: both extra full runs `ok=True failed=[]` with the identical baseline
candidate order; the direct crash child exited `137` (hard `os._exit`, no cleanup).

## Reproduction

From `/home/reid/1cfe/teax`, with any Python 3.10+ (needs only the standard library):

```bash
python3 .project/active/spike-crash-safe-study-lifecycle/probe_crash_safe_study.py
```

Expected: exit status 0 and a JSON report with `"ok": true`, `"failed": []`, all 58
`checks` true, `baseline_case_count: 9`, and the candidate order above. The driver
works in a fresh `mktemp` directory and cleans it up; it writes nothing under the
repo. To watch a real crash directly:

```bash
D=$(mktemp -d)
python3 .project/active/spike-crash-safe-study-lifecycle/study_lifecycle.py \
  run --db "$D/study.db" --crash-at "before_commit:study-s6-fake:c0000"
echo "exit $?"   # -> 137
rm -rf "$D"
```

## Open Questions / Follow-ups

- **[AGENT] S4-package repeat (deferred).** Repeat the identical lifecycle against
  S4's sealed generated package via S5's real prepared-pipeline evaluator, once
  teax's in-flight scalar ExitPoint persistence work is merged (the standing S5
  prerequisite, commit `77bb6d0` on `exitpoint-persistence-contract`, not yet on
  `main`). No lifecycle change is expected — the evaluator interface is the only seam.
- **[AGENT] Durability boundary.** This proves fsync-before-return survives a killed
  process, not power/disk-cache loss. If production must claim power-loss safety,
  add a block-layer fault-injection test; otherwise state the boundary in the spec.
- **[AGENT] Garbage collection.** The probe *identifies* orphan staging tmps as
  collectable (bytes don't hash to any referenced digest) but does not implement a
  sweep. Production needs an explicit, safe GC pass — content-addressed artifacts may
  be shared by replicates, so collection must be by "unreferenced by any committed
  case," never by attempt.
- **[AGENT] Attempt-history schema.** The probe's `attempts` table records one row
  per attempt with a final `outcome`. Production should decide whether attempt
  history is append-only-per-transition or last-state-wins, and how it relates to
  the "controlled mutable operational state (cursors)" the concept keeps separate —
  the probe derives resume position from committed cases and needs no cursor.
- **[AGENT] Fingerprint set.** The probe binds the concept's full compatibility tuple
  and rejects on any mismatch. Confirm at spec time that these are exactly the fields
  that start a new lineage, and that `strategy_config` canonicalization is stable.

### Suggested upstream back-reference (added under S6)

> **Spike result — [AGENT], 2026-07-12:** Confirmed against a fake evaluator. A
> SQLite + content-addressed staging store survived hard `os._exit` crashes injected
> before case commit and mid artifact-staging; resume reproduced the uninterrupted
> run's ordered cases exactly. All five pass criteria held (identical ordered cases;
> no double-commit under `(study_id, candidate_id)`, enforced by a UNIQUE
> constraint; no committed case referencing a missing/half-written artifact; invalid
> proposals persisted as proposal records; incompatible-fingerprint open rejected),
> plus the three-layer identity: the crashed candidate committed on a new
> `attempt_id` with the failed attempt preserved, and deliberate replicates got
> distinct candidate IDs sharing one artifact. The S4-package repeat is deferred on
> the same merged-scalar-work prerequisite as S5. See
> `../../../teax/.project/active/spike-crash-safe-study-lifecycle/findings.md`.
