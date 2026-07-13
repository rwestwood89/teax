# Implementation Plan: Model Evaluator and Typed Entry (Item 10)

**Status:** Draft
**Created:** 2026-07-12
**Last Updated:** 2026-07-12
**Branch:** constraint-exec-epic

## Source Documents
- **Spec:** `.project/active/model-evaluator/spec.md`
- **Design:** `.project/active/model-evaluator/design.md` ← component details, D1–D7, INV1–INV6, the phase→failure map, and the parity equivalence class live here. This plan does not restate them.
- **Design review:** `.project/active/model-evaluator/design-review.md` (Approved-with-must-fixes; both must-fixes are folded into design rev 2).
- **Probe being productionized:** `.project/active/constraint-study-integration-spike/real_evaluator.py` (throwaway; the shape to port).

## Implementation Strategy

**Phasing rationale.** Two hard rules shape the order.

1. **Environment and fixtures are a hard prerequisite** — no evaluation test can run until teax's own venv holds the project deps and the sealed S4-lineage package is available as a committed fixture. That is Phase 0, gated before any product code.
2. **The isolation boundary is the highest-value thing to lock first** (design de-risk note, `design.md#next-stage-handoff`). INV1's kept test and the four isolation-clean modules come *before* the package-touching backend, so the no-generated-import rule is enforced from the first product commit instead of retrofitted. The four clean modules (`evidence.py`, `failure.py`, `entry_source.py`, `projection.py`) need neither the executor nor the generated package, so they can be built and proven package-free.

After that, the package-touching layer builds outward in dependency order: load the sealed package and stand up the prepare-once in-memory backend (Phase 2), add the file-backed audit path plus the NaN-aware parity fixtures (Phase 3), then complete the failure taxonomy and the three-distinguishable-outcomes proof and publish the public API (Phase 4).

**Critical path:** Phase 0 (env + fixture) → Phase 1 (isolation-clean core + INV1) → Phase 2 (in-memory backend, B3/B4 + S5 invariants) → Phase 3 (file-backed + parity) → Phase 4 (failure taxonomy + SC3 + public API).

**First proof point:** Phase 1's INV1 isolation test passing (AST allowlist scan + package-absent construction) over the four clean modules. That is the earliest signal that the central bet — runtime evidence never depends on generated classes — is enforced mechanically, not by discipline.

**Overall validation approach:** each phase starts with its test(s); each phase has an explicit green gate; the isolation test is the standing guard that every later phase must keep passing.

---

## Phase 0: Environment + Fixture Provisioning (prerequisite — no product code)

### Goal
Make teax's own venv able to run the evaluation tests, and make the sealed S4-lineage package a committed, self-contained test fixture. Everything after this phase assumes both are done.

### Assumption Under Test
- teax's checkout-local `.venv` can be provisioned with the project deps (it currently lacks them — this is the "broken for real-simkit runs" condition; S5 findings: "The checkout-local `.venv` does not contain project dependencies").
- The sealed package Item 0 used still verifies its seal after being copied into teax and can be loaded under its declared name `wi014_s4`.

### Steps

**0a. Provision teax's own venv.** The venv exists (`.venv/`, uv 0.10.0, CPython 3.12.3) but holds no project deps. Install both packages editable into it:
- [x] `uv pip install -e packages/teax-simkit[dev]`
- [x] `uv pip install -e packages/battery-tea-demo[dev]`
  (equivalently `uv pip install -e .[dev]` from root for workspace mode — CLAUDE.md Build & Development Commands.)

**Smoke check (gate 0a):**
- [x] `.venv/bin/python -c "import simkit, pydantic, numpy; print('deps ok')"` → prints `deps ok`
- [x] `.venv/bin/pytest packages/teax-simkit -q` → existing framework suite green (the four hard-coded-checkout-path tests S5 named may still fail; if so, run with `--ignore` for those files and record it — they do not exercise this item).

