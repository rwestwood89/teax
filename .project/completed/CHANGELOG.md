# Changelog

Historical record of completed work.

---

## [2026-07-13] - [CONSTRAINT-EXEC] Items 0, 10-12 (teax side)

**Type**: Epic (4 items in this repo; canonical epic archived in sysml-codegen)
**Duration**: ~1 day (created 2026-07-12; archived 2026-07-13)

### Summary
The teax items of the CONSTRAINT-EXEC epic: the end-to-end integration spike (Item 0), the
`PreparedEvaluator` / typed-entry production API (Item 10, Shape A instantiated-models-only
[OWNER]), the crash-safe SQLite study store + fixed-order runner + list/grid strategies
(Item 11, Option A append-only-per-transition [OWNER]), and the study policy/query/CLI surface
(Item 12). Verdicts are data (`satisfied | violated | indeterminate`); case states and verdict
classes are independently queryable; resume is fingerprint-bound.

### Deliverables
- `.project/completed/20260713_{constraint-study-integration-spike,model-evaluator,study-store-runner,study-policy-cli}/`.
- Post-run fixes in the owner session: CE-F3 (`0d606a4`, `entry_models` from the pipeline spec
  + fixture-name source-scan guard); `test_no_battery_deps` hardcoded paths (`1b63272`).
  Suite at close: 262 passed, fully green.
- Epic close-out + independent findings audit: sysml-codegen
  `.project/completed/20260713_epic_constraint_execution*.md`. Open follow-on: CE-F2
  (multi-channel `CandidateBridge`).

### Lessons Learned
- The single-channel toy fixture certified Items 10-12 only for what it exercised; the first
  real multi-entry-channel package surfaced CE-F2/F3. Integration fixtures should match the
  real package shape, not the minimal one.
