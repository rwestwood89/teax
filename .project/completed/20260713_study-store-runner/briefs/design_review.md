# Brief: Item 11 design review — Study Store, Runner, and Strategies

You are a fresh review session in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`. You did not write this design; review it skeptically.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `design-review.md` in `.project/active/study-store-runner/`.

## Review target
`.project/active/study-store-runner/design.md` (spec, spec-review, briefs beside it). The Option A attempt-history decision is `[OWNER]`-grade — review its execution, not the choice.

## Ground truth
S6 probe (`.project/active/spike-crash-safe-study-lifecycle/study_lifecycle.py` — the proven protocol); Item 0 probe (`.project/active/constraint-study-integration-spike/integration_probe.py`); certified Item 10 code (`packages/teax-simkit/simkit/evaluation/`); the committed sealed-package fixture.

## What to probe hardest
1. **Crash-safety fidelity under the productionization.** S6's proof binds to a specific protocol (tmp → fsync → rename → dir fsync → single-transaction commit). Walk the design's staging + DDL and confirm no step was reordered or weakened; specifically, does the `staging/{lease_id}/{attempt_id}.tmp` layout preserve the final-path-complete invariant and content-addressed dedup (two replicates, one artifact) that S6 proved?
2. **The lease design (D4).** TTL + pid-liveness reclaim: walk the failure matrix — dead process/live TTL, live process/expired TTL (a stalled evaluator that resumes!), pid reuse, two hosts sharing a store file. Does any cell allow two writers? Is "safe false-live" actually safe (GC blocked forever by a hung-but-alive pid?)? Does resume-after-crash reclaim promptly per spec?
3. **Option A consequences.** MAX(attempt_number) vs row count is flagged — check the DDL + runner flow for other places a row-per-transition breaks S6 assumptions (e.g. "crashed attempt stays at `started`" queries, UNIQUE constraints, the resume-skip logic keyed on attempt outcomes).
4. **Fault-injection honesty.** The named-fault seams for execution_failed/assessment_failed: confirm the real evaluator remains the system under test (the fault triggers upstream/downstream of it, not replacing it), and weigh the design's own flagged alternative (second raising fixture package) — is the chosen shape sufficient for the spec's "against the real evaluator, not only a fake"?
5. **Non-finite sentinel encoding (D3).** Round-trip: NaN in evidence → sentinel on disk → query layer (Item 12) reading it back. Collision risk with a legitimate `{"__nonfinite__": ...}` user value — is the encoding injective, and is that stated?
6. **Determinism pins.** Cross-process grid-order test and positional minting: check the DDL/strategy design has no dict/set iteration in the proposal path.

Verdict format: must-fix list (each with why), nice-to-haves, overall verdict (Approved / Approved-with-must-fixes / Rework). Verify against code — do not take the design's word.
