# Spec Review: Study Store, Runner, and Strategies (Lists/Grids) — Item 11

**Spec:** `.project/active/study-store-runner/spec.md`
**Contract:** `claude-pack/commands/_my_spec.md`
**Review File:** `.project/active/study-store-runner/spec-review.md`
**Date:** 2026-07-12

---

## Reality Check

**Sound.** The spec is pointed at the right work item, the Problem section is accurate, and
every code-facing claim I checked is true against the real Item 10 evaluator:

- The evaluator protocol is `evaluate(typed_inputs) -> ModelEvidence` with no `attempt_number`
  (`simkit/evaluation/evaluator.py:31`). ✓
- `EvaluationFailure.retryable` defaults `False` and the docstring states evaluator code never
  sets it otherwise (`failure.py:26-38`), so "evaluator failure → terminal → `execution_failed`"
  is faithful. ✓
- `_json_safe` is documented digest-input-only, never the on-disk encoding
  (`evaluator.py:34-39`), so "Item 11 owns the on-disk non-finite encoding" is correct. ✓
- Shape A entry source refuses missing/extra/wrong-channel models and already names expected
  vs got (`entry_source.py:41-68`). ✓
- Non-finite passes the entry source by construction (`entry_source.py:9`), so the
  proposal-validity-≠-non-finite requirement is grounded. ✓

S6 fidelity is strong: all five pass criteria are carried as success criteria, and all three
S6 carry-forwards (positional minting + rationale; WAL+FULL as contract; final-path-complete
invariant) survive as `[HARD]` requirements. The reserved attempt-history gate is captured
well **in its own section** — both options, consequences, and the requirements that hold under
either.

This is not a Rework. It is a solid spec with one genuine internal contradiction, one real
safety gap, and a handful of omissions that would otherwise leak into design. Details below.

---

## Audit

### Lens 1 — Faithfulness

**L1-1 · Question to the user:** The spec drops S5 carry-forward (3). That carry-forward
(concept Appendix B, S5) says: "whichever `MappingEntrySource` API shape spec chooses … the
wrong-type diagnostic naming expected and got types is required behavior, not probe detail —
it is the study layer's first line of defense." The spec's bridge requirement (spec.md:157-160)
mentions only that "the entry source only refuses a missing/extra/wrong-channel model" — it
never elevates the expected/got diagnostic to a stated requirement, and never says where wrong-
type is caught relative to the evaluator boundary. The diagnostic already exists in consumed
Item 10 code (`entry_source.py:56-66`), so the requirement may be satisfied by consuming Item
10 as-is — **but the spec should say so explicitly and cite S5 CF3**, so design doesn't wrap or
degrade it. **Is the intent that Item 11 relies on Item 10's entry-source diagnostic verbatim,
or that the bridge validates types before handing to the evaluator?** (See also L3-4 —
classification of a bridge-produced wrong-type.)

**L1-2 · Question to the user (tag):** Positional candidate minting is tagged `[HARD]`
(spec.md:93-96), but the spec's own grading note scopes `[HARD]` to "forced by how the real
Item 10 evaluator API, SQLite, or the OS durability primitives actually behave." Positional
minting is forced by none of those — it is forced by the conjunction of two *design*
requirements (deliberate replicates must stay distinct; resume must be idempotent without
content addressing). That makes it an owner-ratified design decision carried from S6 CF2, i.e.
`[INHERITED]`, not `[HARD]`. The distinction matters only because `[HARD]` is settled-eligible
and would over-harden a decision that is really "the best scheme given two constraints."
**Worth a downgrade to `[INHERITED]` (S6 CF2)?** Low stakes — the rationale is captured
correctly either way.

### Lens 2 — Problem & Approach

**L2-1 · Direct claim (sharpest finding):** The GC safety rule is unsafe under a concurrent
runner, and the spec never rules concurrency out. GC is specified as "collects exactly the
orphaned staging garbage S6 characterized (a truncated mid-staging `.tmp` whose bytes hash to
no referenced digest)" (spec.md:60-62, 197-199). But a **live** mid-staging `.tmp` from a
running process is byte-for-byte indistinguishable from a **crashed** orphan: both are half-
written, both hash to no referenced digest (the live one hasn't been fsync'd and renamed yet).
Content-hash collectability alone cannot tell them apart, so GC as specified would delete a
concurrent runner's in-flight artifact. The concept defers parallel workers, but nothing in the
spec establishes single-writer-plus-no-concurrent-GC, and SQLite WAL explicitly allows a reader
process alongside the writer — a manual GC pass (one of the Open-Question triggers) could run
while a runner is active in another process. **Either the spec must state that GC never runs
concurrently with a runner (e.g. GC-on-open or GC-when-idle only, single-writer store), or the
staging protocol needs a liveness marker (pid/lock/mtime grace) so GC can distinguish live tmps
from crashed orphans.** The "collects exactly S6's orphan garbage" success criterion is only
true in the absence of a concurrent writer, and that precondition is unstated.

