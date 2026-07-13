# Spike: TEAx Typed Entry and Scalar Continuity

## Summary of Findings

**[AGENT] Verdict: S5 is confirmed and its TEAx scope is closed.** Across four
independent runs, all 100 typed mapping evaluations matched file-backed outputs
exactly. Missing, extra, and wrong-type mappings failed before either ordinary
module ran. Every case used a distinct retained execution context, later cases
did not alter earlier contexts, and `persist_outputs=False` created no output
directory.

The ordinary scalar path held in both the throwaway probe and a kept regression
test. A producer channel contains `RootModel[float]`; `.root` field extraction
delivers exactly `float` to the consumer; the consumer returns
`RootModel[float]`. The default router contains all eight scalar handler names.
The three scalar-focused test files pass 71/71, and the framework suite passes
165/165 after excluding four known tests that hard-code another checkout path.

Prepare-once was materially faster on this deliberately small graph. The four
runs measured 4.013×–4.360× over rebuilding and revalidating for every mapping
case. Prepared mapping evaluation took 2.06–2.37 ms for 100 cases; prepared
file-backed evaluation, including rewriting and loading the input artifact,
took 28.49–35.76 ms. Keep the semantic prepare/evaluate split and the throughput
claim for this backend shape. Benchmark the S4 sealed package before claiming a
cross-model speedup.

The scalar persistence prerequisite is also complete. Current `main` at
`7560d65` contains the audited unified primitive-persistence work through
`a49ead5` and `54b4249`, superseding the earlier branch-only implementation.
The reconciliation record reports 240 passing tests after its audit correction
and 13/13 workaround-free fusion-tea anchors with byte-identical artifacts.
The triggering concept now carries this verdict and a back-reference to these
findings.

## Question / Goal

**[INHERITED: sysml-codegen constraint-execution concept, S5]** Assumption under
test: TEAx can prepare an existing constraint-free graph once,
then evaluate about 100 typed in-memory entry mappings with a fresh execution
context per case, producing exactly the same outputs as file-backed entry
loading while rejecting invalid mappings before any module runs and writing no
artifacts when `persist_outputs=False`.

The same probe tests ordinary scalar continuity directly: a single-output
producer places `RootModel[float]` on a channel, a consumer receives its
extracted `.root` as `float`, and the consumer returns `RootModel[float]`.

This serves S5 in
`/home/reid/1cfe/sysml-codegen/.project/concepts/constraint-execution-and-design-space-studies-claude.md`.
S5 also requires the in-flight scalar ExitPoint persistence work to be finished,
audited, and merged. This spike checks that repository state instead of
re-implementing the already completed work.

## Log

### 2026-07-12 — Context and existing scalar work

Command:

```bash
.project/scripts/get-metadata.sh
git status --short --branch
```

Observed:

- Metadata reported branch `exitpoint-persistence-contract` at commit `77bb6d0`.
- `.project/active/exitpoint-persistence-contract/audit.md` certifies the scalar
  ExitPoint persistence implementation.
- The implementation and its tests are committed as `77bb6d0`. Only
  `exitpoint-persistence-contract` contains that commit; `main` does not, so the
  S5 prerequisite is audited and committed but not merged.
- The checkout-local `.venv` does not contain project dependencies. Reproduction
  therefore uses the fusion-tea environment with `PYTHONPATH` pinned to this
  TEAx checkout, matching the existing cross-repository setup.

### 2026-07-12 — Runnable prototype added

Added:

- `probe_pipeline.yaml`: one constraint-free EntryPoint → producer → consumer →
  ExitPoint graph.
- `probe_typed_entry_scalar_continuity.py`: a strict mapping source and
  prepared-pipeline wrapper around the real TEAx validator, graph, executor,
  registry, and router.

The only replaced behavior is EntryPoint loading. File-backed and mapping-backed
legs otherwise run through the same TEAx execution code. The probe also rebuilds
and revalidates the graph for each candidate in a control leg so preparation and
evaluation costs are not conflated.

### 2026-07-12 — Probe run 1

Command:

```bash
PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit:/home/reid/1cfe/teax/packages/battery-tea-demo \
  /home/reid/1cfe/fusion-tea/.venv/bin/python \
  .project/active/spike-teax-typed-entry-scalar-continuity/probe_typed_entry_scalar_continuity.py
```

Observed:

- 100/100 mapping outputs exactly matched file-backed outputs.
- Missing, extra, and wrong-type mappings were rejected before module execution.
- 100 distinct retained contexts preserved their own entry and output channels.
- `RootModel[float] → float → RootModel[float]` held for every ordinary module run.
- No `no-persist-outputs/` directory was created.
- Timing: mapping preparation 0.114 ms; 100 prepared mapping evaluations
  2.060 ms; 100 rebuild-plus-evaluation cases 8.983 ms; speedup 4.360×.
- File preparation was 0.061 ms; 100 file-backed evaluations including input
  rewrites were 28.486 ms.

### 2026-07-12 — Existing scalar implementation checks

Command:

```bash
PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit:/home/reid/1cfe/teax/packages/battery-tea-demo \
  /home/reid/1cfe/fusion-tea/.venv/bin/pytest \
  packages/teax-simkit/simkit/tests/io/test_output_router.py \
  packages/teax-simkit/simkit/tests/core/test_pipeline_validator_exit.py \
  packages/teax-simkit/simkit/tests/test_toy_pipeline.py -q
```

Observed: `53 passed`. This covers the eight scalar writer names, natural JSON
bytes, falsy values, exit fail-fast behavior, exit producer/declaration type
checks, the existing producer/consumer toy pipeline, and defaults-only scalar
persistence.

