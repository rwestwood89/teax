# Numeric study evidence

[OWNER] Fully fix blank study columns across affected repositories, implement on new branches from main in git worktrees, validate, push, and open PRs (2026-09-05 request).

[INHERITED: fusion-tea `.project/research/20260905-091948_blank-study-column-root-cause.md`] Pipeline execution already extracts multi-output fields. Evidence projection drops their bare numeric values before persistence.

## Implementation decisions

- [AGENT] Publish bare Python int/float and existing one-level numeric `.root` wrappers as floats under exactly the selected ExitPoint keys. Exclude raw and wrapped bool; Boolean state is not a numeric measurement.
- [AGENT] Preserve nonfinite values through the existing evidence codec and retain structured constraint report handling. Do not recursively flatten arbitrary objects.
- [AGENT] Move evidence schema v2 to v3 because numeric membership changes while the executable fingerprint can remain constant. Existing compatibility binding must refuse v2-to-v3 resume; historical evidence remains readable and needs a fresh run to obtain omitted values.
- [AGENT] Validate exact numeric membership and values through both real evaluators and a study-store close/reopen/query using mixed scalar outputs and exit aliases. Test scalar exclusions, nonfinite encoding, and compatibility explicitly.

## Progress

- [x] Implement projection and version transition.
- [x] Add regressions and migration documentation.
- [x] Run full repository checks: 432 passed. Implementation committed as `ca5d490`.
- [x] Parent-agent review inspected the projection and tests with no blockers (2026-09-05).
- [x] Real stellarator package acceptance: all four heating outputs (100.0, 50.0, 50.0, 0.5) reached stored evidence and a reopened query; the historical exporter emitted `50.0` for restored `p_coupled_probe`. Wrapped LCOE remained 313.5134115016116. Evidence contained 98 numeric outputs under schema v3 with unchanged executable fingerprint `d4be395197a060590238ff74aa0c5e30fa65c94f0c9390055697da61d62be708`. Temporary trace: `/tmp/fixed-heating-acceptance-trace.json`; no historical artifacts were changed.

Validation command: `UV_CACHE_DIR=/tmp/teax-uv-cache UV_PROJECT_ENVIRONMENT=/home/reid/1cfe/teax/.venv PYTHONPATH=/tmp/teax-numeric-evidence/packages/teax-simkit:/tmp/teax-numeric-evidence/packages/battery-tea-demo uv run --no-sync python -m pytest`. Explicit worktree `PYTHONPATH` makes subprocess crash/resume tests use the same v3 runtime as the parent process when reusing the original checkout's environment.

[AGENT] Test implementation finding: YAML ExitPoint parsing binds each public key to the channel with that same name; the destination filename only names a file. Integration tests therefore distinguish producer field, public channel, and destination filename. Projection tests separately assert that result keys survive unchanged. No YAML alias feature is introduced.
