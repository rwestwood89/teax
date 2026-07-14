# Brief: Item 11 spec — Study Store, Runner, and Strategies (Lists/Grids)

You are the spec stage for Item 11 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `spec.md` in `.project/active/study-store-runner/`.

## Provenance of what you're given
- Concept (owner-ratified): `.project/reference/constraint-execution-concept.md` — "Study Layer" section + Study Execution invariants + Vocabulary.
- Epic Item 11: `.project/reference/epic_constraint_execution.md`.
- S6 result + carry-forwards (concept Appendix B) and findings: `.project/active/spike-crash-safe-study-lifecycle/` (the probe's `study_lifecycle.py` is the shape being productionized).
- Item 0 findings: `.project/active/constraint-study-integration-spike/findings.md` — the runner-side mismatches assigned to Item 11 (injected validation seam; proposal-validity vs non-finite axes; the strategy→candidate bridge that builds instantiated entry models under the [OWNER] Shape A decision from Item 10).
- **Item 10 is CERTIFIED and on this branch** — `simkit/evaluation/` is the real evaluator API to spec against (evaluate(typed_inputs) → ModelEvidence; failure outcome; Shape A entry). Read the actual code, not just its design.

## RESERVED OWNER GATE — do not decide
The **attempt-history schema** (append-only-per-transition vs last-state-wins) is a decision the owner (Reid) has reserved. The spec must NOT pick one: capture both with consequences (auditability vs simplicity; what S6's probe did; what crash-resume forensics need), state the requirements that hold under either, and mark it `[RESERVED: owner decision at design]`.

## Scope (epic Item 11 §1–6)
1. `StudyDefinition`: variables/domains by parameter ID, observables by output ID, objectives, response roles, failure policy, strategy, budget, retention; cannot redefine a predicate.
2. Strategies: prepared lists and grids implementing propose/observe; three-layer identity with the positional candidate-minting rule documented (S6 carry-forward (2): resume idempotency presupposes deterministic proposal order; content-based IDs would collapse deliberate replicates); deliberate replicates distinct.
3. `StudyStore`: SQLite, `WAL` + `synchronous=FULL` as CONTRACT (S6 carry-forward (3)); compatibility binding at creation; `UNIQUE(study_id, candidate_id)`; append-only cases/attempts, separated mutable operational state; content-addressed artifact staging (tmp → fsync → atomic rename → dir fsync → single-transaction commit; final-path-complete invariant stated).
4. Runner: validate/canonicalize → evaluate → assess → stage durably → atomic commit → advance feedback; invalid proposals persist as `ProposalRecord`s; retry under new `attempt_id`.
5. Lifecycle hygiene: safe GC (only artifacts unreferenced by any committed case — replicates share artifacts); durability boundary stated (fsync-before-return, not power-loss).
6. Kept crash tests: S6's regimes (crash-before-commit, crash-mid-staging, resume-identical) as CI-runnable tests against the REAL evaluator (Item 10), not only a fake.

## Out of scope
Adaptive strategies + feedback crash semantics (S7 gates them); policy/query/CLI (Item 12).

## Success criteria (from the epic)
- All five S6 pass criteria as kept tests against the real evaluator.
- Incompatible-fingerprint open fails; changed anything mid-study starts a new lineage.
- GC collects exactly the orphaned staging garbage S6 characterized, never a shared replicate artifact.
