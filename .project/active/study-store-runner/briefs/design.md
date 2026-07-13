# Brief: Item 11 design — Study Store, Runner, and Strategies

You are the design stage for Item 11 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `design.md` in `.project/active/study-store-runner/`.

## RESERVED GATE — RESOLVED BY OWNER
**Attempt-history schema = Option A, append-only-per-transition.** `[OWNER]` decision (Reid, 2026-07-12, orchestrated-run gate). Every attempt state change is its own ordered row (started → committed/failed) with a transition-ordering column. Record it in the design with that provenance grade. Rationale the owner endorsed: strongest crash forensics, and the only shape that stays unambiguous when attempts gain more transitions (S7 adaptive strategies).

## Input
- Spec (committed, review-revised): `.project/active/study-store-runner/spec.md` — [HARD]/[INHERITED] requirements fixed, including: WAL+synchronous=FULL as contract, staging protocol, UNIQUE(study_id, candidate_id), positional minting + row-major grid order + cross-process determinism pin, lease-based single-writer/GC contract, bridge-defect outcome, three case states.
- S6 probe (`.project/active/spike-crash-safe-study-lifecycle/study_lifecycle.py`) — the proven store/runner shape to productionize (adapting its INSERT OR REPLACE attempt row to Option A).
- Certified Item 10 evaluator (`packages/teax-simkit/simkit/evaluation/`) — consumed as-is.
- Item 0's `integration_probe.py` — the real-evaluator wiring shape, including the bridge that builds instantiated entry models (Shape A).

## Design guidance (orchestrator, agent-grade)
- Decide and record: module layout (a `simkit/study/` subpackage mirroring `simkit/evaluation/` is the natural shape — decide), SQL schema DDL (tables, indices, the transition-ordering column for Option A), the lease mechanism (operational-state table + heartbeat vs pid+timestamp — pick and state staleness rules), the staging directory layout and tmp naming (carrying lease/attempt identity per the spec), the bridge API (study variable → entry-model field construction; wrong-type diagnostic surface), and how crash tests inject kills against the real evaluator (subprocess + os._exit at named seams, per S6).
- The S6 probe's 58 invariant checks are the behavioral oracle — design the kept-test suite so each S6 pass criterion maps to a named CI-runnable test against the real evaluator (plus the fake evaluator for the fast paths, if useful — say which).
- A skeptical design_review follows; make the Option A schema and the lease/GC design explicit with rejected alternatives.
