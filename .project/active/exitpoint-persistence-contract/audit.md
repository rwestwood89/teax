# Audit: ExitPoint Persistence Contract

**Verdict:** Certify
**Audited:** 2026-07-12
**Branch:** exitpoint-persistence-contract
**Commit:** c9e1e85

---

## Summary

The implementation delivers the contract as designed: eight JSON-native default
handlers, defaults-win composition, and a pre-run cross-check that keeps the
widened registry honest. All three phases are complete, every spec success
criterion in this item's scope is met, and the code follows the design's D1–D6
decisions without silent deviation. The one open success criterion (fusion-tea
workaround deletion) is explicitly deferred to pre-PR by the spec itself, not a
gap. Full suite: 208 passed, 4 pre-existing environmental failures unrelated to
this change.

## Findings

### Plan completion

All three phases verified complete.

- **Phase 1 (default handlers).** Eight handlers registered in
  `create_default_router()` — four bare scalars → `write_json_payload`, four
  `RootModel[...]` → `write_json_model` (`output_router.py:283-309`). Defaults
  preserved in the convenience helper via a one-condition `has_handler` guard
  (`output_router.py:381-383`). Tests cover exact bytes, wrapped/bare identity,
  falsy values, extension enforcement, and override policy
  (`test_output_router.py:243-369`).
- **Phase 2 (exit type validation).** Channel-type map passed into
  `_validate_exit_module`; cross-check extracted to `_validate_exit_output_type`
  (`pipeline_validator.py:348-385`). Executor-level fail-fast test proves no
  module runs on an unknown exit type (`test_pipeline_validator_exit.py:187-226`,
  `run_count == 0`).
- **Phase 3 (e2e + docs).** Defaults-only pipeline fixture and e2e asserting
  exact bytes and `produced` flags (`test_toy_pipeline.py:206-238`); docs and
  `CLAUDE.md` updated; battery integration fixture corrected. No placeholder
  code or TODOs.

### Spec conformance

- **SC1 — single-output `RootModel[float]`, no router, bare scalar written.**
  Met. `test_toy_pipeline.py:206-238` runs with no `output_router`; `wrapped.json == "20.0"`.
- **SC2 — multi-output `float`/`int`/`str`/`bool`, natural JSON.** Met. Same e2e:
  `2.5`, `10`, `"value:10"`, `true`.
- **SC3 — all eight names, exact bytes, `.json` enforcement, wrapped/bare byte
  identity.** Met. `test_output_router.py:243-294`.
- **SC4 — falsy scalars persist with `produced: true`.** Met.
  `test_default_router_persists_falsy_scalars` covers `0.0`, `0`, `""`, `False`.
- **SC5 — unknown exit type fails before any module runs, executor-level.** Met.
  `test_pipeline_validator_exit.py:187-226` asserts `run_count == 0`.
- **SC6 — mislabeled binding fails pre-run.** Met.
  `test_exit_binding_rejects_resolvable_type_mismatch` covers `float`-as-`bool`,
  `RootModel[float]`-as-`float`, and `float`-as-`RootModel[float]`.
- **SC7 — existing tests + battery demo green, byte-identical.** Met. 208 passed.
  Battery `demo_linear_alt.yaml` exit bindings corrected from bare types to their
  true `RootModel[...]` producers — D3 caught a genuinely mislabeled fixture; the
  fix declares the real type rather than weakening the check (design "watch"
  item honored).
- **SC8 — fusion-tea workaround deletion re-verified.** Open `[ ]` — correctly.
  The spec assigns this to pre-PR against the final commit; not in this item's
  audit scope.
- **SC-docs — contract documented.** Met. `docs/rootmodel-and-primitives.md`
  gains "Persisting Results at the ExitPoint" with the contract, YAML shapes, and
  all five boundaries; `CLAUDE.md` error 4 split plus the new error-5 entry.

Requirements (`[HARD]`/`[NEED]`/`[INFERRED]`): all met. Non-goals respected — no
`list`/`dict` handlers, no EntryPoint scalar loading, no sysml-codegen cleanup,
no fusion-tea landing; channel representation and filenames unchanged.

### Design conformance

Implementation follows the design.

- **D1** eight names / two existing writers in `create_default_router()` — as
  specified, wrapped names derived from `_DEFAULT_SCALAR_TYPE_NAMES`.
- **D2** defaults win in `create_output_router_with_json_schemas` — verified a
  custom `"float"` does not swap the handler
  (`test_custom_schema_convenience_registration_preserves_default_handlers`).
- **D3** cross-check with skip-if-unresolvable — confirmed it genuinely engages
  for real `MultiOutput` bare-scalar channels: the introspector maps
  `floating→float, integer→int, text→str, flag→bool`, so a mislabel resolves and
  raises rather than being skipped.
- **D4** `_DEFAULT_SCALAR_TYPE_NAMES` is private. **D5** new
  `toy_scalar_module.py`, existing toys untouched. **D6** docs extended, not
  created; prose says "four supported scalar types," never "all JSON-native."

All required invariants verified via the test suite.

### Code integrity

No issues found. `create_default_router()` uses clean dict comprehensions; the
D2 change is the intended single `has_handler` condition; D3 is a focused helper
with an actionable error hint. The skip-if-unresolvable branch
(`pipeline_validator.py:349-354`) is not a silent fallback — it is the designed,
documented scope limit (the check narrows looseness, it does not invent type
resolution), and unknown handlers still raise loudly one check earlier
(`pipeline_validator.py:338`). No broad excepts, no backwards-compat shims, no
optional-parameter papering.

---

## Certification

Checked and verified: all three plan phases; spec success criteria SC1–SC7 and
the documentation criterion; design decisions D1–D6 and the required invariants;
code integrity of the two touched framework files. Ran the three touched test
files (53 pass), the full simkit suite (139 pass, 4 pre-existing env failures),
and the battery demo suite (69 pass) — 208 functional passes total. Confirmed
the 4 failures are the untouched `test_no_battery_deps.py` tests that hard-code
`/home/reid/teax` (this checkout is `/home/reid/1cfe/teax`).

SC8 (fusion-tea cross-repo reproduction) is left open by design — it belongs to
pre-PR against the final commit.

**Not checked:** The cross-repo fusion-tea anchor reproduction (deferred to
pre-PR per spec, and requires the fusion-tea checkout which is not present). Byte
identity against pre-change battery artifacts was verified only through the
passing battery suite, not by diffing on-disk artifacts from a main-branch run.
Behavior under an explicit `include_builtins=False` router was verified by unit
test, not through a full `execute_pipeline` run.
