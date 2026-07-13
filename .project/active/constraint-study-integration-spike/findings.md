# Spike: Item 0 — End-to-End Integration (S6 lifecycle × S5 evaluator × S4 sealed package)

## Summary of Findings

**[AGENT] Verdict: the untouched seam holds. S6's study-lifecycle machinery drives S4's
real sealed package through an S5-shaped prepared-pipeline evaluator with zero changes to
the runner/store logic.** All three success criteria pass. The architecture is confirmed;
every mismatch found is a schema/naming/wiring detail that reshapes Item 10's and Item 11's
specs, not the design — exactly as the epic predicted.

**What passed (40/40 checks, stable across three repeats):**

- **Three verdict classes each land as a `completed` case with correct real evidence.**
  Satisfied (budget 5000 → `satisfied`, headline `all-satisfied`), violated (budget 2500 →
  `violated`, headline `violation`, completes as evidence and never raises), and
  indeterminate (budget `NaN` → `indeterminate`, `actual_value` null, margin null). Every
  case carries real ordinary outputs (cost fixed at 3000 from the actual generated calc
  graph), not a stub.
- **The indeterminate class is only reachable through the typed in-memory entry.** A NaN
  budget cannot travel through the file-backed JSON entry; injected as a real
  `float('nan')` into the typed `ToyPlantParams` entry model, it flows to the generated
  Kleene predicate (`cost <= NaN` → unknown → `indeterminate`). This is the concrete
  cross-stack proof of the three-valued semantics S2 verified in isolation.
- **The invalid proposal stays a `ProposalRecord`** (valid=0, no `candidate_id`, no case).
- **Crash-and-resume reproduces the uninterrupted run.** A hard `os._exit(137)` injected
  before committing the indeterminate candidate, then resumed in a fresh process, produced
  byte-identical ordered cases (excluding `attempt_id`), no double-commit, the crashed
  attempt preserved in append-only history (a1 crashed, a2 committed), and every referenced
  artifact present. Deliberate replicate: distinct `candidate_id`, identical inputs, one
  shared content-addressed artifact. Incompatible-fingerprint reopen raises.
- **Evaluator dropped into `FakeEvaluator`'s place unchanged.** The S6 runner order,
  three-layer identity, atomic commit, artifact staging, resume idempotency, and
  compatibility binding all worked as-is against the real evaluator.

**Benchmark (S5 carry-forward (2), cross-model): prepare-once is ~64× faster than rebuild
on the real package** (63.7×–64.8× over two runs; 100/100 verdict parity). This is far
above S5's ~4× on its two-module toy graph, because the real package's per-build cost is
dominated by validation the prepared path pays once: custom-schema-type registration,
field-reference validation, and a five-module topology. Prepared eval ~0.046 ms/case;
rebuild ~2.95 ms/case. **Keep the semantic prepare/evaluate split and the throughput claim;
the cross-model measurement strengthens it — the speedup grows with model validation cost.**

### Evaluator-interface mismatches, named precisely (feed Items 9–11)

None are architectural. All are schema/naming/wiring seams for the production spec.

1. **Typed entry is two-level, not one scalar per parameter ID.** The concept describes
   "typed in-memory input keyed by contract parameter IDs." In the real package the
   EntryPoint emits **one structured channel** (`toy_plant_params: ToyPlantParams`) whose
   *fields* are the parameter IDs; downstream modules field-extract
   (`toy_plant_params.toy_plant__Toy_Plant__plant_budget`). So the evaluator's
   candidate→entry bridge builds a domain params model and keys the mapping by the entry
   *channel name*, then the study variable ("vary `plant_budget`") selects a *field* of that
   model. **Item 10** must define the typed-entry contract at both levels (channel → model;
   model field → parameter ID), not as a flat parameter-ID→scalar map.
   (`real_evaluator.py:evaluate`, and pipeline.yaml entry block.)

2. **Proposal validity and non-finite input are different axes; S6's fake rule conflates
   them.** S6's `validate_and_canonicalize` rejects non-finite / out-of-range `x` as
   *invalid* → `ProposalRecord`. But a non-finite budget is a **well-formed candidate** that
   the model *evaluates* to `indeterminate`. If the production domain validator copies the
   fake rule, the entire indeterminate verdict class becomes unreachable (every such point
   is bounced as an invalid proposal). **Item 11** must define proposal validation as
   "malformed / missing / wrong-type" only — never "non-finite" — and let the model produce
   `indeterminate`. (`integration_probe.py:real_validate_and_canonicalize`.)

