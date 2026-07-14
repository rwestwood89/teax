# Brief: Item 10 spec — Model Evaluator and Typed Entry (production API)

You are the spec stage for Item 10 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `spec.md` in `.project/active/model-evaluator/`.

## Provenance of what you're given
- Concept (owner-ratified design), readable in-repo: `.project/reference/constraint-execution-concept.md` — "Contracts and the Evaluator" section + Required Invariants + Study Execution invariants.
- Epic Item 10: `.project/reference/epic_constraint_execution.md`.
- S5 result + carry-forwards (concept Appendix B) and findings: `.project/active/spike-teax-typed-entry-scalar-continuity/findings.md`. Note: S5 carry-forward (1) is already discharged — the continuity regression test is committed on this branch.
- **Item 0 findings (fresh, load-bearing):** `.project/active/constraint-study-integration-spike/findings.md` — eight named evaluator-interface mismatches, all schema/naming/wiring. Each one is a spec input for this item: the spec must state, per mismatch, what the production API does about it.

## RESERVED OWNER GATE — do not decide
The `MappingEntrySource` API shape (instantiated-models-only vs validate-raw-mappings) is a decision the owner (Reid) has reserved for himself. The spec must NOT pick one: capture both candidate shapes with their consequences (including Item 0's finding that typed entry is channel→model→field, not a flat parameter-ID map), state the wrong-type-diagnostic requirement that holds under EITHER shape (S5 carry-forward (3) — expected and got types named), and mark the choice `[RESERVED: owner decision at design]`. Everything not hinging on that choice should be fully specified.

## Objective (from the epic)
Productionize the S5 evaluator: typed in-memory entry source, prepared-pipeline backend, immutable `ModelEvidence`, and one normalized failure outcome.

## Scope (epic Item 10 §1–4)
1. `MappingEntrySource` API (shape reserved — see gate above; no silent coercion under either).
2. Prepared pipeline backend: validate + build topology once, fresh execution context per case; file-backed path retained; case-level parity between them as a kept test.
3. `ModelEvidence`: immutable, runtime-owned generic envelope — responses keyed by stable IDs, selected outputs, provenance, full report as opaque artifact; runtime types never import generated classes.
4. Normalized failure outcome: phase, module/channel when known, cause, retryability, partial-artifact status — violation stays evidence, breakage stays failure.

## Out of scope
Study semantics (Item 11); optimizers/adaptive strategies (S7-gated). Contract consumption hardening happens when Item 9 lands — spec against S4/Item-0's sealed-package shape and note the Item 9 dependency where it bites.

## Success criteria (from the epic)
- S5's invariants as kept teax tests: mapping/file parity, pre-execution rejection of missing/extra/wrong-type, context isolation, no files in no-persist mode.
- Evaluating S4-lineage packages returns evidence with constraint verdicts projected onto generic response keys.
- A module exception, a schema failure, and an infeasible verdict land in three distinguishable places.
- (Carry-forward (1) already discharged this run — note it as done, don't re-plan it.)

## Environment note
teax's own `.venv` is broken for real-simkit runs; the working form is the agentic-mbse venv + sys.path insert (see Item 0 findings' reproduction). Items 10–12 should provision teax's own venv as a first implementation step (epic risk table) — put that in the spec as a requirement.