**Fallback (only if 0a fails for reasons outside this item — e.g. no package index reachable).** The design sanctions running under the licensed host venv until teax's own is stood up (`design.md#validation-approach`; spec Implementation Prerequisites). Record the borrowed-env form and proceed:
```bash
PYTHONPATH=/home/reid/1cfe/teax/packages/teax-simkit \
  /home/reid/1cfe/fusion-tea/.venv/bin/pytest \
  packages/teax-simkit/simkit/tests/evaluation -q
```
If the fallback is used, note in Implementation Notes *why* provisioning failed, so the env task is not silently marked done.

**0b. Provision the sealed-package fixture (reuse, do not regenerate).** Item 0's sealed package is the S4-lineage package the evidence tests need. It is on disk at
`/home/reid/1cfe/sysml-codegen/.project/active/spike-vertical-slice-constraint-execution/out/package_live`
(reachable now via the Item 0 spike's `_pkg/wi014_s4` symlink). **Reuse this exact package** — copy its tree into teax as a committed fixture so the test suite is self-contained and does not depend on the sibling repo path or on live SysIDE.
- [x] Copy the `package_live` tree (its Python package, `pipelines/pipeline.yaml`, `contracts/package_contract.json`; exclude `__pycache__`) into `packages/teax-simkit/simkit/tests/evaluation/fixtures/sealed_package/package_live/`.
- [x] Confirm the copied seal still verifies: hash every file under the tree against `contracts/package_contract.json`'s `artifact_hashes` and confirm no unhashed extras (the check `real_evaluator.py:verify_seal` performs). This is the acceptance test for the copy.
- [x] Commit the fixture tree. It is test data, not product code.

*Regeneration path (documented, not a test dependency):* the package can be regenerated via Item 0's recipe (live SysIDE in the agentic-mbse uv env — `findings.md` Reproduction, "Regenerate S4's sealed package"). This is the provenance/refresh path only; kept tests must not invoke it.

**0c. Author the input fixtures (reuse Item 0's candidate set).** The parity and verdict fixtures reuse Item 0's proven inputs. Fixed design attributes are `plant_length=4.0`, `plant_unit_cost=250.0`, `plant_width=3.0` (`real_evaluator.py:FIXED`); the varied field is `plant_budget`.
- [x] `budget=5000` → `satisfied`; `budget=2500` → `violated` (Item 0 verdict classes).
- [x] **F-budget:** `budget=NaN` → `indeterminate`, compared outputs `area=12`, `cost=3000` finite (`design.md#implementation-notes`, "Parity fixtures").
- [x] **F-output:** `plant_length=NaN` → `area=NaN`, `cost=NaN` (non-finite reaches a *compared* output).
- [x] For the file-backed leg, the entry JSON carries a **bare `NaN` token** (stdlib `allow_nan=True` round-trips it via `readers.py:35` / `writers.py:25–27`) — **not** the `{"__nonfinite__": …}` tag (that tag is digest-input only). See `design.md#implementation-notes`.

### Validation (gate)
- [x] Smoke check 0a green (or fallback recorded with reason).
- [x] Sealed-package fixture present under `tests/evaluation/fixtures/` and its seal verifies.
- [x] Input fixtures present for all five cases above.

**What We Know Works After This Phase:** teax's own env (or the recorded fallback) runs the framework suite; the sealed package loads and seal-verifies from inside teax; the fixture inputs exist.

---

## Phase 1: Isolation-Clean Core + INV1 Isolation Test (de-risk first)

### Goal
Build the four generated-import-clean modules and the kept isolation test that guards them, before any package-touching code exists. This locks the no-generated-dependency rule from the first product commit.

### Assumption Under Test
The evidence envelope, entry source, failure types, and projection can all be built, imported, and constructed with the generated package **absent** from `sys.path`, and import only from the allowlist (stdlib, `pydantic`, `simkit`-internal). If any of them needs a generated import, the central bet (`design.md#core-concept`) is wrong and we find out now.

### Test Stencil (write these first)
```python
# tests/evaluation/test_isolation.py  — INV1, two legs (design.md#required-invariants INV1)
import ast, pathlib
CLEAN = ["evidence.py", "entry_source.py", "failure.py", "projection.py"]
ALLOWED_ROOTS = {"pydantic", "simkit"}  # plus the stdlib set (enumerate or use sys.stdlib_module_names)

def test_clean_modules_import_only_allowlist():
    for name in CLEAN:
        src = (EVAL_DIR / name).read_text()
        tree = ast.parse(src)                      # AST, not runtime — catches TYPE_CHECKING/string-annotation imports
        for node in ast.walk(tree):
            for root in import_roots(node):        # handles Import + ImportFrom, top-level module root
                assert root in ALLOWED_ROOTS or root in STDLIB, f"{name} imports {root}"

def test_construct_evidence_with_generated_package_absent(monkeypatch):
    # ensure 'wi014_s4' is NOT importable, then import the four modules and build a ModelEvidence
    assert "wi014_s4" not in sys.modules
    from simkit.evaluation import ModelEvidence, ResponseEntry, EvidenceProvenance
    ev = ModelEvidence(responses={"headline": "indeterminate"}, outputs={"area": 12.0},
                       provenance=EvidenceProvenance(...), report=object())  # report opaque
    assert ev.responses["headline"] == "indeterminate"
```

### Changes Required

**See `design.md#component-overview` for each module's exact contents and `design.md#required-invariants` (INV1) for the scan's two legs.**

- [x] `simkit/evaluation/__init__.py` (NEW) — start the package; export the clean types as they land.
- [x] `simkit/evaluation/evidence.py` (NEW, isolation-clean) — `ModelEvidence` (frozen), `ResponseEntry`, `EvidenceProvenance`, `CANONICAL_HEADLINE` constant. Provenance fields per `design.md#deferred-item-decisions`: `executable_fingerprint`, `evidence_schema_version`, `evaluator_version`, `input_digest` (no candidate/study identity, no timestamp).
- [x] `simkit/evaluation/failure.py` (NEW, isolation-clean) — `EvaluationPhase` enum (`entry_validation | preparation | module_execution | output_write`), `EvaluationFailure` (frozen: phase, cause, module_or_channel, `retryable` always `False`, partial_artifacts), `EvaluationFailed` exception carrying it (D4).
- [x] `simkit/evaluation/entry_source.py` (NEW, isolation-clean) — `MappingEntrySource` (Shape A, D1). Port `real_evaluator.py:90` `MappingEntrySource` unchanged in shape: `from_spec` derives the channel→type map from EntryPoint bindings; `validate` refuses missing/extra/wrong channel-model instance, naming expected vs got (INV2). Non-finite passes by construction.
- [x] `simkit/evaluation/projection.py` (NEW, isolation-clean, duck-typed) — `project(run_result, report) -> ModelEvidence`. Read-only headline normalize via `CANONICAL_HEADLINE` (generated `all_satisfied`→`satisfied`, `violation`→`violated`, `indeterminate`/`not_assessed` unchanged; Item 0 mismatch 5); per-constraint `r.status` pass-through (already canonical); output unwrap `v.root` (`RootModel[float]`); attach report opaque. Reads the report by attribute only; never imports it. Shape in `design.md#implementation-notes` snippet.
- [x] `tests/evaluation/test_isolation.py` (NEW) — the two legs above.
- [x] `tests/evaluation/test_projection.py` (NEW) — unit-test `project` against a **fake** duck-typed report (a simple object with `.headline`, `.results`, `r.constraint_id`/`r.status`) and a fake run-result — no package needed. Cover: headline normalization for all four generated values; status pass-through; output unwrap; opaque report attached unchanged.

### Validation (gate)
**Automated:**
- [x] `pytest tests/evaluation/test_isolation.py tests/evaluation/test_projection.py -q` → green.
- [x] Full framework suite still green (no regressions from the new package).

**What We Know Works After This Phase:** the four clean modules import allowlist-only and construct with the generated package absent; `project` normalizes correctly against a duck-typed report. The isolation guard is live and every later phase must keep it green.

---

## Phase 2: Package Load + Prepared In-Memory Backend (touches package)

### Goal
Load the sealed package under its declared name and stand up the prepare-once in-memory evaluator. This is where B3 (non-finite reaches the verdict) and the S5 invariants become kept teax tests against the real package.

### Assumption Under Test
- **B3:** a non-finite float passes entry construction/validation and flows to the Kleene predicate, yielding `indeterminate` (design.md Key Bets; Item 0).
- **B4:** the private `_execute_entry` override contract holds — a seeded context reaches the channels, and prepare-once/run-per-case behaves as Item 0 measured.
- **S5's four invariants** hold against the real package, not just S5's toy graph.

### Test Stencil (write first)
```python
# tests/evaluation/test_prepared_evaluator.py
def test_nonfinite_budget_reaches_indeterminate_verdict(prepared):        # B3, spec SC5
    params = prepared.ToyPlantParams(toy_plant__Toy_Plant__plant_budget=float("nan"), **FIXED)
    ev = prepared.evaluate({"toy_plant_params": params})
    assert ev.responses["headline"] == "indeterminate"                     # not rejected as invalid

def test_execute_entry_override_seeds_channels(prepared):                  # B4 mitigation
    # a seeded MappingContext reaches the entry channel without any file load
    ...

def test_invalid_typed_input_rejected_before_any_module_runs(prepared):    # INV2 / S5
    with pytest.raises(EvaluationFailed) as e:
        prepared.evaluate({"toy_plant_params": WrongModel()})
    assert e.value.failure.phase is EvaluationPhase.entry_validation       # names expected vs got

def test_no_output_directory_in_no_persist_mode(prepared, tmp_path):       # INV6 / S5
    prepared.evaluate({...}); assert not any(tmp_path.iterdir())

def test_fresh_context_per_case_no_channel_bleed(prepared):                # S5 isolation
    ...
```

### Changes Required

**See `design.md#architecture` (Prepare once / Evaluate per case) and `design.md#component-overview`.**

- [x] `simkit/evaluation/package_load.py` (NEW, touches package) — `PackageLoader` protocol, `ProvisionalPackageLoader` (D7). Port `real_evaluator.py:verify_seal` (inlined seal check) and `load_package` (symlink-under-declared-name → import under `wi014_s4`). Point it at the Phase 0 committed fixture tree.
- [x] `simkit/evaluation/evaluator.py` (NEW, touches package) — `Evaluator` protocol; `PreparedEvaluator` (prepare-once in-memory). Port `real_evaluator.py:_build_prepared` + `RealPreparedEvaluator`, **minus `attempt_number`** (D3), **minus the dict-rewrite** (projection is now `projection.project`). Wire:
  - prepare: loader → `_build_schema_type_registry` / `_build_entry_loaders` / in-memory JSON router via `create_output_router_with_json_schemas([...], in_memory=True)` (D5) → `build_graph(spec)` (the `preparation` phase, once) → `MappingEntrySource.from_spec`.
  - evaluate: `source.validate` → seed fresh `MappingContext` → `MappingExecutor` (overrides only `_execute_entry`) → `executor.run(graph, context, persist_outputs=False)` → `projection.project(result, report)`.
  - the per-case `except Exception → raise EvaluationFailed(EvaluationFailure(phase=module_execution, cause=type+message, retryable=False))` catch-all (replaces the probe's `ExecutionFailed(str)`; full taxonomy refined in Phase 4).
- [x] Extend `simkit/evaluation/__init__.py` — export `Evaluator`, `PreparedEvaluator`, `PackageLoader`, `ProvisionalPackageLoader`.
- [x] `tests/evaluation/conftest.py` (NEW) — a `prepared` fixture that loads the sealed fixture package once per session; `FIXED` constant; channel-ID constants (`AREA_CH`/`COST_CH`/`REPORT_CH`/`ENTRY_CH` from `real_evaluator.py:182`).
- [x] `tests/evaluation/test_prepared_evaluator.py` (NEW) — the stencils above (B3, B4, INV2, INV6, context isolation).

### Validation (gate)
**Automated:**
- [x] `pytest tests/evaluation/test_prepared_evaluator.py -q` → green.
- [x] Isolation test (Phase 1) still green — `package_load.py`/`evaluator.py` are the *only* modules allowed to touch the package; they are outside the scanned set (D2). Confirm the scan set still lists exactly the four clean modules.

**Manual:**
- [x] Evaluate `budget=NaN` and confirm evidence carries `indeterminate` with finite `area`/`cost` — the B3 end-to-end check against the real package.

**What We Know Works After This Phase:** the sealed package loads and evaluates; non-finite input reaches the verdict; entry validation rejects wrong inputs pre-execution; no directory is written in no-persist mode; each case gets a fresh context. The in-memory backend is real.

---

## Phase 3: File-Backed Backend + NaN-Aware Parity Fixtures

### Goal
Add the file-backed audit path sharing the same `project(...)`, and the kept parity test with the two mandatory non-finite fixtures. This is what admits the fast in-memory path (INV4).

### Assumption Under Test
The two backends return equivalent-class-equal results over the enumerated equivalence class (`design.md#required-invariants` INV4), **including** the NaN-aware numeric-equality rule — which F-output actually exercises (a compared output is non-finite on both legs), where F-budget only exercises verdict + finite-output parity across a NaN input (design.md must-fix M1 correction).

### Test Stencil (write first)
```python
# tests/evaluation/test_parity.py
def nan_aware_equal(a, b):
    return a == b or (not math.isfinite(a) and not math.isfinite(b)
                      and math.isnan(a) == math.isnan(b) and (a > 0) == (b > 0))

@pytest.mark.parametrize("case", ["satisfied", "violated", "F_budget", "F_output"])
def test_backends_agree(prepared, file_backed, case):
    inp = load_case(case)
    a, b = prepared.evaluate(inp), file_backed.evaluate(file_form(inp))
    for k in a.outputs:                                   # selected outputs, NaN-aware
        assert nan_aware_equal(a.outputs[k], b.outputs[k])
    assert a.responses == b.responses                     # verdict statuses string-exact
    # excluded: provenance, timestamps, digests, artifact paths, report on-disk encoding
```

### Changes Required
**See `design.md#architecture` (File-backed backend) and `design.md#implementation-notes` (Parity fixtures).**
- [ ] `simkit/evaluation/evaluator.py` — add `FileBackedEvaluator` (audit): standard `execute_pipeline` path (file entry, real router, `persist_outputs=True`) → the **same** `projection.project(...)`. Export it from `__init__.py`.
- [ ] `tests/evaluation/fixtures/` — file-form entry JSONs for all four parity cases (F-output uses a bare `NaN` token per Phase 0c).
- [ ] `tests/evaluation/test_parity.py` (NEW) — the NaN-aware equivalence-class comparison over the four cases; assert the excluded fields are not compared.

### Validation (gate)
- [ ] `pytest tests/evaluation/test_parity.py -q` → green for all four cases.
- [ ] F-output confirmed to drive a non-finite value into a *compared* output on both legs (add an assertion that `math.isnan(a.outputs["area"])`), so the NaN-aware rule is genuinely exercised — not vacuously passing.

**What We Know Works After This Phase:** both backends agree over the equivalence class; the NaN-aware rule is exercised directly by F-output; the fast path is admitted on real parity.

---

## Phase 4: Failure Taxonomy + Three Distinguishable Outcomes + Public API

### Goal
Complete the normalized failure taxonomy across the four phases, prove SC3's three distinguishable outcomes, and publish the final public API surface.

### Assumption Under Test
The four failure phases are distinguishable and correctly bound to real raise sites (`design.md#implementation-notes` phase→failure map): a module exception → `module_execution`; an entry rejection → `entry_validation`; a prepare-time validation error → `preparation`; and an `indeterminate` verdict is **evidence, never a failure** (INV5, SC3).

### Test Stencil (write first)
```python
# tests/evaluation/test_failure_taxonomy.py
def test_module_exception_is_module_execution(prepared):        # SC3 (a)
    with pytest.raises(EvaluationFailed) as e:
        evaluate_case_that_raises_in_run(prepared)
    assert e.value.failure.phase is EvaluationPhase.module_execution

def test_entry_rejection_is_entry_validation(prepared):         # SC3 (b) — different phase
    with pytest.raises(EvaluationFailed) as e:
        prepared.evaluate({"toy_plant_params": WrongModel()})
    assert e.value.failure.phase is EvaluationPhase.entry_validation

def test_indeterminate_is_evidence_not_failure(prepared):       # SC3 (c) / INV5
    ev = prepared.evaluate(nan_budget_case)                      # returns, does not raise
    assert ev.responses["headline"] == "indeterminate"

def test_every_raised_failure_is_terminal(prepared):            # D4
    ...  # any EvaluationFailure has retryable is False
```

### Changes Required
**See `design.md#implementation-notes` (the phase→real-failure map) and `design.md#required-invariants` (INV5).**
- [ ] `simkit/evaluation/evaluator.py` — wrap the prepare-time `build_graph` call to emit `phase=preparation` on validation failure (the probe did not; new, correct behavior). Confirm the per-case catch-all emits `module_execution` with `cause` = type+message and `module_or_channel` when known; `retryable=False` always (D4). `output_write` is file-backed-only and unreachable in no-persist mode — assert it is never emitted there.
- [ ] `simkit/evaluation/__init__.py` — finalize the full public API list (`design.md#component-overview` Public API): `MappingEntrySource`, `ModelEvidence`, `ResponseEntry`, `EvidenceProvenance`, `CANONICAL_HEADLINE`, `EvaluationPhase`, `EvaluationFailure`, `EvaluationFailed`, `Evaluator`, `PreparedEvaluator`, `FileBackedEvaluator`, `PackageLoader`, `ProvisionalPackageLoader`.
- [ ] `tests/evaluation/test_failure_taxonomy.py` (NEW) — the stencils above (SC3, INV5, D4).

### Validation (gate — final)
- [ ] `pytest tests/evaluation -q` → all evaluation tests green (isolation, projection, prepared evaluator, parity, failure taxonomy).
- [ ] Full framework suite green (no regressions): `pytest packages/teax-simkit -q` (or the borrowed-env form if Phase 0 fell back).
- [ ] Public API importable: `python -c "from simkit.evaluation import *"` resolves every name above.
- [ ] Isolation test still green — the guard held across all four phases.

**What We Know Works After This Phase:** the full kept suite — S5's four invariants, F-budget + F-output parity, isolation (AST + allowlist + package-absent), three distinguishable outcomes, non-finite-reaches-verdict — passes against the real sealed package. Item 10's evaluator API is production and ready for Item 11 to consume.

---

## Environment Setup

**See CLAUDE.md Build & Development Commands and Phase 0 above.** teax's own `.venv` is provisioned in Phase 0a; the borrowed fusion-tea venv (Item 0 reproduction recipe) is the sanctioned fallback only if provisioning fails for reasons outside this item.

## Risk Management

**See `design.md#potential-risks` for the full analysis.** Phase-specific mitigations:
- **Phase 0:** if provisioning fails, the fallback is explicit and its use must be recorded with a reason (do not silently mark the env task done).
- **Phase 1:** the isolation test is written *before* the package-touching code, so isolation rot (a convenience `from wi014_s4 import ...`) fails the build from the first product commit. The AST scan + package-absent legs together have teeth; either alone has a gap (design M2 resolution).
- **Phase 2:** B4's private-hook coupling (`_execute_entry`) is a real risk; the seeded-context test asserts the override contract so a teax refactor of the entry path fails loudly.
- **Phase 3:** the naive-NaN-parity trap is mitigated by F-output, whose *compared* output is non-finite — add the `isnan` assertion so the rule is exercised, not vacuously passed.

## Implementation Notes

[TO BE FILLED DURING IMPLEMENTATION — leave empty now]

### Phase 0 Completion
**Completed:** 2026-07-12
**Actual Changes:**
- Provisioned teax's own `.venv` (already existed, uv 0.10.0, CPython 3.12.3, no project deps): `uv pip install -e packages/teax-simkit[dev] -e packages/battery-tea-demo[dev] --python .venv/bin/python`. Smoke check green; framework suite green except the four pre-existing hard-coded-checkout-path tests in `test_no_battery_deps.py` (fail with `FileNotFoundError: /home/reid/teax` — unrelated to this item, matches the plan's documented expectation). No fallback needed.
- Copied Item 0's sealed package tree (`package_live`, 25 files excl. `__pycache__`) into `packages/teax-simkit/simkit/tests/evaluation/fixtures/sealed_package/package_live/`. Re-verified the seal against the copy: 24/24 artifact hashes match, zero unhashed extras, fingerprint `3be9f72d237e8c1c1fae19beb2e242d4134f57f9ee91428669317749d5714eea` unchanged.
- Read the package's `pipeline.yaml`, `toy_plant_params.py`, `demo_plant_affordable.py`, `panel_area_impl.py`/`panel_cost_impl.py` to confirm the fixture arithmetic: `area = length * width`, `cost = area * unit_cost`, budget compared via a Kleene `<=` that returns `None` (→ `indeterminate`) when either operand is non-finite. Confirms F-budget (`budget=NaN`, `cost`/`area` stay finite at 3000/12) and F-output (`plant_length=NaN` → `area`/`cost` both NaN) match the design's stated fixture behavior exactly.
- Authored four entry fixtures under `tests/evaluation/fixtures/entries/`: `satisfied.json` (budget=5000), `violated.json` (budget=2500), `f_budget.json` (budget=NaN, bare token), `f_output.json` (plant_length=NaN, bare token). Verified all four round-trip through stdlib `json.load` (matches `readers.py:35`'s `allow_nan=True` default) with the NaN cases producing real `float('nan')`.

**Issues:** None.
**Deviations:** None — no fallback env needed; the four failing tests are the ones the plan named in advance, so no additional recording was required beyond noting them here.

### Phase 1 Completion
**Completed:** 2026-07-12
**Actual Changes:**
- `simkit/evaluation/failure.py` (NEW) — `EvaluationPhase` enum, `EvaluationFailure` (frozen, `retryable` defaults `False` and evaluator code never overrides it), `EvaluationFailed` exception carrying the failure.
- `simkit/evaluation/evidence.py` (NEW) — `ResponseEntry` (a `Literal["satisfied","violated","indeterminate","not_assessed"]` type alias, not a wrapper class — the "entries" in `responses` are plain canonical-vocabulary strings, matching the Phase-1 test stencil's `ev.responses["headline"] == "indeterminate"`), `CANONICAL_HEADLINE`, `EvidenceProvenance`, `ModelEvidence` (frozen, `report: Any`).
- `simkit/evaluation/entry_source.py` (NEW) — `MappingEntrySource`, ported unchanged in shape from `real_evaluator.py`. Deviation from the probe: `validate` raises `EvaluationFailed(EvaluationFailure(phase=ENTRY_VALIDATION, ...))` directly instead of bare `ValueError`/`TypeError` — this is what makes INV2 ("names expected vs got", phase-tagged) hold at the source instead of needing a wrapping catch in `evaluator.py`.
- `simkit/evaluation/projection.py` (NEW) — `project(result, report, *, provenance) -> ModelEvidence`. Deviation from the design's two-arg prose signature: `provenance` is a required keyword-only third parameter, not patched on afterward. Reasoning: `ModelEvidence` is frozen, so "build without provenance, then patch" would need a `model_copy` two-step for every caller; a required parameter keeps `project` a total function and keeps the isolation-clean module free of any fingerprint/versioning knowledge (that stays in evaluator.py, Phase 2). Scalar-output selection is a duck-typed `hasattr(value, "root")` check — this is what lets the same function generalize across pipelines without hardcoding channel names.
- `simkit/evaluation/__init__.py` (NEW) — exports the four clean modules' public names built so far.
- `tests/evaluation/test_isolation.py` (NEW) — both INV1 legs: AST allowlist scan (stdlib ∪ `pydantic` ∪ `simkit`-internal, including relative imports) over the four clean modules, and package-absent `ModelEvidence` construction with `wi014_s4` confirmed absent from `sys.modules`/`sys.path`.
- `tests/evaluation/test_projection.py` (NEW) — headline normalization for all four generated values, per-constraint status pass-through, output unwrap + non-scalar (report/ConstraintEvaluation) exclusion, and report-attached-unchanged, all against fake duck-typed objects (no package needed).

**Issues:** None.
**Deviations:** The two documented above (`EvaluationFailed` raised from `entry_source.validate` rather than bare exceptions; `provenance` as a required parameter of `project` rather than a two-step patch) — both are additive precision on the design's prose, not contradictions of it.

**Gate:** `pytest tests/evaluation/test_isolation.py tests/evaluation/test_projection.py -q` → 9 passed. Full framework suite (excluding the four pre-existing hard-coded-checkout-path failures) → green, no regressions.

### Phase 2 Completion
**Completed:** 2026-07-12
**Actual Changes:**
- `simkit/evaluation/package_load.py` (NEW) — `PackageLoader` Protocol, `ProvisionalPackageLoader` (D7): inlined seal verification (ported from `real_evaluator.py:verify_seal`) plus symlink-under-declared-name loading. Deviation from the probe: `link_root` and `package_dir` are constructor parameters, not module-level constants — the probe's `_PKG_ROOT` lived next to the throwaway file; production needs the symlink location caller-supplied (tests use a per-session `tmp_path_factory` dir) so the fixture tree stays the only committed artifact.
- `simkit/evaluation/evaluator.py` (NEW) — `Evaluator` protocol; `PreparedEvaluator` (prepare-once in-memory), porting `real_evaluator.py`'s `_build_prepared`/`RealPreparedEvaluator` minus `attempt_number` (D3) and minus the dict-rewrite (projection is now `projection.project`). `_MappingContext`/`_MappingExecutor` mirror the probe's `MappingContext`/`MappingExecutor` shape exactly (only `_execute_entry` overridden — B4). The per-case catch-all normalizes any executor exception to `EvaluationFailed(phase=MODULE_EXECUTION, ...)`. One addition ahead of the plan's own schedule: `build_graph` at prepare time is already wrapped to raise `EvaluationFailed(phase=PREPARATION, ...)` — the plan assigned this to Phase 4, but since `evaluator.py` was being written now anyway, doing it here means Phase 4 only needs to confirm/test it, not add it fresh.
- `simkit/evaluation/__init__.py` — exports extended with `Evaluator`, `PreparedEvaluator`, `PackageLoader`, `ProvisionalPackageLoader`.
- `tests/evaluation/conftest.py` (NEW) — session-scoped `prepared` fixture (loads the sealed fixture package once, symlink root in a `tmp_path_factory` dir); `FIXED` constant; `AREA_CH`/`COST_CH`/`REPORT_CH`/`ENTRY_CH` channel-ID constants from the fixture's `pipeline.yaml`.
- `tests/evaluation/test_prepared_evaluator.py` (NEW) — B3 (NaN budget → `indeterminate` with finite `area`/`cost`), satisfied/violated verdicts, B4 (`_execute_entry` override reaches the channels — asserted via correct `area`/`cost` values), INV2 (wrong-model entry rejected pre-execution, phase `entry_validation`), INV6 (no directory written under `persist_outputs=False`), and fresh-context-per-case isolation (no channel bleed across two sequential `evaluate()` calls on the same `prepared` fixture).

**Issues:** None. One transient mistake caught before commit: an ad hoc manual verification script imported `simkit.evaluation.evaluator` with a redundant `sys.path.insert` that shadowed the editable install, producing a spurious `ModuleNotFoundError: wi014_s4`; re-running under a plain `.venv/bin/python` (no manual path manipulation) succeeded — not a product defect, noted here only because it briefly looked like one.

**Deviations:**
- `PackageLoader`/`link_root` made caller-configurable (above) rather than following the probe's hardcoded sibling-directory constant.
- The `preparation`-phase `EvaluationFailed` wrapping (plan's Phase 4 item) implemented now instead of Phase 4, since it was cheap to add while writing `evaluator.py`'s `__init__` the first time.

**Gate:** `pytest tests/evaluation -q` → 15 passed (isolation 2, projection 7, prepared-evaluator 6). Isolation test (Phase 1) still green — `evaluator.py`/`package_load.py` are outside the four-module scan set, confirmed. Full framework suite green (excluding the four pre-existing hard-coded-checkout-path failures). Manual B3 end-to-end check against the real sealed package: `budget=NaN` → `headline: indeterminate`, `outputs: {area: 12.0, cost: 3000.0}` — matches the design's stated fixture arithmetic exactly.

### Phase 3 Completion

### Phase 4 Completion

---

**Status:** Draft → In Progress → Complete
</content>
</invoke>
