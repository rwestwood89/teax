# Brief: Item 12 plan — Study Policy, Query, and CLI Surface

You are the plan stage for Item 12 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `plan.md` in `.project/active/study-policy-cli/`.

## Input
Design (committed): `.project/active/study-policy-cli/design.md` — D1–D9 authoritative. Spec beside it.

## Planning guidance (orchestrator, agent-grade)
- Implement runs on sonnet: mechanical phases, exact files, per-phase gates in teax's venv.
- Build the acceptance round-trip FIRST as the design says (create → run → crash-at → resume → query), then policy/objectives, then query/CaseView, then CLI polish.
- Additive fields on StudyDefinition must not break Item 11's committed tests — call out the compatibility check.
- Final gates: new tests green, study suite (29) + evaluation suite (25) still green, framework suite green except the 4 known, ruff clean.
- Keep phases resumable from checkboxes.
