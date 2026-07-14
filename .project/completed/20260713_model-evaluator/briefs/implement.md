# Brief: Item 10 implement — Model Evaluator and Typed Entry

You are the implement stage for Item 10 in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously; never pause for background agents or schedule check-backs.
- You ARE allowed to commit in this repo — you are the only session writing to this tree. Commit at each completed plan phase; check off plan.md checkboxes with implementation notes. End commit messages with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Do NOT touch `.project/` outside `.project/active/model-evaluator/`.

## Input — execute the plan
`.project/active/model-evaluator/plan.md` (Phases 0–4) is authoritative; `design.md` rev 2 holds the component specs, Shape A [OWNER] decision, fixture definitions, and the isolation-test spec.

## Environment
- Phase 0 provisions teax's own venv first; the borrowed fusion-tea env is the sanctioned fallback (record why if used). Item 0's findings hold the working incantations.
- The sealed package fixture comes from Item 0's run (copy + re-verify seal per the plan). If it's missing on disk, the plan's refresh path regenerates it from sysml-codegen — read-only use of that repo.
- The design's hard rules are non-negotiable: runtime evidence/entry/projection modules import nothing generated (the AST-allowlist isolation test must pass); a violated verdict never raises; the report artifact is never mutated.

## Quality bar
- Match teax-simkit idiom (see existing `simkit/` modules for style). No TODOs, no commented-out code.
- Kept tests are the deliverable as much as the code: S5's four invariants, F-budget + F-output (with the genuine isnan assertion), isolation, three-distinguishable-outcomes, non-finite-reaches-verdict.
- Final gates: full teax suite green (including pre-existing tests), new evaluation tests green, ruff clean if configured.
- If a gate fails and the fix is outside plan scope, STOP and report precisely.
