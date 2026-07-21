# Spec Review: GAP-CLOSE F1 TEAx Normalization

**Spec:** `.project/active/gap-close-f1-normalization/spec.md`
**Contract:** `/home/reid/.agents/skills/my-spec/SKILL.md`
**Review File:** `.project/active/gap-close-f1-normalization/spec-review.md`
**Date:** 2026-07-18

---

## Reality Check

**Concerns, but sound.** The spec is about the right work item. Its problem statement matches the
current evaluator behavior: each evaluator catches the run-level exception and raises
`EvaluationFailed`, while the serial executor alone has the failing pipeline module key at the
`module.run()` call. The owner’s value-versus-raise ruling and no-partial-report consequence are
carried correctly at the core. Design would not be sent toward the wrong problem, so a focused
audit is warranted rather than a Stage 0 rework.

---

## Audit

### Lens 1 — Faithfulness

**L1-1 · Direct claim:** The spec weakens an inherited observable contract while presenting it as
preserved. The source spec fixes `module_or_channel` to the generated constraint pipeline module
key and records that key as `constraint_id.lower()` for the generated module
(`../sysml-codegen/.project/active/gap-runtime-contract/spec.md:35-41`). This spec cites that source
as `[INHERITED]` in Known Requirements, but then reopens the value as “the pipeline module key or
another stable generated-module name” in Open Questions
(`.project/active/gap-close-f1-normalization/spec.md:88-92,128-131`). The attachment mechanism
belongs in design; the public identity value does not, unless the spec explicitly records that it
is departing from the inherited source and grades the replacement honestly.

**L1-2 · Direct claim:** The owner ruling supports “no constraint report, not a partial one”; it
does not say that no `ConstraintEvaluation` object may ever be produced. The latter wording entered
through the upstream agent-written success criterion
(`../sysml-codegen/.project/active/gap-runtime-contract/spec.md:46-48`), while the owner record says
only that the candidate yields no constraint report
(`../sysml-codegen/.project/research/20260718_gap-review-verification.md`, “Owner ruling — F1
policy”). The current spec’s Success Criteria expands this again to “no `ConstraintEvaluation`”
(`.project/active/gap-close-f1-normalization/spec.md:38-39`). Preserve that expansion only as an
inherited or inferred candidate-level outcome; do not let it read as part of the owner-settled
consequence.

### Lens 2 — Problem & Approach

No material finding. The spec keeps the problem at the executor/evaluator seam, leaves the
identity-transport mechanism to design, and excludes arithmetic guards and broad executor
refactoring. That is the right size and abstraction boundary for the TEAx leg.

### Lens 3 — Pipeline Risk

**L3-1 · Rewrite request:** Module identity is required but not yet proven in a way that defeats a
constant or stale label. The arithmetic matrix can be implemented with one generated constraint
module, in which case every test could pass while the normalization always reports that one key.
Require the regression set to distinguish at least two generated constraint module keys, or an
equivalent adversarial observation that proves the reported key follows the module that actually
raised. This adds testability to the observable outcome without choosing how identity crosses the
executor/evaluator seam.

**L3-2 · Direct claim:** “No `ConstraintEvaluation`” is not a reliable pipeline-level invariant.
The executor runs modules serially and stores each completed module’s channel output immediately
(`packages/teax-simkit/simkit/core/pipeline_executor.py:126-140,181-231`). If a later constraint
module fails, an earlier constraint module may already have created and stored its
`ConstraintEvaluation`; what the APIs can guarantee is that no `ModelEvidence` or aggregate report
is returned and that the file-backed ExitPoint writes no candidate outputs, because persistence
starts only after the run reaches the ExitPoint (`pipeline_executor.py:147-162`). Rewrite the
criterion around those observable candidate-level semantics. Include a later-failing constraint
case so the test proves that completed earlier constraint work still does not escape as partial
evidence or persisted output.

**L3-3 · Rewrite request:** The traceback criterion is internally hard to read and can drive
opposite implementations. It says the original exception never escapes “as a raw traceback,” then
requires the same traceback to remain reachable through `EvaluationFailed.__cause__`
(`.project/active/gap-close-f1-normalization/spec.md:33-35`). The upstream contract states the point
plainly: the arithmetic exception is not top-level, explicit chaining preserves it, and the chain
is not suppressed (`../sysml-codegen/.project/active/gap-runtime-contract/spec.md:42-45`). Rewrite
this criterion in those observable terms and drop “raw traceback.”

**L3-4 · Direct claim:** Failure-record parity is underspecified relative to the inherited
contract. The source requires the exact rendered cause
`f"{type(original).__name__}: {original}"` and the exact pipeline module key
(`../sysml-codegen/.project/active/gap-runtime-contract/spec.md:35-41`); the current success
criterion requires only that `cause` “retains” type and message and that identity “names” the
module (`.project/active/gap-close-f1-normalization/spec.md:29-32`). Two implementations could
therefore produce different public records and both claim compliance. Once L1-1 is resolved, state
the exact failure-record equality expected across prepared and file-backed routes.

### Lens 4 — Hygiene

No material finding.

### Lens 5 — Reader Comprehension

**L5-1 · Rewrite request:** The reader cannot tell whether “no `ConstraintEvaluation`” means no
internal object was constructed, no channel value survived, no report was aggregated, or no
evidence was returned. That ambiguity hides the important candidate-level promise. Rewrite it in
terms of what callers and the file-backed artifact boundary observe, as required by L3-2.

---

## Engagement Summary

**Overall take:** The spec has the correct problem, scope, and owner policy. It needs a focused
revision before design because the public module identity has been reopened despite a more precise
inherited contract, and the no-partial-evidence language is both overbroad and insufficiently
observable.

**Here’s what I need you to weigh in on:**

1. **[L1-1, L3-4]** Keep the inherited pipeline module key and exact rendered cause as the
   cross-backend public contract, or explicitly record and re-grade any intended departure before
   design.
2. **[L3-1]** Require an adversarial identity test that distinguishes multiple possible failed
   module keys; a single-module fixture cannot prove causal identity.
3. **[L1-2, L3-2, L5-1]** Narrow “no `ConstraintEvaluation`” to the observable promise: no returned
   evidence/report and no persisted candidate outputs, even when an earlier constraint completed
   before a later one failed.
4. **[L3-3]** Replace “raw traceback” with the unambiguous top-level-versus-chained-exception
   contract already stated upstream.

---

## Resolutions

No resolutions recorded in this independent orchestration-stage review.

---

**Verdict:** Revise
**Next Steps:** Return this review to the spec agent and incorporate the findings into `spec.md`.
The reviewer does not edit the spec. Re-run `my-spec-review` only if the revised observable
contract or provenance grading changes materially; otherwise proceed to design after confirming
the targeted revisions.
