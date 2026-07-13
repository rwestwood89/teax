# Brief: CONSTRAINT-EXEC Item 14 Appendix B — teax docs + W5b loader-seal wiring (ready-to-apply)

Process: work synchronously; you MAY commit in this repo (sole writer). Suites: study(57+)/evaluation(25) green; framework green except the 4 known test_no_battery_deps failures; ruff clean. End commits with: Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

- **Design (rev 2, committed):** `.project/active/constraint-migration-acceptance/design.md` ← **all component details, file:line targets, bets, decisions, invariants live here. Do not restate; link.** Key anchors: five-workstream architecture (`design.md#architecture`), the dual carrier surfaces (`design.md#key-decisions` D1), the gain-fix tier (D2), within-v3 removal (D3), the epsilon boundary rule (`design.md#implementation-notes`), retirement grep targets (Appendix B), per-repo doc set (Appendix A).
- **Design review:** `design-review.md` — Approved-with-must-fixes; all three MF and five NTH incorporated into design rev 2 (verified this session).
- **Reference (fusion-tea harness):** `.project/reference/fusion-tea-ife-sweep/FACTS.md` — deletion target `sweep_ife.py:82`, outputs dir, `>`-vs-`>=` boundary hazard. Carries the paths for Appendix C.
| **S-TEAX** (Appendix B) | teax | W3c docs, W5b loader seal wiring, W5c tracking-key note | parallel to S-CODEGEN | Items 10–12 landed |
| **S-FUSION** (Appendix C) | fusion-tea | W4 IFE acceptance + prepare-once benchmark | **last** | W1 landed **and** W5b landed **and** Item 13 certified **and** Items 10–12 green |
Every retirement target in Appendix B deletes cleanly with the mapping test (Phase 2) and the catalog (Items 5–9) covering what the manifest reported; the loader's `.get("dropped_constraints", [])` tolerance (`loader.py:239`) and the three-key gate (which excludes `dropped_constraints`, verified in design review) make D3's within-v3 removal safe.

### Test Stencil (Write This First)
```bash
# The grep-clean gate is the test (INV-B). Run after deletion; must return zero.
grep -rn "collect_constraint_manifest\|render_constraint_report\|report_dropped_constraints" src/
grep -rn "not executable" src/         # no blanket warning (the kept halt at constraint_lowering.py:481 is distinct)
grep -rn "dropped_constraints" src/    # snapshot section gone from serializer/loader/capture
```

### Changes Required
**See `design.md` Appendix B (retirement grep targets) and D3 (within-v3 removal). Do NOT touch the kept generation-halt at `constraint_lowering.py:481` (explicit non-goal).**

- [x] **Delete** (Appendix B, grep-verifiable): the render/serialize half of `constraint_report.py` (render + `manifest_to_records`/`manifest_from_records`, the two blanket warnings), `extractor.py`'s `report_dropped_constraints`, `pipeline_builder.py`'s call site, `snapshot_context.py`'s replay + ctx pass-through, `serializer.py`'s `dropped_constraints` emission, `loader.py`'s `dropped_constraints` read, `capture.py`'s pass-through, the `constraint_manifest` ctx field (`pipeline_context.py`). **Deviation (documented, not a stop):** `collect_constraint_manifest` (the pure sweep) and `ConstraintManifestEntry`/`ConstraintKind`/`OwnerKind` are KEPT, not deleted — Phase 2's kept mapping test calls the sweep directly and would break if it were removed; only the report/render/snapshot-replay wiring around it retired.
- [x] **Re-anchor REQ-EXT-09 tests**: `TestReqExt09ConstraintDropDiagnostic` (catf_mfe span + unassessed count, wi014 eligible-catalog membership), the `item4_require` sentinel test (re-anchored to manifest kind counts, no report call), the wi014 manifest round-trip in `test_snapshot_contract.py` (re-anchored to live sweep + committed-snapshot catalog join). `TestConstraintRequireAndExclusion`'s other two tests and `TestConstraintDroppablePolicyParity` were unaffected (no report call) and needed no change. Deleted `tests/unit/test_constraint_report.py` entirely (its whole subject — render/serialize — no longer exists).
- [x] **D3 heterogeneous corpus:** re-captured `plant_values`/`fusion_tea` a second time (after the serializer stopped emitting the key) so those two omit it cleanly; the other 27 retain it as an ignored vestige — verified via a full re-capture + byte-identity check, then reverted the 27 (the key-removal touches every fresh capture, but only these two fixtures are meant to be re-captured).

