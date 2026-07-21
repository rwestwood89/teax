# Design Review: Study Store, Runner, and Strategies (Lists/Grids) — Item 11

**Design:** `.project/active/study-store-runner/design.md`
**Spec:** `.project/active/study-store-runner/spec.md`
**Review File:** `.project/active/study-store-runner/design-review.md`
**Date:** 2026-07-12
**Reviewer posture:** skeptical; verified against S6 `study_lifecycle.py`, Item 0 findings, and the certified `simkit/evaluation/` code — not the design's word.

---

## Fundamental Assessment

**Sound.** The approach is right: productionize the proven S6 shape as a `simkit/study/`
subpackage over the certified Item 10 evaluator, consuming the evaluator/entry/evidence/failure
types as-is. This is a productionization plus three named Item-0 adaptations, not a redesign, and
the design keeps it that way. The `[OWNER]`-grade Option A attempt-history choice is executed
consistently (per-transition rows, `transition_seq` ordering, `MAX(attempt_number)` derivation
called out). No over-engineering: every table and module earns its place, and the design refuses
a cursor (D6) and a parallel mechanism where the evaluator/executor already own the behavior.

Not a Rework. But two of the six probe areas surface real correctness gaps that must be closed
before implementation: the runner lease admits two concurrent writers in one failure cell, and
the grid compatibility canonicalization can silently accept a definition that shifts positional
identity. Both attack invariants the spec grades `[HARD]`/`[INFERRED]` (INV-F single writer, INV-G
determinism, positional minting). Verdict: **Approved-with-must-fixes.**

---

## Probe Findings (the six hardest points)

### 1. Crash-safety fidelity under productionization — **holds.**
Walked the S6 protocol (`study_lifecycle.py:423-452`) against the design's staging path.

- Ordering is preserved exactly: tmp write → `fsync` file → atomic `os.replace` → `fsync` dir →
  single case-row transaction (INV-C, design §Architecture, matches S6 `_stage_artifact` +
  `commit_case`). No step reordered or weakened.
- Final-path-complete (INV-B) is intact: dedup checks `exists()` at `artifacts/{digest}.json`
  first and the final path only ever appears via atomic rename of a fully-fsync'd tmp.
- Content-addressed dedup (two replicates, one artifact) survives the `staging/{lease_id}/{attempt_id}.tmp`
  relayout: the tmp path is per-attempt-unique, but the final path is still `{digest}.json`, so the
  second replicate hits the `exists()` short-circuit and no second artifact is written. This matches
  S6's `test`: replicates A/B (proposals 7/8) share one artifact.
- The relayout genuinely closes L2-1 (a crashed orphan tmp is attributable to a dead lease dir).

One completeness gap, minor: S6 wrote tmps directly into `staging_dir`; the per-lease subdir
`staging/{lease_id}/` must be created (`mkdir`) at lease-acquire or first stage. Not stated. See NF-4.

### 2. Lease design (D4) — **MUST-FIX (MF-1). One cell admits two writers.**
Failure matrix walk:

| Owner process | Lease TTL | Same host? | Acquire verdict | Safe? |
|---|---|---|---|---|
| dead | within TTL | yes | `os.kill(pid,0)`→ESRCH → **dead** → reclaim | ✓ prompt resume |
| dead | within TTL | no | heartbeat fresh → **live** → `StudyLocked` | ✓ (slow; waits TTL) |
| **live but stalled** | **past TTL** | either | heartbeat stale → **dead** → reclaim | **✗ two writers** |
| dead, pid reused | past TTL | yes | reused pid alive → false-live, then TTL → dead → reclaim | ✓ safe-slow |
| dead, pid reused | within TTL | yes | reused pid alive → **false-live** → `StudyLocked` | ✓ safe-slow |

- **"Safe false-live" is safe** — confirmed. A reused/hung pid keeps the lease "live" only until its
  heartbeat ages past TTL (the dead owner stops heartbeating), then the TTL branch reclaims. GC is
  **not** blocked forever. That claim holds.
