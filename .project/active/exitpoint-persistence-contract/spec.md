# Spec: ExitPoint Persistence Contract for JSON-Native Values

**Status:** Implementation Complete (audit and pre-PR fusion re-verification pending)
**Owner:** Reid W
**Created:** 2026-07-10 12:48 PDT
**Complexity:** LOW (code) — the contract decision is already settled by the
concept and confirmed by spike; what remains is a small, well-bounded change
plus tests and docs.
**Branch:** exitpoint-persistence-contract

---

## Problem

The framework routes bare scalars (multi-output decomposition) and wrapped
scalars (`RootModel[T]` single-output) between modules, but the output
boundary can only persist named Pydantic models. A `float` the framework
itself placed on a channel cannot leave the pipeline: validation rejects the
exit binding pre-run (T-1, `pipeline_validator.py:319`), and a hand-registered
handler crashes in the stock serializer (T-2, `writers.py:13-27`,
`'float' object has no attribute 'model_dump'`).

Every consumer of a sysml-codegen-generated package carries the same
workaround — a hand-built router teaching TEAx to write its own channel
values (`fusion-tea/exploration/ife_e2e/run_anchors.py:119-132`). That is
framework knowledge duplicated per harness, and it defeats the goal of
generated packages running with no hand-written glue.

The contract fix is decided (concept) and proven sufficient (spike,
2026-07-10): eight JSON-native default handler names in
`create_default_router()`. All 13 fusion-tea anchor checks pass with the
workaround deleted; artifacts byte-identical; zero new test failures.
This item implements it properly: code, tests, and documentation.

## Success Criteria

- [x] A pipeline with a single-output `RootModel[float]` module executes with
      `custom_schema_types=[Float]`, **no explicit router**, and writes the
      bare scalar JSON value.
- [x] A pipeline with a multi-output model containing plain `float`, `int`,
      `str`, and `bool` fields executes with no explicit router and writes
      each channel as its natural JSON value.
- [x] `create_default_router()` tests cover all eight names with exact JSON
      payload bytes (`1.25`, `2`, `"value"`, `true`) and `.json` extension
      enforcement; wrapped and bare forms of the same value produce
      byte-identical files.
- [x] Falsy scalars (`0.0`, `0`, `""`, `False`) persist as artifacts
      (`produced: true`), not skipped.
- [x] An ExitPoint type with no registered handler still fails validation
      **before any module runs**, with the existing actionable error —
      proven by an executor-level test with an observable module side
      effect, not only a router unit test.
- [x] An ExitPoint binding that mislabels its channel (e.g., a `float`
      channel declared `bool`, or wrapped/bare confusion in either
      direction) fails validation before any module runs.
- [x] Existing `BaseModel`/`RootModel` output tests and the battery demo
      remain green with byte-identical serialized content.
- [x] fusion-tea can delete the router construction and `WriteHandler` lambda
      from `run_anchors.py` and reproduce anchor outputs with only
      `registry=` + `custom_schema_types=` (spike-proven; **re-verified at
      pre-PR 2026-07-12** against the final working tree: workaround-free run
      passes all 13 anchors, 7 exit artifacts byte-identical per run,
      manifests identical modulo run id).
- [x] Documentation states the persistence contract: which types persist by
      default, which need registration, and the known boundaries (explicit
      routers, `None`, entry side).

## Known Requirements

Contract behavior (settled in the concept, restated here as the implementable
requirements):

- **[NEED]** `create_default_router()` registers `float`, `int`, `str`,
  `bool` with a writer that accepts JSON-native payloads
  (`write_json_payload`), and `RootModel[float]`, `RootModel[int]`,
  `RootModel[str]`, `RootModel[bool]` with the model writer
  (`write_json_model`). Both writers already exist; no new code paths.
- **[HARD]** The written representation is the natural JSON value
  (`float → 1.25`, `str → "value"`, `bool → true`); whether the value
  traveled wrapped or bare is invisible on disk. Pydantic model
  serialization is unchanged.
- **[HARD]** The wrapped handler names are the deterministic Pydantic class
  names (`RootModel[float].__name__ == "RootModel[float]"`), so they can be
  hard-coded.
- **[HARD]** An explicitly supplied `output_router` replaces the defaults
  entirely, and `include_builtins=False` routers exclude the primitive
  handlers — primitives count as built-ins. (Existing semantics, unchanged;
  must be documented because "primitives just work" is false there.)
- **[HARD]** `custom_schema_types` continues to accept only `BaseModel`
  subclasses; transitional generated packages that still pass `Float` etc.
  keep working (they re-register the same handler — the spike ran this way).
- **[NEED]** Fail-fast validation is not weakened: unknown exit type names
  (`bytes`, `Decimal`, any unregistered domain name) still raise
  `PipelineValidationError` pre-run. No duck-typed fallback writer.
- **[NEED]** Falsy scalar payloads persist; the produced/not-produced check
  is `payload is None`, never truthiness. (`None` itself continues to mean
  "not produced" — a legitimately-`None` `Optional` field records
  `produced: false` rather than writing `null`.)
