# Brief: Item 0 — End-to-End Integration Spike (S6 lifecycle × S5 evaluator × S4 sealed package)

You are one stage of the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`.

## Process constraints
- Work synchronously. Never pause for background agents, never schedule check-backs — the headless run exits if you wait.
- Do NOT run `git commit` — the orchestrator commits (other sessions share working trees). Leave your files in the working tree.
- Spike protocol: throwaway code, kept findings. No production code in any repo. Deliverable: `findings.md` (summary-on-top, reproduction commands, verdict feeding Items 9–11) in `.project/active/constraint-study-integration-spike/`.

## Intent (from the epic and concept — owner-ratified design)
Every architectural bet was spike-tested in isolation (S1–S6). This spike connects the one untouched seam: **real evaluator × real sealed package × real study lifecycle**, before Items 9–11 freeze production schemas. If you surface an evaluator-interface mismatch, that reshapes Item 10's spec — not the architecture. Precision in naming any mismatch is the whole value of this spike.

## Objective
Run S6's study lifecycle machinery against S4's sealed generated package through an S5-shaped prepared-pipeline evaluator.

## Scope
1. Regenerate S4's sealed package (S4's probe A, in sysml-codegen `~/1cfe/sysml-codegen` on branch `constraint-exec-epic`) and wire an S5-style prepared-pipeline evaluator over it (typed in-memory entry, fresh context per case).
2. Drive S6's runner/store machinery (reuse `~/1cfe/teax/.project/active/spike-crash-safe-study-lifecycle/study_lifecycle.py` as-is) against it: a prepared candidate list covering satisfied, violated, and indeterminate (non-finite input via typed mapping) points, an invalid proposal, and one crash-and-resume cycle.
3. Benchmark prepare-once vs rebuild on the real package (the S5 carry-forward (2) cross-model measurement).

## Out of scope
- Any production code in any repo; any new lifecycle capability (S6's machinery reused as-is); adaptive strategies (S7 territory).

## Success criteria
- All three verdict classes land as `completed` cases with correct evidence; the invalid proposal stays a `ProposalRecord`; resume reproduces the uninterrupted run.
- Any evaluator-interface mismatch between S6's fake evaluator shape and the real prepared pipeline is named precisely — or its absence is stated explicitly.
- Prepare-once vs rebuild measured on the real package; findings recorded with reproduction commands.

## Required reading (in order)
1. `~/1cfe/sysml-codegen/.project/concepts/constraint-execution-and-design-space-studies-claude.md` — Appendix B, S4–S6 results and carry-forwards (load-bearing).
2. `~/1cfe/sysml-codegen/.project/active/spike-vertical-slice-constraint-execution/findings.md` (S4 — Reproduction section; probe A/B/C are committed there).
3. `~/1cfe/teax/.project/active/spike-teax-typed-entry-scalar-continuity/findings.md` (S5 — Reproduction).
4. `~/1cfe/teax/.project/active/spike-crash-safe-study-lifecycle/findings.md` (S6 — Reproduction).

## Environment facts (verified this run or recorded in prior findings — trust but re-verify on first failure)
- teax `main` ≥ `7560d65` is merged; the S6 deferral prerequisite is already satisfied. The S6 findings' citation of unmerged `77bb6d0` is stale.
- teax's own `.venv`/`uv run` is broken for real-simkit runs. Working form (S4's probe_c): host python from the agentic-mbse venv + `sys.path.insert` of `~/1cfe/teax/packages/teax-simkit`. Check S4 findings' reproduction commands for the exact incantation.
- syside license loads for script runs, not bare `python -c` probes — use real script files for any live extraction.
- S4's sealed package regeneration (probe A) needs live extraction in sysml-codegen; run its committed probe scripts from that repo.