- **But TTL-based deadness is not sound.** The design's safety rests on an unstated bet: *a lease past
  its TTL will never be written to by its old owner again.* That is true for pid-death (the fast path)
  but **false for a live-but-stalled owner** — a real model evaluation, a GC pause, or a slow disk that
  exceeds TTL. The reclaiming runner takes a new `lease_id`; the stalled runner wakes and proceeds to
  stage → commit with no check that it still holds the lease. Two runners now write concurrently.
  `UNIQUE(study_id, candidate_id)` catches a *same-candidate* double-commit as an `IntegrityError`
  (which the runner must then handle — S6 never had to), but both runners resume at the same
  uncommitted position and will also interleave attempt-transition rows, artifact stages, and
  GC-vs-live-tmp deletion. INV-F ("at most one live runner … GC never runs against a live lease") is
  violated in this cell.
- **Severity is not pathological.** With a 30 s TTL and heartbeat emitted inline between candidates,
  *any* single evaluation longer than 30 s routinely trips false-death. The design never specifies
  whether heartbeat is a background thread or inline — and that choice decides whether normal slow
  evaluations trigger this.
- **The GC rule compounds it:** GC collects `staging/{dead_lease}/*.tmp`. If the "dead" lease belongs to
  a stalled-but-live runner, GC deletes a tmp that runner is mid-writing or about to rename → its rename
  fails.

**Required:** fence every store write on lease ownership (a fencing token). Condition the case-commit
transaction (and transition/proposal inserts) on `lease_id` still being the current one — e.g. the
commit `INSERT` runs in the same transaction as a `SELECT lease_id … WHERE lease_id = :mine` guard, and
aborts loudly if reclaimed. Alternatively, restrict reclaim of a *live* pid to the pid-death signal only
and treat pure-TTL expiry as reclaimable **only** after fencing is in place. Also: specify the heartbeat
mechanism, and set TTL ≫ any expected evaluation time is *not* a fix (evaluation time is unbounded) —
fencing is.

### 3. Option A consequences — **holds, with one DDL precision fix (MF-4).**
- Resume-skip is unaffected: it keys on `cases` via `has_case(candidate_id)` (unchanged from S6), not on
  attempt outcomes. Option A adds rows to `attempt_transitions` only.
- "Crashed attempt stays at `started`" is correctly reframed: a crash leaves a `started` transition with
  no terminal row (design §Implementation Notes) — the forensic signature. Nothing in the resume path
  reads this; it is forensics only. Good.
- `UNIQUE(study_id, candidate_id)` still lives on `cases`, not on transitions. Correct.
- **Bug in the stated derivation:** `next_attempt_number = MAX(attempt_number) + 1` returns **NULL on the
  first attempt** (no rows → `MAX` is NULL → `NULL+1` is NULL). Must be
  `COALESCE(MAX(attempt_number), 0) + 1`. Flagged as an impl gotcha in the design but written wrong in
  both the Core-Concept consequence line (D2) and Implementation Notes.

### 4. Fault-injection honesty — **sufficient for the runner, but B4's evaluator side must be cited, not assumed (NF-2).**
- The named `execution_failed` fault is a wrapper `Evaluator` that, for one designated candidate, raises
  the authentic `EvaluationFailed(EvaluationFailure(phase=MODULE_EXECUTION, retryable=False))` — byte-for-byte
  what `evaluator.py:114-120` constructs when a real module raises. For **the runner** (routing an
  `EvaluationFailed` by phase), the real evaluator is still the SUT everywhere except that one raise, and
  the exception is indistinguishable from the real one. That is honest for testing the routing switch.
- **What it does not prove is B4 itself** — that a *real module raise* actually surfaces as
  `MODULE_EXECUTION`. The design asserts B4 but the named fault assumes it. This link is, however, already
  certified in Item 10: `evaluator.py:112-120` wraps *any* exception from `_executor.run` into
  `MODULE_EXECUTION`. So the honest resolution is cheap: **cite Item 10's coverage** as the ground for not
  needing the heavier raising-fixture package, rather than leaving B4 unbacked. The design's own flagged
  alternative (a second fixture whose module raises) would close it end-to-end but is not required if the
  citation is made.
