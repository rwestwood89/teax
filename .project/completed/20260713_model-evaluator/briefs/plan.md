# Brief: Item 10 plan — Model Evaluator and Typed Entry

You are the plan stage for Item 10 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `plan.md` in `.project/active/model-evaluator/`.

## Input
- Design rev 2 (committed, review-revised): `.project/active/model-evaluator/design.md` — subpackage layout, Shape A [OWNER], four decisions, fixture set (F-budget + F-output), isolation test spec, kept-test suite are authoritative.
- Spec, reviews beside it. Item 0's `real_evaluator.py` is the code being productionized.

## Planning guidance (orchestrator, agent-grade)
- Implement runs on sonnet: mechanical phases, exact files under `packages/teax-simkit/simkit/evaluation/`, signatures from the design, per-phase gates.
- Phase 0 is the epic-mandated venv provisioning: make teax's own env able to run the evaluation tests (the current .venv is broken for real-simkit runs; the plan must give the exact provisioning commands and a smoke check, falling back to documenting the borrowed-env form if provisioning fails for reasons outside this item).
- The S4-lineage package needed for evidence tests: Item 0 regenerated it (see its findings' reproduction). Plan a fixture-provisioning step that reuses that package (committed or regenerated), not a new generation path.
- Kept tests: S5's four invariants, F-budget + F-output parity, isolation (AST+allowlist+package-absent), three-distinguishable-outcomes, non-finite-reaches-verdict.
- Keep phases resumable from checkboxes.
