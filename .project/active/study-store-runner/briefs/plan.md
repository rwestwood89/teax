# Brief: Item 11 plan — Study Store, Runner, and Strategies

You are the plan stage for Item 11 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `plan.md` in `.project/active/study-store-runner/`.

## Input
- Design rev 2 (committed, review-revised): `.project/active/study-store-runner/design.md` — DDL (Appendix A, fenced-commit SQL), the S6-criterion→test map (Appendix B), lease/fencing, D1–D8 are authoritative.
- The S6 probe `study_lifecycle.py` is the reference implementation being productionized; Item 10's `simkit/evaluation/` and the committed sealed-package fixture are consumed as-is.

## Planning guidance (orchestrator, agent-grade)
- Implement runs on sonnet: mechanical phases, exact files under `packages/teax-simkit/simkit/study/`, DDL from Appendix A verbatim, per-phase gates runnable in teax's own venv (provisioned in Item 10 — verify with a smoke check first).
- Sequence to de-risk: store + DDL + staging + fencing first (with crash tests against a fake evaluator for speed), then strategies + bridge, then runner against the REAL evaluator, then the full S6-criterion kept-test suite (Appendix B) + determinism pins + GC tests.
- Crash tests are subprocess-based (os._exit at named seams per S6); keep them CI-runnable and fast — plan the seam-injection mechanism concretely.
- Final gates: all Appendix B tests green, evaluation suite still green (25), framework suite green except the four known pre-existing failures, ruff clean.
- Keep phases resumable from checkboxes.
