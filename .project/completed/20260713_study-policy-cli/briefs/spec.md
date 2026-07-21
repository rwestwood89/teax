# Brief: Item 12 spec — Study Policy, Query, and CLI Surface

You are the spec stage for Item 12 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `spec.md` in `.project/active/study-policy-cli/`.

## Provenance
- Concept (owner-ratified): `.project/reference/constraint-execution-concept.md` — "Study Layer" + "How It Works" (Run a Study; Inspect and Resume) + Vocabulary.
- Epic Item 12: `.project/reference/epic_constraint_execution.md`.
- **Items 10 and 11 are CERTIFIED on this branch** — spec against the real code: `simkit/evaluation/` (evidence, failure) and `simkit/study/` (store DDL incl. Option A attempt_transitions, runner, strategies, DispositionPolicy stub, sentinel encoding, compatibility binding, lease). Read them.

## Objective (from the epic)
Give studies their user surface: policy assessment over immutable evidence, result queries joining the catalog, and the study CLI contracts.

## Scope (epic Item 12 §1–3)
1. **Policy**: user-selected interpretation of evidence (reject, penalize, keep-for-boundary, feed-strategy); assessment never mutates stored evidence; `assessment_failed` preserves real evidence. (Item 11 shipped a minimal DispositionPolicy — this item delivers the full protocol.)
2. **Query**: cases by parameter, output, constraint ID, status, assessment; static source detail joined through the catalog; tracking-key correlation shows fingerprint boundaries (names correlate, never equate).
3. **CLI**: create/run/resume/inspect contracts; resume refuses changed fingerprints with a new-lineage message; a rejected point retains outputs and violations for boundary plots.

## Out of scope
Visualization/plotting; optimizer configuration.

## Success criteria (from the epic)
- A grid study runs end-to-end from CLI: define → run → interrupt → resume → query, with the resumed result identical to uninterrupted.
- Policy failure yields `assessment_failed` with evidence intact; query distinguishes the three case states and three verdict classes.
- teax suite green.

## Notes
- The "catalog" the query joins is the ConstraintCatalog embedded in the generated package's contract — for this item, the sealed fixture's catalog is the available shape (Item 9's ModelContract lands later in sysml-codegen; consume what the fixture provides and note the seam).
- The non-finite sentinel decode (Item 11's D3 reserved key) is part of the query layer's read path — spec its decode behavior.
