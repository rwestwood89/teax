# Spike: ExitPoint default primitive handlers — fusion-tea anchor reproduction

**Date:** 2026-07-10 12:25 PDT
**Branch:** exitpoint-persistence-contract @ c9e1e85
**Upstream:** `.project/concepts/exitpoint-persistence-contract.md` (Next-Stage Handoff, "first risk to de-risk")

## Summary of Findings

**Confirmed.** The concept's eight-handler change to `create_default_router()`
is sufficient, on its own, for fusion-tea's generated ife_e2e package to run
with no explicit router. Nothing else in the design needs to move.

- With the router workaround deleted and only the 11-line default-router edit
  applied (`output_router_eight_handlers.patch`), **all 13 anchor checks pass**
  (Hawker, realistic-HIF, Osiris wired single-pass, perturbed-gain rerun) at
  rel tol 1e-6.
- The persisted artifacts are **byte-identical** to the workaround run for
  both pipeline passes — all 7 exit files each (5 × `RootModel[float]`,
  2 × bare `float`), and manifests identical modulo the random run id.
  The old workaround's compact `json.dumps` lambda and the new
  `write_json_payload` (indent=2) produce the same bytes for scalars because
  indent only affects containers.
- Before the edit, the workaround-free run reproduces **T-1 exactly**:
  `PipelineValidationError: ExitPoint output type has no registered write
  handler`, raised pre-run at `pipeline_validator.py:320`. T-2 was never
  reached (validation is genuinely fail-fast).
- All eight names behave through the real `write_outputs` path with exact
  expected bytes (`1.25`, `2`, `"value"`, `true`); wrapped-vs-bare float files
  are byte-identical; **falsy scalars (`0.0`, `0`, `""`, `False`) persist**
  (the produced check is `payload is None`), confirming the concept's
  edge-case claim.
- Regression: teax suite **179 passed, 0 new failures**. The 4 failures in
  `test_no_battery_deps.py` fail identically on unmodified source
  (environmental, unrelated).

Consequences for the concept doc: the "first risk" is retired; the follow-up
claim (sysml-codegen can drop `Float` from `CUSTOM_SCHEMA_TYPES`) was **not**
tested here and remains open — see Open Questions.

## Question / Goal

The concept claims that adding eight JSON-native default handlers to
`create_default_router()` (`float`/`int`/`str`/`bool` → `write_json_payload`;
`RootModel[…]` of each → `write_json_model`) is *sufficient* for a
sysml-codegen-generated package to run with **no explicit router** and
reproduce its outputs.

Confirmed if: fusion-tea's `exploration/ife_e2e/run_anchors.py`, with the
T-1/T-2 router workaround deleted, passes all anchor checks and writes
artifact files identical to the workaround run.

The generated exit block exercises both shapes under test
(`generated/pipelines/ife_hif.yaml:99-107`): 5 × `RootModel[float]`,
2 × bare `float` channels.

## Log

Environment: fusion-tea's exec venv
(`fusion-tea/exploration/pipeline_spike/.venv-exec`) imports `simkit`
**editable from this repo's working tree** (`packages/teax-simkit/simkit`),
pydantic 2.13.4 — so working-tree edits apply immediately. teax `packages/`
tree was clean before and after the spike.

**Probe A — baseline, workaround intact, unmodified teax.**
`cd fusion-tea/exploration/ife_e2e && ../pipeline_spike/.venv-exec/bin/python run_anchors.py`
→ all 13 checks OK (`probe_A_baseline_with_workaround.log`). Created run dirs
`ife-tea-results-7db39da5` (run C, lcoe=270.121…) and `-75b68056` (run C',
lcoe=216.555…), recorded in `rundirs_created_A.txt`.

**Probe B — workaround deleted, unmodified teax (expect T-1).**
`run_anchors_no_workaround.py` loads the original harness source, string-replaces
`run_pipeline()`'s router block with a defaults-only `execute_pipeline` call
(asserts the replace hit), and execs it with `__file__` pointing at the original
so relative paths resolve. Result: `PipelineValidationError: ExitPoint output
type has no registered write handler` from `pipeline_validator.py:320`, before
any module ran (`probe_B_no_router_unmodified_teax.log`). Note: the traceback's
quoted source line shows the *original* file's line 121 (traceback rendering
reads the on-disk file); the executing code had no router.