- **[NEED]** Convenience registration never silently degrades a framework
  default: `create_output_router_with_json_schemas` registers a custom name
  only if no default handler already holds it (uniformly, for all default
  names — a custom type named `float` must not swap the scalar writer out
  and resurrect T-2). `register_handler()` remains the deliberate override.
  (Amended per design review M1 — supersedes the earlier reserved-name
  rejection idea, which sat in the wrong subsystem and broke the
  explicit-router escape hatch.)
- **[NEED]** An ExitPoint binding whose declared type differs from its
  producer channel's resolvable type fails validation before execution,
  with an error naming the binding, both types, and the fix. Channels whose
  producer type cannot be resolved are skipped, not guessed. (Added per
  design review C1, owner-approved: with all eight scalar handlers
  registered, a mislabeled scalar binding would otherwise succeed and write
  a falsely labelled manifest. Supersedes the concept's "trust the declared
  name — explicitly unchanged" edge case.)
- **[INFERRED]** An in-repo end-to-end pipeline fixture exercises both
  channel shape *categories* through `execute_pipeline` with no router:
  all four scalars as bare decomposed fields, plus one wrapped
  (`RootModel[float]`) single-output channel. The full eight-name matrix is
  covered at the router-unit level instead of e2e because wrapped
  `int`/`str`/`bool` traverse code paths identical to wrapped `float` at
  every stage (the introspector branches only on `is_rootmodel`; the
  executor and writer never branch on the type parameter). (Amended per
  design review M5, owner-approved — the earlier "all four scalars in both
  shapes" wording was imprecise.) This complements, not replaces, the
  cross-repo fusion-tea check.

Documentation (explicitly in scope per the request):

- **[NEED]** `docs/rootmodel-and-primitives.md` gains an output-persistence
  section alongside the existing channel-type rules: the contract statement
  (default JSON-native persistence vs. `custom_schema_types` registration vs.
  explicit routers), the YAML exit-binding shapes for wrapped and bare
  scalars, and the boundaries — explicit/`include_builtins=False` routers
  have no primitive handlers; `None` records not-produced; the default
  persists exit only (EntryPoint still cannot load a bare scalar).
- **[NEED]** `CLAUDE.md` custom-schema section updated: error 4's solution
  ("ExitPoint output type has no registered write handler") distinguishes
  JSON-native names (never register — framework default) from domain names
  (register via `custom_schema_types`); the custom-schema requirements note
  the eight reserved names if the collision guard lands.

## Non-Goals

- `list`/`dict` channel values — JSON-native too, but a separate follow-up;
  this contract covers the four scalars and their `RootModel` wrappers only.
- Arbitrary object serialization (`bytes`, `Decimal`, …) — explicit handlers.
- EntryPoint loading of scalars; the boundary stays exit-only for now.
- Changing channel representation, multi-output decomposition, exit
  filenames, result aggregation, or explicit-router replacement semantics.
- The sysml-codegen cleanup (dropping `Float` from `CUSTOM_SCHEMA_TYPES`,
  removing `_collect_exit_point_primitive_types()`) — separate ticket in that
  repo, scoped to exit-only per the concept's handoff caveat.
- Landing the fusion-tea workaround deletion — happens in fusion-tea after
  this ships; this item only guarantees (and re-verifies) that it works.

## Open Questions / Deferred to design

All resolved in design rev 2 (see `design.md` and `design-review.md`
Resolutions):

- ~~Constant public or private?~~ Private (`_DEFAULT_SCALAR_TYPE_NAMES`) —
  no runtime consumer exists (review m1).
- ~~Where does the collision guard live?~~ Nowhere — replaced by defaults-win
  composition in `create_output_router_with_json_schemas` (review M1).
- ~~Doc placement; does the concept example graduate?~~ Extend
  `docs/rootmodel-and-primitives.md` + surgical `CLAUDE.md` edits; the
  heater example stays a concept artifact (design D5/D6).

---

## Related Artifacts

- **Backlog ticket:** `.project/backlog/teax-primitive-output-contract.md`
- **Concept:** `.project/concepts/exitpoint-persistence-contract.md`
  (contract, principles, rejected alternatives, decision trail)
- **Concept example:** `.project/concepts/exitpoint-persistence-contract-example/`
  (heater_tea end-state walkthrough)
- **Spike:** `.project/active/spike-exitpoint-default-primitives/findings.md`
  (sufficiency proof, probe patch, reproduction steps)
- **Docs to update:** `docs/rootmodel-and-primitives.md`, `CLAUDE.md`
- **Design:** `.project/active/exitpoint-persistence-contract/design.md`
- **Design review:** `.project/active/exitpoint-persistence-contract/design-review.md`
  (resolutions recorded; C1 folded in, M5 resolved by amending this spec)

---

**Next Steps:** After approval, proceed to `/_my_design` (or `/_my_spec_review`
first if you want the adversarial pass — the contract is load-bearing even
though the diff is small).
