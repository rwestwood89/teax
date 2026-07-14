# Brief: Item 10 spec review — Model Evaluator and Typed Entry

You are a fresh review session in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`. You did not write this spec; review it adversarially.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `spec-review.md` in `.project/active/model-evaluator/`.

## Review target
`.project/active/model-evaluator/spec.md` (brief at `briefs/spec.md`).

## Context
- Concept: `.project/reference/constraint-execution-concept.md` ("Contracts and the Evaluator", Required Invariants, Study Execution).
- Epic Item 10: `.project/reference/epic_constraint_execution.md`.
- Ground truth: Item 0 findings (`.project/active/constraint-study-integration-spike/findings.md`) — the eight mismatches; S5 findings (`.project/active/spike-teax-typed-entry-scalar-continuity/`); the real evaluator probe code (`constraint-study-integration-spike/real_evaluator.py`); current teax runtime code (`packages/teax-simkit/`).

## What to probe hardest
1. **The eight-mismatch dispositions.** For each, check the disposition against the Item 0 findings text itself: is the [HARD] requirement actually what the finding demands, and is anything punted to Items 9/11 that this item's own success criteria secretly need? (E.g. can "constraint verdicts projected onto generic response keys" be tested without the headline vocabulary being normalized *in this item*?)
2. **The reserved gate hygiene.** Both API-shape options must be genuinely open: no requirement elsewhere in the spec quietly presupposes one of them (that would make the owner's choice fake). Flag any such leakage.
3. **Runtime-types-never-import-generated-classes**: is it stated testably (an importability/isolation check), not aspirationally?
4. **Failure taxonomy completeness**: phase, module/channel, cause, retryability, partial-artifact status — walk teax's actual executor failure paths (pipeline_executor, validator) and check each real failure lands in exactly one phase.
5. **Parity kept-test**: mapping vs file-backed — is the equivalence class stated precisely (which outputs, which artifacts excluded)?

Verdict format: must-fix list (each with why), nice-to-haves, overall verdict (Approved / Approved-with-must-fixes / Rework). Verify against code and findings — do not take the spec's word.
