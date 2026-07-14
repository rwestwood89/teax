# Brief: Item 12 design — Study Policy, Query, and CLI Surface

You are the design stage for Item 12 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `design.md` in `.project/active/study-policy-cli/`.

## Input
- Spec (committed): `.project/active/study-policy-cli/spec.md`. Its [HARD] definition-reconstruction finding and sentinel-decode requirement are fixed.
- Certified Items 10/11 code: `simkit/evaluation/`, `simkit/study/` — consumed as-is (if a change there seems needed, surface it loudly; small additive extensions to `simkit/study/` are within this item's scope where the spec requires them, e.g. extending StudyDefinition for objectives/response roles).

## Orchestrator decisions (agent-grade — record as such)
1. **CLI create shape = the spec's lean Option A**: declarative config (package ref + variables/domains + budget/retention + policy selected from a small built-in registry), grid-sufficient; the CLI resolves entry_model from the loaded package and synthesizes the proposal validator. Rejected for now: Python-entrypoint reference (thinner but keeps "define" out of the CLI; can be added later without breaking A). This was NOT an owner-reserved gate (those were Items 7/10/11 only) — the spec's conservatism is appreciated but the orchestrator decides it.
2. Tracking-key correlation stays scoped to surfacing the fingerprint boundary (the spec's Law-4 narrowing is accepted); note it for Item 14's docs.

## Design guidance
- Decide and record: config file format + schema, the policy registry protocol (how a named policy maps to objective extraction + disposition), the query API surface (Python-first with CLI wrappers, or CLI-only), how `resume` reconstructs the StudyDefinition from the config + store fingerprint check, and where the sentinel decode lives (one shared decode function next to encode_evidence, imported by query — never duplicated).
- The end-to-end CLI test (define → run → interrupt → resume → query) is the item's acceptance: design its interrupt mechanism (reuse Item 11's crash controller / subprocess kill) concretely.
- A design_review follows only if your design surfaces genuinely contested calls; keep complexity proportional — this is a 1-day surface item over certified machinery. Make it boring.