- `assessment_failed` is genuinely honest: real evaluator → real evidence → injected policy rejects a
  designated candidate → evidence preserved. Matches the criterion's intent exactly. No concern.
- `retry` fault (transient store-I/O on the first persistence attempt) is downstream of a completed real
  `evaluate()`. Honest.

Note: Item 0 confirmed the real package returns `indeterminate` (Kleene) on a non-finite operand and
**never raises** (findings §mismatch 2), so a real *input* cannot produce `execution_failed` — the named
fault is the only way, and that is legitimate given the citation above.

### 5. Non-finite sentinel encoding (D3) — **MUST-FIX (MF-3): injectivity is now load-bearing and unstated.**
- Round-trip on disk (INV-H, bytes re-hash to digest) is fine: one canonicalizer produces the bytes and
  the digest is `sha256` of exactly those bytes.
- **The new hazard is semantic decode.** In Item 10 the `{"__nonfinite__": tag}` tag was *digest-input only,
  never decoded* (`evaluator.py:34-39` docstring), so a collision was harmless. Item 11 makes it the
  **actual on-disk encoding that Item 12's query layer reads back**. Decoding requires the encoding be
  **injective**: a legitimate value `{"__nonfinite__": "nan"}` appearing inside `report` (which is
  `Any`/opaque, `evidence.py:58`) would be silently reconstructed as a real NaN. The design never states
  the key is reserved/collision-free or that the report schema cannot emit it.
- Real-world likelihood is low (the generated `ConstraintReport` is typed, not free-form), so this is
  "must **state** the assumption," not "will corrupt today." Required: declare the sentinel key reserved and
  the encoding injective, and either argue the report schema cannot produce the key or escape it — so Item
  12 can decode safely.

### 6. Determinism pins — **MUST-FIX (MF-2) hiding behind an otherwise-clean proposal path.**
- The proposal path itself is clean: `GridStrategy` uses `itertools.product` over declared variable order,
  never a set/hash-ordered structure (design §strategy.py); list order is preserved. The independent
  `test_grid_determinism_pin` is the right extra guard.
- **But the compatibility canonicalization can accept a definition that shifts positional identity.**
  `strategy_config` is "the ordered variable→domain map for a grid," digested via canonical JSON. S6's
  `canonical_bytes` uses `sort_keys=True` (`study_lifecycle.py:45`) — which **sorts the variable keys
  alphabetically**, discarding declared order. Proposal order, however, comes from `itertools.product` over
  *declared* order. So two grid definitions that declare the same variables in a **different order** produce
  the **same** `strategy_config` fingerprint (and likely the same `study_definition_fingerprint`, if it is
  canonicalized the same way) yet enumerate a **different** proposal sequence. Reopening a store built with
  order `[budget, ratio]` using a definition ordered `[ratio, budget]` passes the compatibility check, then
  re-proposes in a different order — so positional `candidate_id`s now map to different candidates. Resume
  silently corrupts. This directly undercuts the `[HARD]` "grid proposal order is row-major over declared
  variable order" requirement and the positional-minting contract it rests on.
- Required: at least one binding fingerprint (the `strategy_config`, or the `study_definition_fingerprint`)
  must encode declared variable order using an **order-preserving** canonical form — an array of
  `[name, domain]` pairs, not a `sort_keys` object. State it as the grid's canonicalization contract.

---

## Dimensional Review

