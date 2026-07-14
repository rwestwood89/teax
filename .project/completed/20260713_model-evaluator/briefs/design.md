# Brief: Item 10 design — Model Evaluator and Typed Entry

You are the design stage for Item 10 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `design.md` in `.project/active/model-evaluator/`.

## RESERVED GATE — RESOLVED BY OWNER
**`MappingEntrySource` shape = Shape A, instantiated-models-only.** `[OWNER]` decision (Reid, 2026-07-12, orchestrated-run gate). Record it in the design with that provenance grade. Consequences per the spec's RESERVED section apply: the caller owns building the channel model (Item 11's bridge resolves channel→model→field); the source refuses a wrong channel-model instance naming expected vs got; non-finite floats pass by construction; the runtime never references generated classes, statically or dynamically.

## Input
- Spec (committed, review-revised): `.project/active/model-evaluator/spec.md` — its [HARD] requirements, phase taxonomy (entry_validation / preparation / module_execution / output_write), runtime-owned vocabulary, NaN-aware parity class, and isolation test are fixed. "Deferred to design" items are yours to decide and record.
- Spec review: `spec-review.md`. Item 0 findings + `real_evaluator.py` (the working probe shape to productionize). S5 findings.
- Current runtime: `packages/teax-simkit/` (executor, validator, entry sources, output router).

## Design guidance (orchestrator, agent-grade)
- Productionize from the Item 0 probe's proven shape — name what moves from `real_evaluator.py` into the runtime package and what changes (it ignored `attempt_number`; production drops it from the protocol per the spec).
- Decide and record the four deferred items: ModelEvidence provenance fields (constrained by Item 11's resume join: lineage + executable/study fingerprints + candidate identity), opaque-report storage form, retryability rule (state the rule; deterministic evaluator → almost everything terminal), ExitPoint-write-handler coupling (local workaround vs validator change — flag if it grows beyond Item 10).
- Module placement: decide where evaluator/evidence/entry-source modules live in teax's package layout (mirror existing structure) and the public API surface.
- Design the kept-test suite explicitly: S5's four invariants, the parity fixture set (NaN case mandated), the isolation test (import scan + package-absent construction), and the three-distinguishable-outcomes test.
- A skeptical design_review follows; make the productionization deltas from the probe explicit with rejected alternatives.
