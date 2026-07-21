# Spec: GAP-CLOSE F1 TEAx Normalization

**Identifier:** GAP-CLOSE-F1-TEAX-NORMALIZATION
**Status:** Complete
**Owner:** Reid W
**Created:** 2026-07-18
**Complexity:** MEDIUM
**Branch:** constraint-exec-epic
**Epic:** GAP-CLOSE Item 1

---

## Problem

Sysml-codegen now lets exceptions from generated constraint arithmetic propagate unchanged, as
required by the owner's F1 ruling. TEAx catches those exceptions at each evaluator boundary and
raises its normalized `EvaluationFailed` outcome, but the evaluator catches too late to know which
generated constraint module failed. Its `module_or_channel` field is therefore empty. A caller can
distinguish broken execution from a constraint verdict, but cannot identify the constraint whose
execution broke.

This missing TEAx leg leaves GAP-CLOSE Item 1 incomplete. Exceptional arithmetic must arrive at the
same normalized, module-specific failure contract through the prepared in-memory and file-backed
evaluation routes without changing generated arithmetic or the existing constraint verdict
semantics.

## Success Criteria

- [x] `PreparedEvaluator` and `FileBackedEvaluator` normalize an equivalent raised exception from
      generated constraint arithmetic as `EvaluationFailed` with identical public
      `EvaluationFailure` records. Each record has
      `phase == EvaluationPhase.MODULE_EXECUTION`; `module_or_channel` equal to the exact failed
      generated constraint pipeline module key, which is `constraint_id.lower()` for these
      generated modules; `cause == f"{type(original).__name__}: {original}"`;
      `retryable is False`; and `partial_artifacts == ()`.
- [x] The original arithmetic exception does not escape either evaluation API as the top-level
      exception. Explicit chaining is not suppressed: `EvaluationFailed` is raised `from` the
      original exception, and `EvaluationFailed.__cause__` retains the original exception class,
      message, and causal traceback.
- [x] A failed candidate returns no `ModelEvidence` or aggregate constraint report through either
      evaluator and persists no file-backed candidate outputs. Regression coverage includes an
      execution in which an earlier constraint completes before a later constraint fails, proving
      that the earlier work does not escape as returned partial evidence or persisted candidate
      output.
- [x] Generated-package regressions cover division by zero, zero raised to a negative power,
      exponent overflow, and exceptional arithmetic beneath a supported nested Boolean connective.
      Every case asserts normalized module-specific failure through both evaluator routes, never a
      verdict. Across the regression set, at least two generated constraint pipeline module keys
      can be the failing key, so a constant or stale `module_or_channel` label fails the tests.
- [x] Existing generated-package cases that complete arithmetic retain their current
      `satisfied`, `violated`, and `indeterminate` outcomes. Already-produced non-finite values
      remain `indeterminate` evidence rather than failures.
- [x] Existing prepared/file-backed parity remains green for successful cases, including the
      current non-finite fixtures. The new exceptional-arithmetic cases demonstrate equivalent
      normalized failure semantics across both backends.

## Known Requirements

- **[NEED]** A raised exception in constraint arithmetic is an execution failure, never a verdict.
  Owner ruling recorded 2026-07-18 in
  `../sysml-codegen/.project/research/20260718_gap-review-verification.md`, "Owner ruling — F1
  policy."
- **[NEED]** Generated predicates add no arithmetic guards. Python's existing value-versus-raise
  boundary remains authoritative: an already-produced non-finite value retains indeterminate
  semantics, while a raised exception becomes an execution failure. Owner ruling recorded
  2026-07-18 in
  `../sysml-codegen/.project/research/20260718_gap-review-verification.md`, "Owner ruling — F1
  policy."
- **[NEED]** One failing constraint module means the candidate produces no constraint report, not a
  partial report. Owner-accepted consequence recorded with the F1 ruling in
  `../sysml-codegen/.project/research/20260718_gap-review-verification.md`, "Owner ruling — F1
  policy."
- **[NEED]** The exceptional-arithmetic correction stays small and clean. Owner ruling recorded
  2026-07-18 in
  `../sysml-codegen/.project/research/20260718_gap-review-verification.md`, "Owner ruling — F1
  policy."
- **[HARD]** TEAx exposes evaluation breakage as `EvaluationFailed` carrying an immutable
  `EvaluationFailure` with `phase`, `cause`, `module_or_channel`, `retryable`, and
  `partial_artifacts`. The module-execution phase is `module_execution`; evaluator failures default
  to terminal with no partial artifacts. Existing interfaces:
  `packages/teax-simkit/simkit/evaluation/failure.py` and
  `packages/teax-simkit/simkit/evaluation/evaluator.py`.
- **[HARD]** Both evaluators currently convert per-run exceptions to `EvaluationFailed` with
  `phase=module_execution`, preserve the exception type and message in `cause`, and use explicit
  Python causal chaining. They currently leave `module_or_channel` unset. Existing behavior:
  `packages/teax-simkit/simkit/evaluation/evaluator.py`.
