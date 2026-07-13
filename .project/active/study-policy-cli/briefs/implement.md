# Brief: Item 12 implement — Study Policy, Query, and CLI Surface

You are the implement stage for Item 12 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents or schedule check-backs.
- You ARE allowed to commit in this repo — you are the only session writing to this tree. Commit at each completed plan phase; check off plan.md checkboxes with implementation notes. End commit messages with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Do NOT touch `.project/` outside `.project/active/study-policy-cli/`. Do NOT modify `simkit/evaluation/` (certified). `simkit/study/` may gain the additive StudyDefinition fields the plan names — nothing else there changes; if more seems needed, STOP and report.

## Input — execute the plan
`.project/active/study-policy-cli/plan.md` (Phases 0–5) is authoritative; `design.md` D1–D9 hold the component specs. Heed the plan's two sharp flags: `field(default_factory=dict)` on the frozen dataclass, and the acceptance comparison excluding attempt_id/commit_order (identity columns only).

## Quality bar
- The Phase 2 acceptance round-trip (create → run → crash-at → resume → query, real evaluator) is the item's heart — no sleeps-as-synchronization, deterministic crash seam.
- Match simkit idiom. No TODOs, no commented-out code.
- Final gates: new tests green, study suite (29) green at every phase, evaluation suite (25) green, framework suite green except the 4 known, ruff clean.
- If a gate fails and the fix is outside plan scope, STOP and report precisely.