### 2026-07-12 — Probe run 2

Re-ran the same probe command without modifying the probe.

Observed: all semantic results reproduced. Timing remained material: mapping
preparation 0.114 ms; 100 prepared mapping evaluations 2.110 ms; 100
rebuild-plus-evaluation cases 8.747 ms; speedup 4.145×. File-backed evaluation
including input rewrites took 31.869 ms.

### 2026-07-12 — Reconciled scalar work on current `main`

The earlier repository-state conclusion was stale after the primitive
persistence branches were reconciled. The standard metadata helper is absent
in this checkout, so metadata came from Git:

```bash
git status --short
git log --oneline --decorate -12 --all
git show --stat --oneline 7560d65
```

Observed:

- Current `main` is `7560d65`, merge PR #2 from
  `primitive-persistence-unified`.
- The merged history contains the additive unified implementation in
  `a49ead5` and the audit correction in `54b4249`, on top of bare primitive
  support from `5d6496a`.
- `.project/active/exitpoint-persistence-contract/reconciliation-review.md`
  records 240 passing tests after the audit correction and 13/13
  workaround-free fusion-tea anchors with byte-identical artifacts.
- The earlier branch commit `77bb6d0` was superseded by the reconciled
  implementation. Its required scalar persistence behavior is now on `main`.

### 2026-07-12 — Probe run 3 on merged `main`

Re-ran the documented probe command at `7560d65` before changing production
tests.

Observed: every semantic assertion reproduced. Mapping preparation was 0.118
ms; 100 prepared mapping evaluations took 2.141 ms; 100 rebuild-plus-evaluation
cases took 8.766 ms; speedup was 4.094×. File-backed evaluation including input
rewrites took 28.879 ms.

### 2026-07-12 — Kept scalar-continuity regression added

Added
`test_scalar_type_continuity_between_ordinary_modules` to
`packages/teax-simkit/simkit/tests/test_toy_pipeline.py`. The test runs the
ordinary `ToyDoublerModule → ToyAdderModule` graph and records the consumer's
runtime input type. It asserts that the producer channel remains a
`RootModel[float]`, field extraction supplies exactly `float` to the consumer,
and the consumer result remains correct.

Focused command:

```bash
PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit:/home/reid/1cfe/teax/packages/battery-tea-demo \
  /home/reid/1cfe/fusion-tea/.venv/bin/pytest \
  packages/teax-simkit/simkit/tests/test_toy_pipeline.py::TestToyPipelineExecution::test_scalar_type_continuity_between_ordinary_modules -q
```

Observed: `1 passed`.

### 2026-07-12 — Final validation

Commands:

```bash
PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit:/home/reid/1cfe/teax/packages/battery-tea-demo \
  /home/reid/1cfe/fusion-tea/.venv/bin/pytest \
  packages/teax-simkit/simkit/tests/io/test_output_router.py \
  packages/teax-simkit/simkit/tests/core/test_pipeline_validator_exit.py \
  packages/teax-simkit/simkit/tests/test_toy_pipeline.py -q

PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit:/home/reid/1cfe/teax/packages/battery-tea-demo \
  /home/reid/1cfe/fusion-tea/.venv/bin/pytest packages/teax-simkit -q \
  --ignore=packages/teax-simkit/simkit/tests/test_no_battery_deps.py
```

Observed:

- Scalar-focused files: `71 passed`.
- Framework suite excluding the four known checkout-path tests: `165 passed`.
- A full repository run in the borrowed fusion-tea environment reached 4
  known failures from the hard-coded `/home/reid/teax` path and 19 battery
  setup errors because that environment has neither `pyarrow` nor
  `fastparquet`. These failures do not exercise the S5 code or test.
- A `black --check` attempt could not run because `black` is not installed in
  the available environment. The repository does not declare it as a dev
  dependency.

### 2026-07-12 — Loop closure and final reproduction

Added the S5 verdict and this findings path directly under S5 in the triggering
sysml-codegen concept. Re-ran the probe and the 71 scalar-focused tests after
all edits. Both exited zero; the final probe reported 100/100 parity, isolated
contexts, all invalid-input guards, no persisted directory, scalar continuity,
and a 4.013× prepare-once speedup.

## Reproduction

From `/home/reid/1cfe/teax`:

```bash
PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit:/home/reid/1cfe/teax/packages/battery-tea-demo \
  /home/reid/1cfe/fusion-tea/.venv/bin/python \
  .project/active/spike-teax-typed-entry-scalar-continuity/probe_typed_entry_scalar_continuity.py
```

Expected: exit status 0 and a JSON report with `candidate_count: 100`,
`mapping_file_parity_cases: 100`, three invalid mapping classes, 100 fresh
contexts, `state_leak_detected: false`, scalar consumer type `float`, all eight
default scalar handler names, and `no_persist_output_directory_exists: false`.
Timing values vary by machine; the semantic assertions do not.

The script rewrites `candidate.json` inside this spike folder for the
file-backed comparison. It does not create per-case input files or any output
artifact directory.

## Open Questions / Follow-ups

- **[AGENT] Production API shape:** decide whether `MappingEntrySource` accepts
  only already-instantiated Pydantic models, as this strict probe does, or also
  validates raw mappings into the declared entry type. Do not silently coerce a
  value under a mismatched contract parameter ID.
- **[AGENT] Throughput scope:** repeat the timing against S4's sealed generated
  package before publishing a cross-model speed claim. This probe proves the
  prepare-once benefit on one small TEAx graph.