### 1. Spec Compliance — **Concerns**
Every spec requirement has a design element, and the S6 pass criteria + crash regimes + outcome matrix map
to named kept tests (Appendix B). The provenance carry is faithful: the `[OWNER]` Option A gate is executed,
and `[HARD]` items (WAL+FULL contract, final-path-complete, positional minting, injected validation,
non-finite ≠ invalid, bridge-defect loud routing, evaluator carries no `attempt_number`) all have design
homes. Concern is not omission but two `[HARD]`/`[INFERRED]` invariants that the design's mechanism does not
actually enforce: INV-G/positional determinism (MF-2, grid canonicalization) and INV-F single-writer (MF-1,
lease fencing). The GC-collects-exactly-orphans criterion inherits MF-1 (GC vs live-but-reclaimed tmp).

### 2. Pattern Consistency — **Pass**
Faithfully mirrors S6 and consumes Item 10 as-is. `simkit/study/` mirrors `simkit/evaluation/` module-per-concern.
No new pattern invented where an existing one fits. `INSERT OR IGNORE` proposals, `AUTOINCREMENT`
commit_order, WAL+FULL — all carried from the proven probe.

### 3. Abstraction Quality — **Pass**
Module boundaries are justified. `bridge.py`/`identity.py`/`evidence_io.py`/`compatibility.py` each isolate a
real concern; none is speculative. D1's rejection of extending `simkit/evaluation/` (INV1 isolation) and of a
single `study.py` (size, Item 12 extension) is sound.

### 4. Duplication Avoidance — **Pass**
No parallel mechanism built. Evaluator/executor/entry/evidence reached only through their public surface.

### 5. Data Structure Clarity — **Concerns**
The DDL is explicit and typed; nullable `evidence_digest` for `execution_failed` (D5) is the right call and
makes the GC reference set = non-null digests clean (L3-5). Concern is the non-finite on-disk encoding
(MF-3): the decode contract for Item 12 is under-specified (injectivity unstated).

### 6. Route Safety (failure-routing switch) — **Concerns**
The switch (`ENTRY_VALIDATION → StudyBridgeDefect (loud)`, `else → execution_failed`) is safe for the
*reachable* failure set and correctly makes a bridge defect loud rather than a silent case. But the `else`
is a catch-all over the phase enum, and the enum has **four** phases (`failure.py:13-24`:
`ENTRY_VALIDATION, PREPARATION, MODULE_EXECUTION, OUTPUT_WRITE`), not the "two" B4 names. For the
`PreparedEvaluator` (`persist_outputs=False`) the per-case surface is in fact **`MODULE_EXECUTION` only** —
`OUTPUT_WRITE` is unreachable (no persist) and `PREPARATION` fails at prepare/startup, before any candidate.
So the catch-all never mis-fires today. But the design should reconcile B4's "exactly two phases" wording
with the actual enum and state explicitly that `PREPARATION` surfaces at runner startup (fail-loud), not as
a case — otherwise a future persisting backend routing an `OUTPUT_WRITE` into `execution_failed` is an
unexamined default. See NF-1.

