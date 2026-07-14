# CONSTRAINT-EXEC: model evaluator, crash-safe study layer, CLI (Items 0, 10–12)

**Merge order: independent** — no code coupling to the agentic-mbse/sysml-codegen pair
(their PRs document their own ordering). fusion-tea's `main` push comes last.

## What this delivers

The teax study layer of the CONSTRAINT-EXEC epic (canonical epic archived in sysml-codegen
`.project/completed/20260713_epic_constraint_execution*.md`):

- **Item 0 — Integration spike** (findings archived; drove the typed-entry contract).
- **Item 10 — `PreparedEvaluator` + typed entry** (Shape A instantiated-models-only [OWNER]):
  prepare once, evaluate per case; constraint verdicts projected onto generic response keys;
  module exception / entry-validation rejection / infeasible verdict land in three
  distinguishable places; non-finite inputs reach the verdict, never the guard.
- **Item 11 — Study store/runner/strategies** (Option A append-only-per-transition [OWNER]):
  crash-safe SQLite store with fenced writes (`BEGIN IMMEDIATE` lease re-read), atomic case
  commit, fingerprint-bound resume proven identical to uninterrupted runs via real `os._exit`
  subprocess deaths through the production runner.
- **Item 12 — Policy/query/CLI:** four-disposition policy over immutable evidence; query
  distinguishes case states × verdict classes; define → run → interrupt → resume → query from
  the CLI.

## Post-run fixes (owner session, 2026-07-13)

- **CE-F3 fixed** (`0d606a4`): `PreparedEvaluator` no longer hardcodes the toy fixture's
  `ToyPlantParams` — `entry_models` derives channel → typed model from the pipeline spec; a new
  source-scan guard blocks any model-specific fixture symbol in simkit source (RED against the
  pre-fix code).
- **`test_no_battery_deps` un-hardcoded** (`1b63272`): repo root from `__file__`, retiring the
  4 known path failures.

## Evidence

- Items 10–12 audit-certified with orchestrator-executed probes; independent findings audit
  (sysml-codegen `.project/completed/20260713_epic_constraint_execution_audit_independent.md`)
  re-ran the suite. **262 passed — fully green** (first time; the 4 path failures predated the
  epic). Known follow-on: CE-F2 (multi-channel `CandidateBridge`), registered in sysml-codegen
  BACKLOG.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
