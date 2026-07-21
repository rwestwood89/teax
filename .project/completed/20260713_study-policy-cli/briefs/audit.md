# Brief: Item 12 audit — Study Policy, Query, and CLI Surface

You are a fresh audit session in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`. You did not implement this; audit it.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `audit.md` in `.project/active/study-policy-cli/`.
- Attempt execution first; if blocked, write "Requested live probes" for the orchestrator.

## Audit target
The Item 12 phase commits against `spec.md`, `design.md` (D1–D9), `plan.md` (+ notes). The implement session's final report was unusually terse — audit the actual state with extra skepticism about unrecorded deviations.

## What to verify, not trust
1. **The epic's acceptance criterion**: a grid study runs end-to-end from CLI — define → run → interrupt → resume → query, resumed result identical to uninterrupted. Find and RUN that test; confirm the interrupt is a real crash (subprocess kill at a seam), the comparison covers identity columns in commit order, and the resumed run genuinely skips committed cases.
2. **Policy**: four dispositions implemented; policy "reject" = completed case with evidence retained (boundary-plot point) vs assessment_failed (policy broke) — distinct and queryable; assessment never mutates stored evidence (find the guarantee); assessment_failed reachable through REAL objective-extraction failure.
3. **Query**: three case states × three verdict classes distinguishable; catalog join by constraint_id works against the sealed fixture's catalog; the non-finite sentinel DECODE is exercised (a NaN evidence value round-trips through store → query as a real float('nan')).
4. **Resume/lineage**: resume refuses a changed fingerprint with the new-lineage message (test exists and runs); config semantic digest excludes filesystem paths (moved package dir doesn't break resume — test?).
5. **No certified-code drift**: `simkit/evaluation/` untouched; `simkit/study/` changes limited to the plan's named additive fields — diff and confirm.
6. **Suites**: study suite (29 + new), evaluation (25), framework (green except 4 known), ruff. Run them.
7. **Spec success-criteria walk** with evidence per item; flag silent scope cuts.

Verdict: Certify / Certify-with-notes / Fail.
