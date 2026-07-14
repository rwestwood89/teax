# Brief: Item 11 audit — Study Store, Runner, and Strategies

You are a fresh audit session in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`. You did not implement this; audit it.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `audit.md` in `.project/active/study-store-runner/`.
- Attempt execution first; if blocked, write "Requested live probes" (exact command / mutation + expected outcome) for the orchestrator.

## Audit target
The four Item 11 phase commits against `spec.md` (review-revised), `design.md` (rev 2 — Appendix A DDL, Appendix B test oracle), `plan.md` (+ notes), and the [OWNER] Option A decision.

## What to verify, not trust
1. **The five S6 pass criteria as kept tests against the REAL evaluator** (spec success criterion 1): map each criterion to its test in the suite; confirm the crash regimes use real subprocess deaths through the production runner (not mocked kills), and that resume-identical does a genuine ordered-case comparison.
2. **The fence has teeth** (design MF-1): mutation probe — disable the lease_id check in the fenced commit (or simulate a reclaimed lease) and confirm the corresponding test goes RED; revert, GREEN.
3. **Order-sensitive strategy fingerprint** (design MF-2): the reorder-rejection test exists and actually reorders variables; confirm sort_keys is NOT applied to the strategy-config pair-array.
4. **Option A execution**: attempt_transitions rows per state change with transition_seq; COALESCE on first attempt; crashed attempt forensics visible (started row without terminal row).
5. **GC safety**: shared replicate artifact never collected; live-lease tmps untouchable; reclaimed-lease tmps collectible — find the tests.
6. **Sentinel injectivity**: reserved-key collision rejects loudly — test exists?
7. **Suite/gate claims**: 29 study + 25 evaluation green; framework failure set = exactly the 4 known; ruff clean. Run them.
8. **Spec success-criteria walk** with evidence per item; flag any silent scope cut (e.g. spec'd requirement with no test or code).

Verdict: Certify / Certify-with-notes / Fail.