**L2-2 · Question to the user:** The spec says the three crash regimes run "against the real
evaluator" but never says how crash injection works now that the evaluator is a sealed,
certified module Item 11 may not touch (a Non-Goal, spec.md:247-248). In S6 the crash seams
(`mid_staging` = after fsync of a half-written tmp, before rename; `before_commit` = after the
artifact is durable, before the DB transaction commits) were both **downstream of the
evaluator returning evidence** — they live in the runner/store, not inside `evaluate()`. So the
real evaluator changes *what evidence gets staged*, not *where the seams sit*; the certified
evaluator runs to completion and the crash fires in the runner's staging/commit path. The spec
should state this so design doesn't try to inject a crash inside the sealed evaluator. Two
concrete asks: (a) confirm the crash seams are runner/store-owned test affordances downstream
of the evaluator; (b) point the crash tests at the in-repo fixture
`simkit/tests/evaluation/fixtures/sealed_package/package_live` (Item 10's own test substrate),
so "CI-runnable against the real evaluator" is grounded in teax's pytest rather than Item 0's
external cross-repo venv.

### Lens 3 — Pipeline Risk

**L3-1 · Direct claim (contradiction — must fix):** The StudyStore append-only requirement
contradicts the reserved gate. Spec.md:118-121 states flatly: "Committed cases and attempt
history are **append-only**; controlled mutable operational state (e.g. cursors) is kept
**separate** from them." Read at the row level, "attempt history is append-only" excludes
Reserved **Option B (last-state-wins)** — the probe's shape, which uses `INSERT OR REPLACE` to
overwrite a single attempt's `started` row with its terminal outcome (spec.md:222-231). That is
in-place row mutation, yet the reserved section insists attempt history is *not* operational
state. So under Option B the attempts table is neither strictly row-append-only nor operational
state — a third category line 118 doesn't allow. The reserved section resolves this by scoping
append-only to **across attempts** (a superseded attempt is never erased). **Fix: qualify
spec.md:118 to "append-only across attempts (a superseded attempt is never erased); whether a
single attempt's row is mutated in place is the `[RESERVED]` granularity question," so the
store contract stops silently presupposing Option A.** As written, one `[INHERITED]` requirement
pre-decides the gate the spec claims to leave open.

**L3-2 · Question to the user:** Proposal-order determinism is validated only as a *composite*,
and only for a list. Resume idempotency "presupposes a deterministic proposal order — guaranteed
for prepared lists and grids" (spec.md:93-95). The only check that would catch a determinism
break is Success Criterion 1 (resumed and uninterrupted runs produce identical ordered cases),
and S6's crash tests exercise a **prepared list** of 10 proposals. A **grid** strategy's
proposal order depends on how it iterates the domain product; if that iteration is ever backed
by a set or hash-ordered structure, order could differ across independent processes and the
composite list-only test would never catch it. **Should the spec require an independent
determinism pin for the grid strategy — the same grid definition emits a byte-stable proposal
sequence across two fresh processes — rather than leaning on the list-only resume test?** This
is the property the concept says S7 must establish for adaptive strategies; for grids it is
claimed "guaranteed" but never independently tested.

**L3-3 · Question to the user:** The `proposal_id` minting rule is unspecified, but resume
idempotency depends on it for invalid proposals. On resume the runner re-proposes every
candidate in order (including invalid ones like S6's `p0003`, `x=999`) and re-validates them;
an invalid proposal must re-persist as the *same* append-only `ProposalRecord` without
duplicating. That requires `proposal_id` to be deterministic across processes and the insert to
be idempotent (e.g. `INSERT OR IGNORE` on a positional `proposal_id`). The spec pins
`candidate_id` as positional (spec.md:93-96) but says only that `proposal_id` is "raw strategy
output" (spec.md:100-102) — silent on whether it too is deterministic/positional. **Should the
spec state that `proposal_id` is deterministic across resume and that re-persisting an invalid
proposal on resume is idempotent?** Otherwise a resumed run risks either duplicate ProposalRecords
or a non-reproducible proposals table.

**L3-4 · Question to the user:** A bridge-produced wrong-type would be misclassified. The
failure requirement maps every `EvaluationFailed` to a terminal `execution_failed` case
(spec.md:161-166). But a wrong-type or wrong-channel model handed to the evaluator raises
`EvaluationFailed(phase=ENTRY_VALIDATION)` (`entry_source.py:47-66`) — and that is almost always
a **runner-side bridge bug**, not a legitimate execution failure of a well-formed candidate.
Mapping it to `execution_failed` would silently persist a programming error as a normal study
outcome. **Should an `ENTRY_VALIDATION` failure be treated as a runner defect (fail loud) rather
than an `execution_failed` case, given the bridge — Item 11 code — is what builds the entry
models?** Ties to L1-1.

**L3-5 · Question to the user:** The GC reference set is undefined across the three case states.
"Unreferenced by any committed case" (spec.md:197-199) needs to say which committed cases carry
an artifact digest. A `completed` case does; an `assessment_failed` case preserves real evidence
(spec.md:169-172), so it does too; an `execution_failed` case produced no evidence — does it
reference an artifact at all? If the spec doesn't say `execution_failed` cases have a null
artifact reference, the "referenced" set is ambiguous and GC correctness can't be reasoned
about. This is a spec-level correctness property (not the deferred exact-SQL detail): **state
which case states contribute referenced digests, and that replicate-shared digests are counted
once.**

### Lens 4 — Hygiene

None material. Tags are otherwise honest, sources are cited, the reserved section is exemplary.

### Lens 5 — Reader Comprehension

No material blocker. The spec is dense but well-layered — problem, then S6/Item-0 provenance,
then per-component requirements with sources. A tired engineer can find the contract for any
component on one read. (The one place a reader could be misled is the unqualified append-only
line — L3-1 — which is a correctness fix, not a prose fix.)

---

## Engagement Summary

**Overall take:** The work item is right and the spec is faithful — every code claim I checked
is true, S6 and Item 0 are translated with care, and the reserved attempt-history gate is
handled cleanly in its own section. But one `[INHERITED]` requirement silently pre-decides that
reserved gate, the GC rule is unsafe if a runner and GC ever touch the store at once, and a few
resume/bridge details are presupposed rather than pinned. Fix those and I'd bet design on it.

**Here's what I need you to weigh in on:**

1. **[L3-1]** Must-fix: the "attempt history is append-only" line (spec.md:118) contradicts the
   reserved gate — it excludes Option B. Scope it to "append-only *across attempts*" so the
   store contract stops presupposing Option A.
2. **[L2-1]** The GC content-hash rule can't distinguish a live in-flight staging `.tmp` from a
   crashed orphan. Either forbid concurrent GC-plus-runner (state single-writer / GC-on-idle) or
   add a liveness marker to staging. As written, "collects exactly S6's orphan garbage" is only
   safe with no concurrent writer, and that precondition is unstated.
3. **[L3-2]** Grid proposal-order determinism is claimed "guaranteed" but tested only via a
   list-only composite resume check. Want an independent determinism pin for grids?
4. **[L1-1, L3-4]** S5 carry-forward (3) — the expected/got wrong-type diagnostic as "first line
   of defense" — isn't carried into the spec, and a bridge-produced wrong-type would currently
   be misclassified as `execution_failed`. Decide whether Item 11 relies on Item 10's diagnostic
   verbatim and how an `ENTRY_VALIDATION` failure (a bridge bug) is classified.
5. **[L3-3]** `proposal_id` determinism/idempotency on resume is unspecified — needed so a
   resumed run re-persists an invalid proposal exactly once. Pin it?
6. **[L2-2]** Clarify that crash seams are runner/store-owned (downstream of the certified
   evaluator, which Item 11 may not modify) and point the crash tests at the in-repo
   `sealed_package` fixture so "CI-runnable against the real evaluator" is grounded.

---

## Must-Fix List (brief's format)

1. **[L3-1] Append-only line contradicts the reserved gate.** *Why:* spec.md:118 excludes
   reserved Option B; the spec claims to leave the gate open but one requirement pre-decides it.
   Scope it to "across attempts."
2. **[L2-1] GC race with a concurrent runner.** *Why:* content-hash collectability deletes live
   in-flight staging tmps; the "collects exactly S6's orphan garbage" criterion is unsafe unless
   concurrency is forbidden or staging carries a liveness marker.
3. **[L3-4 / L1-1] Wrong-type classification + dropped S5 CF3.** *Why:* a bridge bug currently
   lands as a normal `execution_failed` case, and the required expected/got diagnostic isn't
   stated as a contract.

## Nice-to-Haves

- **[L3-2]** Independent grid proposal-order determinism pin.
- **[L3-3]** Pin `proposal_id` determinism/idempotency on resume.
- **[L3-5]** Define which case states contribute referenced digests for GC.
- **[L2-2]** Name the crash seams as store-side and cite the in-repo `sealed_package` fixture.
- **[L1-2]** Consider downgrading positional-minting `[HARD]` → `[INHERITED]` (S6 CF2).

---

## Resolutions

_(To be filled in as the owner resolves findings — keyed by ID.)_

---

**Verdict:** Revise (brief vocabulary: **Approved-with-must-fixes**). The work item is sound and
the spec is faithful to code and upstream findings; the three must-fixes above are targeted
edits, not a re-pointing.

**Next Steps:** Record resolutions in this file, then re-run `/_my_spec` (or return to the
spec-agent session) and point it at this review to incorporate. The reviewer does not edit the
spec. The attempt-history granularity gate remains the owner's to resolve at design.