3. **`StudyRunner.run` hard-references a module-global `validate_and_canonicalize`.**
   Reusing the runner "as-is" against a different study required monkeypatching the module
   global; there is no injection point. **Item 11**'s runner must take proposal validation
   as an injected dependency of the `StudyDefinition`, not a module-level function.
   (`integration_probe.py:run_study` installs the patch.)

4. **The evaluator protocol should not carry `attempt_number`.** S6's
   `FakeEvaluator.evaluate(inputs, attempt_number)` uses it only to fake a transient
   failure. The real prepared pipeline is deterministic and stateless per case — the
   argument is unused. Retry/attempt bookkeeping belongs to the runner; **Item 10**'s
   evaluator protocol is `evaluate(typed_inputs) -> Evidence`. (`real_evaluator.py:evaluate`
   accepts and ignores it.)

5. **Headline vocabulary mismatch: generated `all_satisfied` / `not_assessed` (underscore)
   vs study-policy `all-satisfied` / `not-assessed` (hyphen).** `violation` and
   `indeterminate` already match. A naive projection KeyErrors in the policy. The evaluator
   normalized in its projection layer. **Items 9/10** must pin ONE canonical headline
   vocabulary across the generated `ConstraintReport` and the study policy.
   (`real_evaluator.py:HEADLINE_TO_POLICY`.)

6. **Evidence envelope: the generic projection works, and non-finite operands need an
   encoding decision.** The generated report is a Pydantic `ConstraintReport` (a generated
   class); S6's `Evidence` is generic JSON. Projecting report → generic response keys was
   clean — confirming the concept's bet that runtime evidence types need not depend on
   generated classes (`ModelEvidence`). But an indeterminate case's observed operand is a
   real NaN, which standard JSON cannot round-trip; the projection tagged it
   (`{"__nonfinite__": "nan"}`) to keep artifacts valid, stable, content-addressable JSON.
   **Item 11**'s evidence schema must choose the canonical non-finite encoding.
   (`real_evaluator.py:_project`, `_json_safe`.)

7. **The validator demands ExitPoint write handlers even in no-persist mode.** A pure
   in-memory evaluator that never writes still had to build an output router with JSON
   handlers for the generated custom types, because `PipelineValidator` requires a write
   handler per ExitPoint output type unconditionally. Minor coupling (validity vs
   writability). **Item 10** should note it for the in-memory backend.
   (`real_evaluator.py:_build_prepared` builds `create_output_router_with_json_schemas`.)

8. **Package-load names the package by its declared name.** The sealed package's internal
   imports are `from wi014_s4. ...`, so it must be importable under `wi014_s4` (the on-disk
   dir is `package_live`; the probe symlinks it). **Item 9**'s package-load protocol must
   place/load the sealed package under its declared package name.
   (`real_evaluator.py:load_package`.)

## Question / Goal

**[INHERITED: `.project/reference/epic_constraint_execution.md` Item 0; concept Appendix B
S4–S6.]** Assumption under test: S6's crash-safe study-lifecycle machinery, reused as-is,
runs against S4's *real* sealed generated package through an S5-shaped prepared-pipeline
evaluator — and any interface mismatch between S6's fake evaluator shape and the real
prepared pipeline can be named precisely before Items 9–11 freeze production schemas.

Pass criteria (epic Item 0):
1. Three verdict classes land as `completed` with correct evidence; invalid proposal stays a
   `ProposalRecord`; resume reproduces the uninterrupted run.
2. Any evaluator-interface mismatch is named precisely — or its absence stated.
3. Prepare-once vs rebuild measured on the real package.

## Log

### Context (read-only)

- Read the concept (Appendix B S4–S6 and carry-forwards), S4/S5/S6 findings (Reproduction
  sections), the epic Item 0 section, and S6's `study_lifecycle.py` in full.
- Verified environment facts: teax `main` ≥ `7560d65` merged (scalar persistence done);
  fusion-tea venv imports simkit 2.12.5 + pydantic; `study_lifecycle.py` imports clean.
