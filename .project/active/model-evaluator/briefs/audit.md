# Brief: Item 10 audit — Model Evaluator and Typed Entry

You are a fresh audit session in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`. You did not implement this; audit it.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `audit.md` in `.project/active/model-evaluator/`.
- Attempt execution first; if blocked, write a "Requested live probes" section (exact command / mutation + expected outcome) for the orchestrator.

## Audit target
The five Item 10 phase commits against `spec.md`, `design.md` (rev 2), `plan.md` (+ notes), and the [OWNER] Shape A decision.

## Specific claims to verify, not trust
1. **"Four pre-existing, unrelated hard-coded-checkout-path failures"** — check out the pre-Item-10 commit and confirm those exact four failed there too; any NEW failure hiding among them fails the item.
2. **The isolation test's subprocess fix** — confirm the test genuinely fails when an isolation-clean module gains a generated import (mutation probe: add `import wi014_s4` behind TYPE_CHECKING in evidence.py → AST scan must go RED; revert).
3. **NaN parity (F-output)** — the test must assert `isnan` on a COMPARED output field, not just verdict strings; read the assertion.
4. **Violated-never-raises + report-never-mutated** — trace the code paths; find the kept tests.
5. **Shape A conformance** — the entry source accepts instantiated models only, refuses wrong channel-model instances naming expected/got; no raw-mapping validation crept in (that would decide the reserved gate the other way).
6. **Spec success-criteria walk** with evidence per item: S5's four invariants as kept tests, evidence with verdicts projected onto generic keys, three distinguishable outcomes, phase taxonomy correctness.
7. **Seal verification claim** — the committed fixture's seal check runs in the suite, not just once during implement.

Verdict: Certify / Certify-with-notes / Fail.
