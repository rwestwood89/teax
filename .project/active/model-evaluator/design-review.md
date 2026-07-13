# Design Review: Model Evaluator and Typed Entry (Item 10)

**Design:** `.project/active/model-evaluator/design.md`
**Spec:** `.project/active/model-evaluator/spec.md`
**Review File:** `.project/active/model-evaluator/design-review.md`
**Date:** 2026-07-12
**Reviewer posture:** skeptical; verified every load-bearing claim against the runtime code and the Item 0 / S5 findings, not the design's word.

---

## Fundamental Assessment

**Sound.** The design productionizes a seam Item 0 already drove end to end (40/40, three repeats) with zero changes to the runner/store. The core shape — subclass the executor, override only `_execute_entry`, hold the generated report opaque, split "infeasible" (evidence) from "broke" (failure) — is exactly what the probe proved, minus the throwaway bits (`attempt_number`, the dict-rewrite). The `simkit/evaluation/` subpackage with an isolation-clean core and a package-touching backend is the right cut, and the "zero changes to existing runtime files" claim holds up under inspection (see Dimension 2). This is not over-engineering: every abstraction traces to a named Item 0 mismatch or a spec requirement.

Two things need fixing before implementation, and both live in the **validation layer**, not the core design: the isolation test's teeth are under-specified, and the mandated NaN parity fixture does not exercise the invariant its own rationale describes (and contradicts an Item 0 finding without reconciling it). Neither touches the architecture. Verdict: **Approved-with-must-fixes**.

---

## Dimensional Review

### 1. Spec Compliance
**Assessment:** Concerns

Every success criterion maps to a design element, and the four spec-deferred items are resolved with recorded decisions. Provenance grades are carried faithfully: D1 is correctly `[OWNER]`; the deferred resolutions are honestly agent-grade. The Shape A execution matches the reserved-decision consequences in the spec (source refuses wrong channel-model instance; field-value correctness lives at the Item 11 bridge; non-finite passes by construction).

The concern is SC "Both backends agree (kept parity test) … with the NaN/indeterminate case." The design carries the spec's NaN-parity rationale verbatim into its Risks and Validation sections, but that rationale is imprecise about the ToyPlant fixture — see must-fix 1 and Dimension 5. This is a capture-fidelity issue: the design **hardened an imprecise inherited requirement** rather than surfacing that it doesn't fit the actual fixture (capture-fidelity Law 4). The requirement is `[INHERITED]` from the concept; the design should have flagged the mismatch, not repeated it with more confidence.

### 2. Pattern Consistency
**Assessment:** Pass

"Zero changes to existing runtime files" is credible — I walked each component against the code:

- **Prepare-once backend.** `PipelineExecutor.build_graph` (`pipeline_executor.py:104`) is a thin `self._validator.validate(spec)`; `run` (`:107`) takes a prebuilt graph + fresh context and never re-validates topology. The prepare/run split is a first-class runtime property, not a spike trick. No change needed.
- **`_execute_entry` override.** It is an ordinary method (`pipeline_executor.py:167`) the probe subclasses to read from a seeded context. Subclassing, not editing. No change.
- **In-memory JSON-router workaround.** `create_output_router_with_json_schemas(custom, in_memory=True)` already exists (`output_router.py:288-292`); the `in_memory` flag threads to `OutputRouter(..., in_memory=in_memory)` (`:285`). The router is constructed inside the new `evaluator.py`, so the `pipeline_validator.py:326` write-handler coupling is satisfied by construction with no validator edit.
- **INV6 (no output dir in no-persist).** `run` gates both `_ensure_exit_handlers` and `write_outputs` on `persist_outputs` (`:122-123, :148-156`). Nothing writes and no directory is created when the flag is off. Confirmed, no change.

One honest caveat (nice-to-have, not blocking): the design depends on three *private* executor hooks staying stable — `_execute_entry`, `_load_entry_binding`, `_execute_module`. Subclassing a `_`-prefixed method is a real coupling; if teax refactors the entry-loading path, the evaluator breaks silently. This is a hidden bet worth stating (Dimension 7).

