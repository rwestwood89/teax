# Brief: Item 11 implement — Study Store, Runner, and Strategies

You are the implement stage for Item 11 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents or schedule check-backs.
- You ARE allowed to commit in this repo — you are the only session writing to this tree. Commit at each completed plan phase; check off plan.md checkboxes with implementation notes. End commit messages with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Do NOT touch `.project/` outside `.project/active/study-store-runner/`. Do NOT modify `simkit/evaluation/` (Item 10 is certified — consumed as-is; if a change there seems required, STOP and report).
- Budget your time: if a phase's suite gate is a long run, prefer targeted test invocations per the plan; the full framework suite only at final gates.

## Input — execute the plan
`.project/active/study-store-runner/plan.md` (Phases 1–4) is authoritative; `design.md` rev 2 holds DDL (Appendix A — transcribe verbatim), the fence/lease semantics, D1–D8, and the Appendix B test oracle.

## Orchestrator decision (agent-grade, recorded)
The plan's flagged zero-assertion point is resolved: use the named-affordance designated candidate returning a real-shaped zero-results ModelEvidence, as planned. The genuinely-generated zero-assertion aggregator is exercised in Item 7's scope, not here. Proceed without a second fixture package.

## Quality bar
- The crash tests are the deliverable's heart: subprocess os._exit at the named seams, resume in a fresh process, byte-compare ordered cases. No sleeps-as-synchronization; deterministic seam injection only.
- Match simkit idiom. No TODOs, no commented-out code.
- Final gates: Appendix B tests green, evaluation suite 25 green, framework suite green except the four known pre-existing failures, ruff clean on new code.
- If a gate fails and the fix is outside plan scope, STOP and report precisely.