- **[HARD]** The serial executor has the actual pipeline module key at the point it calls
  `module.run()`. The later evaluator catch receives only the exception. Existing execution seam:
  `packages/teax-simkit/simkit/core/pipeline_executor.py`.
- **[HARD]** Module execution is serial and stops on the first raised exception. The constraint
  report aggregator and ExitPoint cannot run after an earlier generated constraint module fails,
  and file-backed output persistence occurs only after the run reaches the ExitPoint. Existing
  control flow: `packages/teax-simkit/simkit/core/pipeline_executor.py`.
- **[INHERITED]** The normalized F1 outcome names the failed generated constraint module, retains
  the original exception type/message and causal chain, and is identical in contract through
  `PreparedEvaluator` and `FileBackedEvaluator`. The public record uses the exact generated
  constraint pipeline module key in `module_or_channel` (`constraint_id.lower()` for these
  generated modules) and renders `cause` exactly as
  `f"{type(original).__name__}: {original}"`. Source:
  `../sysml-codegen/.project/active/gap-runtime-contract/spec.md`, Success Criteria and Known
  Requirements.
- **[INFERRED]** The identity regressions allow at least two different generated constraint
  pipeline module keys to fail. This adversarial coverage proves that `module_or_channel` follows
  the module that raised instead of accepting a constant or stale label. Source:
  `.project/active/gap-close-f1-normalization/spec-review.md`, L3-1.
- **[INFERRED]** The candidate-level consequence of a failed constraint execution is no returned
  `ModelEvidence` or aggregate constraint report and no persisted file-backed candidate outputs,
  including when an earlier constraint completed before a later one failed. This is stronger test
  coverage derived from the serial executor and persistence boundary; it is not part of the
  owner-settled no-constraint-report statement. Sources:
  `.project/active/gap-close-f1-normalization/spec-review.md`, L1-2, L3-2, and L5-1, and
  `packages/teax-simkit/simkit/core/pipeline_executor.py`.
- **[INHERITED]** Exceptional-arithmetic regressions cover division by zero, zero-to-negative
  power, exponent overflow, and a supported nested-connective form. Source:
  `../sysml-codegen/.project/backlog/epic_gap_close.md`, Item 1, and
  `../sysml-codegen/.project/active/gap-runtime-contract/spec.md`, Success Criteria.
- **[INHERITED]** Existing finite verdicts, non-finite Kleene behavior, and live/snapshot generated
  behavior remain unchanged outside the failure-normalization seam. Source:
  `../sysml-codegen/.project/backlog/epic_gap_close.md`, Item 1, and
  `../sysml-codegen/.project/active/gap-runtime-contract/spec.md`, Success Criteria.
- **[INHERITED]** A false predicate is successful `violated` evidence, while thrown predicate code
  is execution failure. Source carried through
  `../sysml-codegen/.project/active/gap-runtime-contract/spec.md`, Known Requirements, from the
  constraint-execution concept's Design Principle 4.
- **[INHERITED]** Prepared and file-backed evaluators preserve equivalent successful evidence over
  their defined parity class, including non-finite input cases. Source:
  `.project/completed/20260713_model-evaluator/spec.md`, Success Criteria and Known Requirements.

## Non-Goals

- Adding safe-division, safe-power, overflow guards, or exception-to-value conversion to generated
  predicates.
- Changing which expressions sysml-codegen or the executable profile admits.
- Changing `satisfied`, `violated`, or `indeterminate` semantics, including current handling of
  already-produced `inf` and `nan` values.
- Changing the public failure taxonomy, adding a new evaluation phase, or changing evaluator
  retry policy.
- Refactoring the pipeline executor or evaluation layer beyond the module-specific failure seam.
- Implementing sysml-codegen's completed F1 propagation leg or any other GAP-CLOSE item.

## Open Questions / Deferred to design

- Choose how the failed module identity crosses the executor/evaluator seam. Candidate mechanisms
  include an executor exception carrying execution context and callback or context tracking read by
  the evaluator. The transported value is fixed as the exact failed pipeline module key; only its
  transport is deferred.
- Place the shared normalization logic so both evaluators stay contract-identical without freezing
  a broader executor API than this requirement needs.

---

## Related Artifacts

- **Epic:** `../sysml-codegen/.project/backlog/epic_gap_close.md`, Item 1
- **Required Reading:**
  - `../sysml-codegen/.project/research/20260718-123558_constraint-expression-final-gap-review.md`,
    F1
  - `../sysml-codegen/.project/research/20260718_gap-review-verification.md`, F1 and owner ruling
  - `../sysml-codegen/.project/active/gap-runtime-contract/spec.md`
- **TEAx contract context:**
  - `.project/completed/20260713_model-evaluator/spec.md`
  - `.project/completed/20260713_model-evaluator/design.md`
  - `.project/completed/20260713_model-evaluator/audit.md`
  - `docs/evaluation-and-study.md`
- **Design:** `.project/active/gap-close-f1-normalization/design.md` (to be created)

---

**Next Steps:** Proceed to `my-design`; the targeted spec-review findings are resolved.