### 3. Abstraction Quality
**Assessment:** Pass

Five modules, each earning its place. The isolation-clean / touches-package split is the load-bearing boundary and it is drawn cleanly: `evidence.py`, `entry_source.py`, `failure.py`, `projection.py` depend only on generic types; `evaluator.py`, `package_load.py` legitimately touch the package and are excluded from the scan by design (D2). The `PackageLoader` seam isolates the Item 9 swap to one module. Holding the report as `Any` read by duck-typed attribute access (`report.headline`, `r.status`) is the right mechanism for the no-generated-dependency rule — Item 0 confirmed the projection is clean (`real_evaluator.py:_project`).

### 4. Duplication Avoidance
**Assessment:** Pass

Both backends share one `project(...)` and one vocabulary; the parity test is what admits the fast path. No parallel projection logic to drift. The design explicitly ports from the probe rather than reinventing.

### 5. Data Structure Clarity
**Assessment:** Concerns

`ModelEvidence`, `ResponseEntry`, `EvidenceProvenance`, `EvaluationFailure` are all frozen and explicitly typed. The provenance field set is well-reasoned (see Dimension 7 — the exclusion of candidate identity is not just fine, it is *required* by Item 0's content-addressed dedup).

The concern is the **NaN parity equivalence class as applied to the actual fixture** (feeds must-fix 1). The equivalence class compares "selected outputs, matched by stable ID, NaN-aware" and "verdict statuses, string-exact," excluding the report's on-disk encoding. For the mandated NaN/indeterminate fixture (budget = NaN):

- The **selected outputs are `area` and `cost`, both finite** — `area = 4×3 = 12`, `cost = 250×12 = 3000` (Item 0: "cost fixed at 3000"). Budget feeds only the constraint predicate (`cost ≤ budget`), not the numeric outputs.
- The NaN lives **only in the report's observed operand** (`report.results[].observed`), which the equivalence class **excludes** (opaque report on-disk encoding).
- The verdict status is the string `"indeterminate"` on both sides — a string compare, no NaN involved.

So no compared field is ever non-finite in this fixture. The NaN-aware numeric-equality rule is correct to have, but it is **not exercised** by the case the spec calls "the case the whole architecture exists to preserve." The fixture proves indeterminate-verdict parity plus finite-output parity across a NaN *input* — a real and worthwhile check — but the design's stated rationale ("the file-backed path round-trips a NaN through JSON while the in-memory path holds a real `float('nan')`, and `NaN != NaN`") describes a comparison that does not occur on any compared field.

### 6. Route Safety
**Assessment:** Pass

The failure taxonomy is the "routing" surface here, and it is bound to real raise sites. I verified each:

- `entry_validation` — `MappingEntrySource.validate` raises pre-execution (missing/extra/wrong channel-model instance). Reachable and distinct under Shape A: passing a wrong-class Pydantic instance triggers it (`real_evaluator.py:119-123`). This is the "schema failure" SC3 exercises.
- `preparation` — `build_graph → validate` (`pipeline_validator.py:326` write-handler, `:363-378` producer/declaration mismatch). Runs once at prepare; the evaluator must wrap the `__init__` `build_graph` call to emit `phase=preparation` (the probe does not — new, correct behavior in the new subpackage).
- `module_execution` — every enumerated raise site is real: MultiOutput missing field (`:205`), single-output shape mismatch (`:226`), field-extraction `AttributeError`→`PipelineExecutionError` (`:397`), None-on-Optional (`:404`), plus arbitrary exceptions inside `module.run()`.
- `output_write` — file-backed only; `write_outputs` is gated on `persist_outputs` (`:148`), so it is genuinely unreachable in no-persist mode. Honestly stated (INV5, taxonomy).

No real failure path lands in no phase: the evaluator wraps the entire `executor.run()` call and maps any escaping exception to `module_execution`, and `preparation`/`entry_validation` are caught earlier in their own steps. One wording imprecision (nice-to-have): the Implementation-Notes prose says `module_execution` is "anything raised inside `module.run()`," but `:205`, `:226`, and `:397` are raised by the executor's `_execute_module` *wrapper* while gathering inputs / decomposing outputs, not literally inside `module.run()`. The enumerated list is right; the one-liner should read "raised during the per-case run loop."

### 7. Bets & Decisions Integrity
**Assessment:** Concerns

The stated bets B1–B3 are genuine claims about reality, each with a real "if false," each backed by an Item 0 observation. Good.

- **B4 is a decision dressed as a bet.** "No failure the evaluator raises is transiently retryable" — the "if false" is immediately defused by its own body ("but transient retry is the runner's layer, so the evaluator never raises it"). That is a scoping decision (it *is* D4), not a bet about the world. Move it to Decisions or reword. Minor.
- **Hidden bet (surface it): the evaluator depends on private executor extension points.** Subclassing `SerialPipelineExecutor` and overriding `_execute_entry`, plus reading `_load_entry_binding`/`_execute_module` behavior, bets that these `_`-prefixed hooks stay stable across teax versions. If teax refactors the entry path, the evaluator breaks with no compile-time signal. Not blocking, but it belongs in Key Bets with a mitigation (a kept test that asserts the override contract, or a note that teax should treat `_execute_entry` as a stable extension point).
- **Hidden bet: the file-backed leg preserves NaN through `model_dump(mode="json")` + stdlib `json`.** The parity fixture rests on this, and Item 0 explicitly found the opposite ("a NaN budget cannot travel through the file-backed JSON entry"). Unstated and unreconciled — see must-fix 1.

**Decision D-provenance is correct and under-justified.** Excluding `candidate_id`/`study_id` from evidence is defended on B2 determinism alone. The *harder* proof is in Item 0: a deliberate replicate produced "distinct `candidate_id`, identical inputs, one shared content-addressed artifact." If evidence carried `candidate_id`, two replicates could not share one artifact — so exclusion is not merely determinism-friendly, it is *required* by the store's content-addressed dedup. Auditability is preserved through the runner's own record (which owns identity) plus `input_digest` as a cross-check anchor. Citing the replicate finding would make this decision bulletproof. Not a must-fix.

### 8. Reader Comprehension
**Assessment:** Pass

Layers diagram, plain "prepare once / evaluate per case" framing, a clear Core Concept stated before mechanism, and the one hard rule ("runtime evidence and entry types never depend on generated classes") called out up front. "Isolation-clean" is defined at first use. A tired engineer can skim this once and know what is built and why. No comprehension-blocking voice.

---

## Issues by Severity

### Critical
*(none — the foundation is sound)*

### Major (must-fix before implementation)
- **M1. NaN parity fixture doesn't exercise its stated invariant, and contradicts Item 0.** The mandated NaN/indeterminate fixture's compared outputs (`area`, `cost`) are finite; the NaN lives only in the excluded report, and the verdict is a string. So the NaN-aware numeric-equality rule is never exercised. Separately, the design asserts "the file-backed path round-trips a NaN through JSON" while Item 0 found "a NaN budget cannot travel through the file-backed JSON entry" — an unreconciled premise conflict. — Dimensions 1, 5, 7.
- **M2. Isolation test teeth are under-specified.** "Scan … for any generated symbol (assert none)" is a blacklist that (a) doesn't say whether the scan is static/source or runtime, so a `TYPE_CHECKING`-guarded or string-annotation generated import slips a runtime scan, and (b) needs to know the generated symbol names — but the package name is provisional (`wi014_s4`) and Item 9 may rename it. — Dimension 2/6.

### Minor (nice-to-have)
- B4 is a decision framed as a bet — move to Decisions or reword.
- State the hidden bet on private executor hooks (`_execute_entry` et al.) in Key Bets with a mitigation.
- Taxonomy prose "inside `module.run()`" should read "during the per-case run loop" to match the enumerated executor-level raise sites (`:205`, `:226`, `:397`).
- Strengthen the provenance-exclusion decision by citing Item 0's content-addressed replicate finding (distinct `candidate_id`, shared artifact) as the hard reason candidate identity must stay out of evidence.

---

## Recommendations

1. **Fix M1.** Reconcile with Item 0 and correct the rationale. Two parts:
   - *Reconcile the round-trip claim.* The runtime reader/writer **can** carry NaN: `read_json_model` uses `json.load` (`readers.py:35`) and `write_json_model` uses `json.dump(model_dump(mode="json"))` (`writers.py:25-27`), both with stdlib `allow_nan=True` default, so a bare `NaN` token round-trips. Item 0's "cannot travel" is about the study proposal path, not a hand-authored parity fixture. State this explicitly and specify the fixture entry file carries a bare `NaN` token (not the `{"__nonfinite__": …}` tag, which is digest-only).
   - *Correct what the fixture proves.* For the ToyPlant fixture the NaN is confined to the excluded report; the fixture proves **indeterminate-verdict + finite-output parity across a NaN input**, not NaN-aware numeric output equality. Either say that plainly, or add a fixture whose *selected output* is non-finite if NaN-aware output comparison must be exercised directly. Keep the NaN-aware rule regardless (it is cheap insurance and correct), but stop describing it as the thing this fixture tests.
2. **Fix M2.** Specify the isolation test concretely, so INV1 fails on violation:
   - Make the scan **static/source-level (AST or text)**, not runtime module introspection, so a `TYPE_CHECKING`-guarded or string-annotation generated import is caught.
   - Prefer an **import allowlist** (the four clean modules may import only from stdlib, `pydantic`, and `simkit`) over a blacklist of generated names — robust to the provisional package name and to Item 9's rename.
   - Keep the **package-absent runtime construction** as the second leg (catches dynamic `importlib`). The two legs together have real teeth; either alone has a gap.
3. Apply the four minor items above.

---

## Resolutions

*(Design-agent, 2026-07-12. All must-fixes and nice-to-haves incorporated into `design.md`.)*

- **M1 (NaN parity) — resolved.** Added "Parity fixtures and non-finite handling" to Implementation
  Notes: states precisely what each leg carries (in-memory holds `float('nan')`; file-backed
  mechanically round-trips a bare `NaN` token via stdlib `allow_nan=True`, `readers.py:35` /
  `writers.py:25–27`), reconciles Item 0's "cannot travel" as the proposal/store layer not the raw
  reader/writer, and splits the fixtures: **F-budget** (budget=NaN → indeterminate; compared outputs
  finite — proves verdict + finite-output parity, *not* NaN-aware equality) and a new **F-output**
  (plant_length=NaN → area/cost non-finite — exercises NaN-aware numeric equality directly on both
  legs). Cross-leg claim scoped explicitly to file-expressible candidates. Validation #2 and the
  Risks NaN bullet updated to match.
- **M2 (isolation test) — resolved.** INV1 and Validation #3 rewritten: static AST source scan
  including `TYPE_CHECKING`/string-annotation blocks, an import **allowlist** (stdlib / `pydantic` /
  `simkit`-internal) instead of a generated-symbol blacklist (robust to the provisional package name
  and Item 9's rename), plus package-absent runtime construction as the second leg.
- **Nice-to-haves — all resolved.** B4 restated: the retryability claim moved into D4 as a decision;
  B4 is now the private-executor-hook bet (`_execute_entry` et al. staying stable) with its failure
  mode and mitigation. Taxonomy prose corrected to "raised during the per-case run loop" with the
  executor-wrapper raise sites (`:205`, `:226`, `:397`, `:404`) named. Provenance-exclusion decision
  strengthened by citing Item 0's content-addressed replicate finding (distinct `candidate_id`s
  sharing one artifact → candidate identity *must* stay out of evidence).

---

**Overall:** Approved-with-must-fixes
**Next Steps:** Record resolutions here, then return to the design-agent session (or re-run `/_my_design`) and point it at this review to incorporate M1, M2, and the minors. The reviewer does not edit the design. Once incorporated, proceed to `/_my_plan` — and per the design's own de-risk note, write INV1's kept isolation test (with M2's teeth) before porting `projection.py`.