**Probe C — apply the concept's edit.** Eight handler names added to
`create_default_router()` exactly as the concept's Core Model sketch
(`output_router_eight_handlers.patch`, 11 lines). Verified
`has_handler()` true for all 8 new + 3 existing built-in names.

**Probe D — workaround deleted, modified teax.** Same command as Probe B
→ **all 13 anchor checks pass** (`probe_D_no_router_modified_teax.log`).
Run dirs `-b1aab80c` (C) and `-221d8bfb` (C') in `rundirs_created_D.txt`.

**Probe E — artifact diff.** Paired A/D run dirs by lcoe value, then
`diff -r --exclude=manifest.json` → **IDENTICAL** for both pairs (7 artifact
files each). Manifests identical after dropping `run_directory`/`short_id`
(random per run).

**Probe F — all eight names, real write path, falsy values.**
`probe_f_all_eight_names.py` drives `OutputRouter.write_outputs` with 12
bindings → exact bytes for all cases, wrapped-vs-bare byte identity, falsy
scalars produced (`probe_F_all_eight_names.log`).

**Probe G — regression.** Workspace root isn't `uv run`-installable
(pre-existing setuptools discovery error), so:
`uv run --no-project --with pytest --with "pydantic>=2.5" --with numpy --with pandas --with pyarrow --with PyYAML --with python-dotenv pytest`
→ 4 failed, 179 passed. Stashed the edit, reran the failing file → same 4
fail on unmodified source. Pre-existing/environmental, not spike-caused.

**Cleanup.** Source edit reverted; probe patch kept as
`output_router_eight_handlers.patch`. fusion-tea repo untouched
(the perturbed-gain rerun restores its input file byte-for-byte; only new
run dirs under `exploration/ife_e2e/outputs/osiris/` were added).

## Reproduction

```bash
# 0. Environment: fusion-tea exec venv has simkit editable from this repo
E2E=~/1cfe/fusion-tea/exploration/ife_e2e
PY=~/1cfe/fusion-tea/exploration/pipeline_spike/.venv-exec/bin/python
SPIKE=~/1cfe/teax/.project/active/spike-exitpoint-default-primitives

# 1. Baseline (workaround intact): all anchors pass
cd $E2E && $PY run_anchors.py

# 2. T-1 repro (workaround deleted, unmodified teax): PipelineValidationError
cd $E2E && $PY $SPIKE/run_anchors_no_workaround.py

# 3. Apply the probe patch to teax
git -C ~/1cfe/teax apply $SPIKE/output_router_eight_handlers.patch

# 4. Workaround-free run now passes all anchors
cd $E2E && $PY $SPIKE/run_anchors_no_workaround.py

# 5. Diff newest two run dirs against baseline's two (exclude manifest.json)
#    → identical; manifests differ only in run_directory/short_id

# 6. All-eight-names probe (exact bytes, falsy scalars)
$PY $SPIKE/probe_f_all_eight_names.py /tmp/probe_f_out

# 7. Regression suite
cd ~/1cfe/teax && uv run --no-project --with pytest --with "pydantic>=2.5" \
  --with numpy --with pandas --with pyarrow --with PyYAML --with python-dotenv pytest

# 8. Revert
git -C ~/1cfe/teax checkout -- packages/teax-simkit/simkit/io/output_router.py
```

## Open Questions / Follow-ups

- **Not tested: dropping `Float` from generated `CUSTOM_SCHEMA_TYPES`.** The
  spike ran with fusion-tea's current generated package, which still passes
  its primitive wrappers in `CUSTOM_SCHEMA_TYPES`. That path is transitionally
  safe (re-registers `RootModel[float]` with the same handler), but the
  follow-up sysml-codegen ticket's removability claim is unverified — and
  `CUSTOM_SCHEMA_TYPES` also feeds entry loaders and field-reference
  resolution (`pipeline_validator.py:117-136`), so that ticket must scope to
  exit-only.
- The 4 pre-existing `test_no_battery_deps.py` failures deserve a look in
  their own right (they fail on clean source in a fresh env).
- `int`/`str`/`bool` names are verified at the router level (Probe F) but no
  generated pipeline exercises them end-to-end yet; the concept's heater
  example would, once built as a fixture.
