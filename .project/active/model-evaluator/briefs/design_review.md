# Brief: Item 10 design review — Model Evaluator and Typed Entry

You are a fresh review session in the orchestrated CONSTRAINT-EXEC epic run. Repo: teax, branch `constraint-exec-epic`. You did not write this design; review it skeptically.

## Process constraints
- Work synchronously; never pause for background agents.
- Do NOT run `git commit` — the orchestrator commits.
- Artifact: `design-review.md` in `.project/active/model-evaluator/`.

## Review target
`.project/active/model-evaluator/design.md` (spec, spec-review, briefs beside it). The `MappingEntrySource` = Shape A decision is `[OWNER]`-grade — do not relitigate it; review its *execution*.

## Ground truth to verify against
Item 0's `real_evaluator.py` + findings (the probe being productionized); `packages/teax-simkit/` (executor, validator, entry sources, output router — the design claims zero changes to existing runtime files); S5 findings.

## What to probe hardest
1. **"Zero changes to existing runtime files"** — walk each design component against the real code: can the prepared-pipeline backend, the in-memory JSON-router workaround, and Shape A entry genuinely be built without touching the executor/validator/router? Item 0's probe needed workarounds — check each workaround's production home is really in the new subpackage.
2. **The isolation test's teeth.** Import scan + package-absent construction: can a dynamic generated-class dependency still slip through (e.g. via the opaque report object being introspected somewhere, or a type annotation import)? Is the test specified concretely enough to fail on violation?
3. **Provenance exclusion decision** — study/candidate identity excluded from evidence. Check against Item 11's resume join needs (concept: resume joins on lineage + fingerprints + candidate identity): does the runner get everything it needs from (evidence provenance + its own store), or does excluding candidate identity from evidence break auditability of stored artifacts?
4. **Failure taxonomy mapping** — the four phases against teax's actual raise sites; is `output_write` reachable in no-persist mode; does any real failure path land in no phase?
5. **NaN parity fixture** — is the file-backed leg actually capable of round-tripping NaN (JSON encoder behavior) and does the design say what the file-backed side yields so the NaN-aware comparison is well-defined?

Verdict format: must-fix list (each with why), nice-to-haves, overall verdict (Approved / Approved-with-must-fixes / Rework). Verify against code — do not take the design's word.
