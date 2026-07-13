# Brief: Item 11 spec review — Study Store, Runner, and Strategies

You are a fresh review session in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`. You did not write this spec; review it adversarially.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `spec-review.md` in `.project/active/study-store-runner/`.

## Review target
`.project/active/study-store-runner/spec.md` (brief at `briefs/spec.md`).

## Ground truth
Concept "Study Layer" + Study Execution invariants (`.project/reference/constraint-execution-concept.md`); S6 findings + probe (`.project/active/spike-crash-safe-study-lifecycle/`); Item 0 findings + probe (`.project/active/constraint-study-integration-spike/`); the CERTIFIED Item 10 evaluator (`packages/teax-simkit/simkit/evaluation/` — real code).

## What to probe hardest
1. **S6 invariant fidelity.** Walk each of S6's five pass criteria and three carry-forwards against the spec's requirements: is anything weakened in translation (e.g. "final-path artifact is always complete" as contract; positional minting rationale; WAL+FULL as required behavior)? The crash tests must be specified against the REAL evaluator, not just the fake — check the spec says how crash injection works with a real evaluation in flight (S6 injected os._exit at protocol seams; a real evaluator changes where those seams sit).
2. **Reserved-gate hygiene.** Append-only-across-attempts vs single-attempt granularity: is the line drawn correctly, and does no other requirement quietly presuppose one option?
3. **The Shape A bridge.** Item 0 mismatch 1 + the [OWNER] Shape A decision put channel→model→field construction in Item 11's bridge. Is the bridge's wrong-type diagnostic requirement (expected/got named, pre-evaluator) specified? Does the study-variable→field mapping have a defined home?
4. **Identity/resume soundness.** Three-layer identity + `UNIQUE(study_id, candidate_id)` + fingerprint binding: walk the resume flow — can a resumed run re-propose candidate c0007 after a crash mid-staging and land exactly one committed case? Where does the spec say proposal order determinism is validated (not just assumed)?
5. **GC safety.** "Unreferenced by any committed case" — is the reference set well-defined at the SQL level (what query defines referenced), and is the staging-dir scan race-free with a concurrent runner?

Verdict format: must-fix list (each with why), nice-to-haves, overall verdict (Approved / Approved-with-must-fixes / Rework). Verify against code and findings — do not take the spec's word.