### Validation
**Automated:**
- [x] The three grep-clean commands (`render_constraint_report`/`report_dropped_constraints`, `not executable`, `dropped_constraints`) return **zero** in `src/`.
- [x] `uv run pytest tests/conformance/test_extractor.py tests/conformance/test_snapshot_contract.py` → re-anchored family green.
- [x] `uv run pytest tests/` → 2329 passed / 23 skipped, no regressions; old snapshots still load.
- [x] Byte-identity re-verified: `plant_values`/`fusion_tea` are the only two committed snapshots without `dropped_constraints`.
- [x] `ruff check src/` clean; `mypy src/` 76 (baseline unchanged).

**What We Know Works After This Phase:**
The rival surface is gone, grep-clean holds, and the REQ-EXT-09 family reads the catalog. The migration (spec workstream 2) is complete in-repo.

---

## Phase 4: W3a — sysml-codegen docs flip + verification matrix

### Goal
Flip this repo's authoring guidance from "constraints are not executable" to teaching the executable profile + block list; add architecture coverage for the new phases; add verification-matrix rows under the register discipline (`design.md` Appendix A).

### Assumption Under Test
The doc surfaces in Appendix A are the complete in-repo set (verified surfaces), and the register-discipline recount (anchor the STATUS column, don't substring-match) reconciles the matrix against `grep -o 'REQ-[A-Z]*-[0-9]*'` over the reference docs.

### Changes Required
**See `design.md` Appendix A (sysml-codegen verified surfaces) and spec Docs requirements.**
- [ ] Flip `docs/architecture/modeling-assumptions.md:400` §8 → teach the executable profile + block list (invocation, conditional, temporal, unit conversion, real-valued equality) and the real-equality → **explicit two-inequality-band** idiom.
- [ ] Update cross-refs: `reference/01-extraction.md:20`, `reference/02-orchestration.md:40`, `verification-matrix.md:228`.
- [ ] Add/extend architecture reference docs: lowering phase, catalog, contracts, evaluator, study layer.
- [ ] `verification-matrix.md`: add rows for the new REQ families (constraint lowering, generation, catalog, contracts, study); **recount index family counts + STATUS from actual table rows** (memory `verification-matrix-drift-modes` — the index counts and missing REQ families are the real drift, not the summary block).

### Validation
- [ ] `grep -rn "not executable" docs/` → only historical/decision-record mentions remain; no authoring guidance still teaches the retired behavior.
- [ ] `grep -o 'REQ-[A-Z]*-[0-9]*' docs/architecture/reference/*.md | sort -u` cross-checks the matrix; every new REQ family has a row.
- [ ] Index family counts + STATUS recounted and consistent (not just the summary block).

**What We Know Works After This Phase:**
This repo's docs teach the built system. (agentic-mbse and teax docs land in S-MBSE / S-TEAX — Appendices A/B.)

---

## Phase 5: W5a — GENERATOR_MISMATCH seam disposition

### Goal
Dispose of the reserved-but-unreachable `GENERATOR_MISMATCH` diagnostic (`contracts/verify.py:24`): either wire a `generator_version` axis so a generator-version mismatch is detectable, or document it as an intentional reserved seam and remove the dead reachability expectation. Record the disposition either way (spec Small Seams).

### Changes Required
**See spec Known Requirements → Small recorded seams (GENERATOR_MISMATCH).**
- [ ] Inspect `contracts/verify.py:24` and its reachability expectation. Decide wire-vs-document.
- [ ] If document-and-remove: remove the dead expectation, add a one-line reserved-seam note (decision-record phrasing, not an instruction to future agents — capture-fidelity Law 3).
- [ ] Record the disposition in the run report.

### Validation
- [ ] The chosen disposition is recorded; if wired, a test exercises the new axis; if documented, the dead expectation is gone and no test asserts unreachable reachability.

**What We Know Works After This Phase:**
The in-repo seam (W5a) is swept. The teax seams (W5b loader seal, W5c tracking-key note) land in S-TEAX (Appendix B).

---

## Phase 6: Epic Success Criteria reconcile (final, after cross-repo sessions)

### Goal
Once S-CODEGEN, S-MBSE, S-TEAX, and S-FUSION have all landed, check the epic's top-level Success Criteria and Item 14's boxes with evidence links, and write the Item 14 close-out report. This phase is resumable — it collects evidence from the four sessions' reports.

### Changes Required
- [ ] Reconcile the **epic** Success Criteria (`epic_constraint_execution.md:39-47`) — Acceptance, migration mapping, byte-identity, docs — each box traceable to a landed item or this item's evidence.
- [ ] Reconcile **Item 14's** boxes (`epic_constraint_execution.md`, Item 14 entry): migration mapping green + grep-clean; IFE grid 100% match + hand rule deleted; docs in all three repos.
- [ ] Write the close-out report `.project/active/constraint-migration-acceptance/run-report.md`: W1 byte-identity result, W2 mapping-test + grep-clean, W3 per-repo doc deltas, **W4 acceptance table** (see Appendix C — committed under fusion-tea's harness dir; link it here), W5 seam dispositions, the prepare-once benchmark, and the recorded **naming-divergence note** (concept "source record" per-usage vs landed `ConstraintCatalogSourceRecord` per-definition — `design.md#core-concept`, the boxed decision: invariant **met as written**, no amendment).
## Appendix B — S-TEAX brief: teax docs + loader seal wiring + tracking-key note (W3c/W5b/W5c)

**Repo:** `~/1cfe/teax` · **Runs:** parallel to S-CODEGEN, but **W5b must land before S-FUSION (W4)** · **License:** not needed for docs; W5b wiring exercised for real in S-FUSION.

**W5b — teax loader seal-verification wiring (precondition of W4, NTH2):**
- [ ] Wire the loader to `verify_package(dir, name, runtime_version, strict)` (signature fixed by Item 9): load-by-declared-name, inject the runtime marker, choose strict. This is the mechanical Item 10/14 change Item 9 named.
- [ ] It is exercised for real when S-FUSION's acceptance loads the sealed IFE package through teax — so it **must land before W4 runs**.
- [ ] Validation: a sealed IFE package loads through teax with seal verification on; a tampered artifact / unhashed extra file fails with a named diagnostic (Item 9 behavior).

**W3c — teax evaluator + study-layer docs (design-best-guess — confirm file set with access):**
- [ ] Document the evaluator and study-layer surfaces Items 10–12 added.
- [ ] No teax doc still describes the retired behavior.

**W5c — tracking-key correlation note:**
- [ ] Document that a `tracking_key` correlates a logical constraint across model versions by **name only** — names correlate, never equate across fingerprint boundaries (concept Vocabulary, line 209).

**Report back:** files touched, W5b wiring confirmation, for the Phase-6 reconcile.

---

## Appendix C — S-FUSION brief: IFE acceptance + prepare-once benchmark (W4)
**Deviation:** kept `collect_constraint_manifest`/`ConstraintManifestEntry`/`ConstraintKind`/`OwnerKind` alive (design's Appendix B literally named `collect_constraint_manifest` as a deletion target, but Phase 2's kept mapping test depends on calling it directly — deleting it would break the very proof Phase 3's retirement is supposed to be authorized by). Recorded as a plan/design inconsistency resolved in favor of the kept test's requirement.

### Phase 4 Completion
### Phase 5 Completion
### Phase 6 Completion

---

**Status:** Draft → In Progress → Complete