- Mapped the real package (`out/package_live`): EntryPoint emits one `ToyPlantParams`
  structured channel; the constraint module carries a real Kleene runtime (`_cmp` returns
  `None` on a non-finite operand → `indeterminate`); the aggregator headline vocabulary is
  underscore-form; `ToyPlantParams` is a plain (non-strict) `float`-field model, so it
  accepts `NaN`/`inf`.

### Regenerate S4's sealed package (scope 1)

Ran S4 probe A (live SysIDE in the agentic-mbse uv env). `PROBE A PASSED`;
`executable_fingerprint = 3be9f72d…` — byte-identical to the prior session (cross-session
determinism holds).

### Wire the S5-shaped evaluator + drive S6 (scope 2)

- `real_evaluator.py`: ports S5's prepared-mapping scaffolding over the real package, adds
  seal verification, the candidate→typed-entry bridge, and the generated-report → generic
  `Evidence` projection. Presents S6's exact `evaluate(inputs, attempt_number)` interface.
- `integration_probe.py`: imports S6's `StudyStore`, `StudyRunner`, `DeterministicPolicy`,
  `PreparedCandidateStrategy`, `Compatibility`, `CrashController` **as-is**; substitutes the
  real evaluator and a real budget-point domain validator (installed by monkeypatch — see
  mismatch 3); real candidate list; subprocess crash-resume orchestration.
- Two wiring fixes surfaced and were resolved: the package must be importable as `wi014_s4`
  (symlink — mismatch 8), and the validator needs custom-type write handlers even with
  `persist_outputs=False` (router built with JSON schemas — mismatch 7).
- `verify` reports **40/40 checks PASSED**, stable across three repeats.

### Benchmark (scope 3)

`bench --n 100`, two runs: prepare-once **63.7×–64.8×** faster than rebuild-per-case;
100/100 verdict+margin parity between the two paths.

## Reproduction

From `/home/reid/1cfe/teax`. All three legs use the licensed host venv with simkit on the
path (teax's own `.venv`/`uv run` is broken for real-simkit runs, per S4/S5).

```bash
# (optional) regenerate S4's sealed package — needs live SysIDE
UV_CACHE_DIR=/tmp/agentic-mbse-uv-cache PYTHONPATH=/home/reid/1cfe/sysml-codegen/src \
  uv run --directory /home/reid/1cfe/agentic-mbse python \
  /home/reid/1cfe/sysml-codegen/.project/active/spike-vertical-slice-constraint-execution/probe_a_live.py

# integration verify (uninterrupted vs crash+resume; 40 invariant checks)
PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit \
  /home/reid/1cfe/fusion-tea/.venv/bin/python \
  .project/active/constraint-study-integration-spike/integration_probe.py verify

# prepare-once vs rebuild on the real package
PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit \
  /home/reid/1cfe/fusion-tea/.venv/bin/python \
  .project/active/constraint-study-integration-spike/integration_probe.py bench --n 100
```

Expected: `verify` prints `=== verify: 40/40 checks ===` and `INTEGRATION VERIFY PASSED`;
`bench` prints a JSON report with `prepared_vs_rebuild_parity_cases: 100` and a
`prepare_once_speedup_over_rebuild` far above 1.25. Timing varies by machine; the semantic
results and parity do not. Scratch dirs (`_work/`, `_pkg/`, `__pycache__/`) are gitignored
and regenerable.

Files (throwaway probe code, kept findings):
- `real_evaluator.py` — S5-shaped prepared-pipeline evaluator over the sealed package.
- `integration_probe.py` — S6 machinery driver (`run` / `verify` / `bench`).

## Open Questions / Follow-ups

- **Items 10/11 inherit the eight named mismatches above** — each is tagged to its item.
  Item 0's checkbox "name the mismatch or state its absence" is discharged: mismatches
  exist, all at the schema/naming/wiring layer, none architectural.
- **Not exercised here** (had upstream coverage, outside Item 0's scope): `execution_failed`
  and `assessment_failed` case states against the real package, zero-assertion packages,
  multi-instance expansion, and the `mid_staging` crash phase (S6 proved all of these
  against the fake evaluator; nothing about the real evaluator changes the store paths they
  exercise). A production Item 11 test suite should re-run S6's full outcome matrix against
  the real evaluator.
- **Non-finite JSON encoding** (mismatch 6) is a genuine schema decision for Item 11, not
  settled here — the probe's `{"__nonfinite__": "nan"}` tag is one option, not a
  recommendation.