### 7. Bets & Decisions Integrity — **Concerns**
Bets are mostly genuine reality-claims with stated failure modes. The weak one is **B3** ("a dead lease is
promptly and safely distinguishable from a live one"): its hidden sub-bet is *a TTL-expired lease's owner
will never write again*, which is false for a live-but-stalled process (MF-1). B3 as written treats TTL
expiry and pid-death as equivalent evidence of deadness; they are not — only pid-death guarantees no future
write. Surface that and B3 becomes honest (and points straight at the fencing fix). **B4** overstates the
phase surface (two vs four; see NF-1). Decisions are well-formed: each names the rejected alternative with a
reason (D1–D7), and Option A (D2) correctly records Option B as a decision-record, not a prohibition.

### 8. Reader Comprehension — **Pass**
The Core Concept states the one idea (content-addressed + positional identity → resume-by-replay) plainly
before mechanism. Invariants are labeled and referenced. A tired engineer can get the model in one pass. No
coined-label-hiding-complexity. Good.

---

## Issues by Severity

### Critical (must address before implementation)
- **MF-1 — Lease admits two writers in the live-but-stalled/TTL-expired cell.** No fencing token on store
  writes; TTL-based deadness ≠ owner-will-never-write. Violates INV-F and the GC-orphans criterion.
  (Dimension 1, 7; Probe 2.)
- **MF-2 — Grid compatibility canonicalization is order-insensitive but proposal order is order-sensitive.**
  A variable reorder passes compatibility yet shifts positional `candidate_id`s → silent resume corruption.
  Violates `[HARD]` grid-order + positional minting. (Dimension 1; Probe 6.)

### Major (should address)
- **MF-3 — Non-finite sentinel injectivity is now load-bearing (Item 12 decodes it) but unstated.** Reserve
  the key, state injectivity, handle/argue-away the `{"__nonfinite__": …}` collision. (Dimension 5; Probe 5.)
- **MF-4 — `MAX(attempt_number)+1` is NULL on the first attempt.** Use `COALESCE(MAX(attempt_number),0)+1`.
  (Probe 3.)

### Minor (consider)
- **NF-1 — B4/routing phase enumeration vs the real four-phase enum.** Reconcile "two phases" with
  `failure.py`; state `PREPARATION` is a startup fail-loud and `OUTPUT_WRITE` is unreachable under
  `persist_outputs=False`. (Dimension 6, 7.)
- **NF-2 — Cite Item 10's `MODULE_EXECUTION` wrapping (`evaluator.py:112-120`) as the ground for the named
  `execution_failed` fault** instead of leaving B4's evaluator side assumed; keeps the raising-fixture
  alternative genuinely optional. (Probe 4.)
- **NF-3 — Cross-host lease reasoning leans on a shared SQLite file.** SQLite + WAL is unreliable on
  network filesystems; since single-writer/no-parallel is the contract, state cross-host as a bounded corner
  (the TTL path) rather than lean on cross-host SQLite correctness. (Probe 2.)
- **NF-4 — Per-lease staging subdir `staging/{lease_id}/` needs an explicit `mkdir`** at acquire/first-stage
  (S6 wrote directly to `staging_dir`). Completeness only. (Probe 1.)

---

## Recommendations

1. **Add a fencing token (MF-1).** Make the case-commit transaction conditional on holding the current
   `lease_id`, and abort loudly if reclaimed. Specify heartbeat as a background thread. Only then is
   TTL-expiry a safe reclaim signal; otherwise restrict reclaim to pid-death. Re-word B3 to separate
   pid-death evidence from TTL evidence.
2. **Make the grid's binding fingerprint order-preserving (MF-2).** Canonicalize the variable→domain map as
   an ordered array of pairs (not a `sort_keys` object) in `strategy_config` (or `study_definition_fingerprint`),
   so a reorder is an incompatibility. This is the exact property positional minting/INV-G rests on.
3. **State the sentinel encoding is injective and reserve the key (MF-3);** fix the `COALESCE` derivation
   (MF-4).
4. **Reconcile the phase enumeration and cite Item 10's wrapping (NF-1, NF-2);** note the SQLite/NFS bound
   (NF-3) and the staging `mkdir` (NF-4).

The de-risk-first plan in the design (stand up store + staging + lease, re-run S6 crash regimes against the
real evaluator before strategies) is the right sequencing — but fold the MF-1 fencing test and an MF-2
reorder-rejection test into that first slice, since both live in exactly that path.

---

## Resolutions

*(To be filled in during Stage 4 as the owner engages each issue. This section is what the design agent reads
to incorporate the review. The reviewer does not edit the design.)*

---

## Verdict

**Overall: Approved-with-must-fixes.**

The foundation is sound and faithful to S6 and Item 10. Four fixes gate implementation: two Critical (lease
write-fencing MF-1; grid order-preserving canonicalization MF-2) that protect invariants the spec grades
`[HARD]`/`[INFERRED]`, one Major encoding-contract statement (MF-3), one DDL correctness fix (MF-4). The four
minors sharpen honesty and completeness. None touches the `[OWNER]` Option A decision — its execution is
correct.

**Next Steps:** Record resolutions above, then re-run `/_my_design` (or return to the design-agent session)
and point it at this review to incorporate. The reviewer does not edit the design.
