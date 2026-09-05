# Current Work

**Last Updated**: 2026-09-05

## Active Work

### Numeric study evidence

Bare numeric ExitPoint outputs now reach evidence beside wrapped numbers. Evidence schema v3 binds the expanded numeric membership and excludes Booleans in both forms; a v2 store requires a fresh lineage for v3 execution. Both evaluator backends and a reopened study query assert exact mixed-output values. Full repository validation: 432 passed. Requirements and validation command: `.project/active/numeric-study-evidence/requirements.md`. Migration: `docs/evaluation-and-study.md#numeric-publication-and-evidence-v3`.

### GAP-CLOSE-F1-TEAX-NORMALIZATION: Exceptional arithmetic failure normalization

- Certified against Revision 3 by independent audit. Both evaluators report the exact failed
  generated constraint module while preserving the original arithmetic exception as the direct
  cause, with no partial evidence or candidate output.
- Locked fixture regeneration was byte-identical. Independent validation passed 43 evaluation,
  277 teax-simkit framework, and 346 repository tests. Audit:
  `.project/active/gap-close-f1-normalization/audit.md`.

## Recently Completed

### 2026-07-13: CONSTRAINT-EXEC Items 0, 10–12 (epic closed, archived)
- Integration spike, model evaluator + typed entry API, crash-safe study store/runner, and the
  study policy/query/CLI surface — all certified and archived to
  `.project/completed/20260713_{constraint-study-integration-spike,model-evaluator,study-store-runner,study-policy-cli}/`.
- Post-run in the owner session: **CE-F3 fixed** (`0d606a4` — `entry_models` derived from the
  pipeline spec replaces the hardcoded `ToyPlantParams`, plus a fixture-name source-scan guard)
  and the 4 pre-existing `test_no_battery_deps` hardcoded-path failures fixed (`1b63272`).
  Suite fully green: **262 passed**.
- Canonical epic close-out + independent findings audit: sysml-codegen
  `.project/completed/20260713_epic_constraint_execution*.md`. Open teax follow-on: **CE-F2**
  (multi-channel `CandidateBridge`), registered in sysml-codegen BACKLOG.
