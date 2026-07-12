# Design: ExitPoint Persistence Contract for JSON-Native Values

**Status:** Implemented (rev 2 — audit pending)
**Owner:** Reid W
**Created:** 2026-07-10 12:55 PDT
**Revised:** 2026-07-10 (resolutions in `design-review.md`; C1 folded in per owner, M5 resolved by spec amendment)
**Branch:** exitpoint-persistence-contract @ c9e1e85

## Overview

Make TEAx's default output path persist the four supported scalar types —
`float`, `int`, `str`, `bool` — and their `RootModel` wrappers with no
consumer registration, so generated packages run with only `registry=` +
`custom_schema_types=`. Two guardrails ship with it: convenience
registration never silently replaces a framework default handler, and an
ExitPoint binding's declared type is cross-checked against its producer
channel's type before execution. This is deliberately **not** closure over
all JSON-native values: `list`, `dict`, and `None` are excluded.

## Related Artifacts

- **Spec:** `.project/active/exitpoint-persistence-contract/spec.md`
- **Design review:** `.project/active/exitpoint-persistence-contract/design-review.md`
  (rev 2 incorporates its resolutions; C1 → fold in, M1 → D2 replaced,
  M5 → spec amended)
- **Concept:** `.project/concepts/exitpoint-persistence-contract.md`
- **Spike:** `.project/active/spike-exitpoint-default-primitives/findings.md`
  — proves D1 for wrapped/bare `float` through a generated pipeline
  (13/13 anchors, byte-identical artifacts) and all eight names at the
  router unit level. Probe patch: `output_router_eight_handlers.patch`.
- **Backlog ticket:** `.project/backlog/teax-primitive-output-contract.md`

## Research Findings

- **Both writers exist and behave as needed.** `write_json_payload()`
  (`simkit/io/writers.py:31-49`) handles non-BaseModel payloads *and*
  BaseModels (via `model_dump`, `writers.py:43-44`); `write_json_model()`
  (`writers.py:13-27`) handles `RootModel`. Scalar bytes identical between
  them — spike-verified for all eight names including falsy values.
- **Two router-creation paths, one root.** `execute_pipeline` builds via
  `create_output_router_with_json_schemas(include_builtins=True)`
  (`simkit/core/pipeline.py:155-166`), which starts from
  `create_default_router()`; the executor fallback
  (`pipeline_executor.py:95`) also calls it. One edit covers both.
- **The helper currently overwrites defaults.** Its registration loop
  replaces any existing handler under a custom name
  (`output_router.py:338-341`). Today that is byte-invisible — all three
  builtin writers produce output identical to `write_json_model`, which is
  all the helper registers — but with scalar defaults present, an overwrite
  of `"float"` would swap `write_json_payload` for `write_json_model` and
  resurrect T-2. This is the collision surface that matters; it is a
  router-composition concern, not a schema-registry concern.
- **Schema-registry guards hit the wrong callers.** `_build_schema_type_registry`
  runs at `pipeline.py:147`, *before* router selection (`pipeline.py:155-170`),
  so any name policy there applies to explicit-router and entry-only callers.
  (This killed rev 1's D2 — see review M1.)
- **The validator already knows producer channel types.**
  `_collect_channel_types()` maps channel → real type object from registry
  descriptors, and from the schema registry for entry channels
  (`pipeline_validator.py:110-155`); `_unwrap_optional()` exists
  (`pipeline_validator.py:157+`). `_validate_exit_module()` today checks only
  handler existence and filename shape (`pipeline_validator.py:285-328`) —
  it never compares the declared type to the producer's. Exit bindings
  cannot be field references (`pipeline_validator.py:299-304`), so the
  cross-check is a straight name comparison.
- **E2E pattern to follow.** `simkit/tests/test_toy_pipeline.py` +
  `tests/core/toy_modules.py` + `tests/fixtures/pipeline_configs/*.yaml`.
  Today every toy e2e passes an explicit router
  (`test_toy_pipeline.py:35-41`); no in-repo pipeline exercises bare
  `int`/`str`/`bool` exits or the defaults-only path.
- **Pydantic naming pin.** `RootModel[float].__name__ == "RootModel[float]"`
  — load-bearing for the hard-coded wrapped names (class *identity* is no
  longer load-bearing anywhere in rev 2).

## Core Concept

This is a boundary-closure change over a deliberately small set: the
persistence layer is a name-keyed handler registry consulted by fail-fast
validation, and the framework already owns two writers that correctly
serialize the four scalar types its channel layer sanctions. The design is:
**put the eight framework-owned names into the default registry contents,
and make the name-trusting registry safe to widen** — composition never
silently replaces a default handler, and the validator cross-checks each
exit binding's declared name against the type its producer actually puts on
the channel. Proof at three levels: handler unit tests, an in-repo
defaults-only e2e pipeline, the cross-repo fusion-tea reproduction.
Serialization knowledge lands where the concept's Principle 2 puts it: the
framework writes what it sanctions on channels; domain packages declare
their named schemas; harnesses register nothing.

The cross-check is what makes widening the registry honest. With three
handler names, a mislabeled scalar binding failed by accident (no handler);
with eleven, it would succeed and write a falsely labelled manifest. The
validator already computes producer types for field-reference validation —
the exit module is simply the one consumer of that map that never used it.

## Key Bets

- **B1.** The interior shape set that codegen emits stays "four scalars +
  named models" for the life of this contract. *If false (e.g., codegen
  emits `list[float]` fields) → the boundary reopens; the fix is more
  default names on this same mechanism, not a redesign.*
- **B2.** No external caller relies on `create_output_router_with_json_schemas`
  *overwriting* a default handler with different behavior. *If false → their
  output format changes silently to the default's; escape hatch is
  `register_handler()` or a hand-built router, both untouched. Verified
  byte-invisible for every current in-tree and known cross-repo caller.*
- **B3.** Existing pipelines' exit bindings are truthfully typed. *If false →
  the new cross-check rejects them loudly at validation with an error naming
  the binding, the declared type, and the producer type — a YAML fix, not a
  breakage mystery. In-tree fixtures and generated fusion-tea YAML are
  verified truthful; the bet is about unknown external YAML.*

## Key Decisions

- **D1. Eight names, two existing writers, in `create_default_router()`.**
  Bare names → `write_json_payload`; wrapped names → `write_json_model`.
  Exactly the spike patch. *Rejected: a new dedicated primitive writer
  (nothing to add); validator changes for T-1 (none needed — spike-confirmed).*
- **D2. Defaults win at the composition boundary.**
  `create_output_router_with_json_schemas` registers a custom name only if
  no default handler already holds it — uniformly, for all default names,
  not a special-cased scalar list. `register_handler()` remains the
  deliberate, documented override. *Rejected: rev 1's reserved-name guard in
  `_build_schema_type_registry` (wrong subsystem — runs before router
  selection, so it hit explicit-router and entry-only callers, and its
  "explicit router escapes it" claim was false; also required a Pydantic
  class-identity policy). Rejected: keeping silent overwrite (a custom type
  named `float` would downgrade the handler and resurrect T-2).*
- **D3. Exit bindings are cross-checked against producer channel types.**
  `_validate_exit_module` compares each binding's `type_name` with the
  producer's type from the existing channel-type map (Optional-unwrapped),
  and raises pre-run on mismatch. Channels whose producer type is
  unresolvable (entry channels with no registered schema) are skipped —
  the check narrows looseness, it does not invent resolution. *Rejected:
  payload inspection at write time (too late — violates fail-fast, and the
  generic writer accepts almost anything). Rejected: keeping the
  trust-the-name looseness (concept's original stance) — D1 turns loud
  scalar mislabels into silent falsely-labelled artifacts, so the concept's
  "explicitly unchanged" edge case is superseded per review C1 + owner
  decision.*
- **D4. The scalar-name tuple is private** (`_DEFAULT_SCALAR_TYPE_NAMES` in
  `output_router.py`); wrapped names derived from it. *Rejected: public API
  (rev 1) — with the identity guard gone there is no runtime consumer; docs
  are not one, and the sysml-codegen cleanup is unproven. Promote if a real
  importer appears.*
- **D5. New toy scalar module + defaults-only e2e fixture; existing toys
  untouched.** A multi-output toy with `float`/`int`/`str`/`bool` fields and
  a pipeline persisting all four bare plus one `RootModel[float]` channel,
  executed with **no router argument** — shape *categories* end-to-end, the
  full 8-name matrix at router level. (Spec's "both shapes" wording amended
  accordingly — review M5, owner-approved: wrapped `int`/`str`/`bool`
  traverse identical code paths to wrapped `float`; the type parameter never
  branches.) *Rejected: full-matrix e2e (three more toy classes proving
  proven branches); widening `ToyMultiOutput` (churns existing fixtures);
  promoting the concept's heater example (illustration with fabricated
  outputs; stays a concept artifact).*
- **D6. Docs: extend, don't create.** `docs/rootmodel-and-primitives.md`
  gains a final "Persisting results at the ExitPoint" section;
  `CLAUDE.md`'s custom-schema error table gets the split solution for
  error 4. Prose says "the four supported scalar types," never "all
  JSON-native values" (review M2). *Rejected: a standalone doc (channel
  rules and persistence rules are one contract).*

## Architecture

All changes live in the persistence layer, its composition helper, and the
exit-validation step; the channel layer (executor, introspector) is
untouched.

```
execute_pipeline(custom_schema_types=[...])          (pipeline.py:143-170)
  ├─ _build_schema_type_registry(types)              (unchanged)
  ├─ create_output_router_with_json_schemas(names)   ← D2: defaults win
  │    └─ create_default_router()                    ← D1: +8 scalar names
  └─ PipelineValidator
       ├─ has_handler(type_name)                     (unchanged, pipeline_validator.py:319)
       └─ exit type ↔ channel-type map cross-check   ← D3 (new, same function)
            └─ OutputRouter.write_outputs            (unchanged)
                 ├─ write_json_payload  ← float/int/str/bool
                 └─ write_json_model    ← RootModel[…] + models
```

Runtime data flow at the exit is unchanged: the router looks up the handler
by declared name, checks the `.json` extension, writes, records the manifest
artifact. The behavioral deltas are all pre-run: which names the default
registry knows (D1), which names composition may claim (D2), and whether the
declared name must match the producer (D3).

## Required Invariants

- `create_default_router().has_handler(n)` for all eight scalar names and
  the three existing builtin schema names.
- Writing `1.25` under `"float"` and `RootModel[float](1.25)` under
  `"RootModel[float]"` produces byte-identical files containing `1.25`;
  same for the other three types.
- Falsy payloads (`0.0`, `0`, `""`, `False`) persist with `produced: true`;
  `None` still records `produced: false` (check stays `payload is None`).
- An ExitPoint name with no handler raises `PipelineValidationError` before
  any module runs — proven by an executor-level test, not only a router
  unit test (review M3).
- An exit binding whose declared type differs from its producer channel's
  resolvable type raises `PipelineValidationError` pre-run; unresolvable
  producer types are skipped, never guessed (D3).
- `create_output_router_with_json_schemas` never changes the handler of a
  name `create_default_router()` supplies; `register_handler()` still
  replaces unconditionally (D2).
- `execute_pipeline(output_router=r)` uses `r` verbatim.
  `include_builtins=False` routers get no default handlers *automatically*;
  a caller may still register wrapped scalar names explicitly (review m2).
- `custom_schema_types=[RootModel[float], …]` (transitional generated
  packages) works unchanged — the wrapped name is preserved as the default,
  which registers the same writer anyway.
- `RootModel[float].__name__ == "RootModel[float]"` (pins the hard-coded
  wrapped names; class identity is deliberately not relied on).
- All existing simkit and battery-demo output tests pass with byte-identical
  serialized content.

## Component Overview

- **`simkit/io/output_router.py`** — `_DEFAULT_SCALAR_TYPE_NAMES` (private,
  D4); eight default handler entries in `create_default_router()` (D1);
  defaults-win registration loop in `create_output_router_with_json_schemas`
  (D2).
- **`simkit/core/pipeline_validator.py`** — exit-binding type cross-check in
  `_validate_exit_module`, consuming the existing channel-type map with
  `_unwrap_optional` (D3).
- **`simkit/tests/io/test_output_router.py`** — handler existence, exact
  payload bytes for all eight names, wrapped/bare byte identity, falsy
  persistence, extension check, unknown-name error, defaults-win behavior
  (scalar and builtin names), `include_builtins=False` + explicit wrapped
  registration.
- **`simkit/tests/core/`** (validator/executor test homes) — executor-level
  fail-fast test: unknown exit type ⇒ `PipelineValidationError` and an
  observable module side effect proves nothing ran (M3); cross-check
  accept/reject matrix: truthful bindings pass; `float`-as-`bool`,
  `RootModel[float]`-as-`float`, and `float`-as-`RootModel[float]`
  mismatches fail pre-run; unresolvable-producer skip.
- **`simkit/tests/core/toy_modules.py` + `tests/fixtures/pipeline_configs/`
  + `tests/test_toy_pipeline.py`** — scalar toy module, defaults-only
  pipeline fixture, e2e asserting file bytes and manifest `produced` flags
  (D5).
- **`docs/rootmodel-and-primitives.md`** — "Persisting results at the
  ExitPoint" section: contract statement (four scalar types + wrappers by
  default; domain schemas via `custom_schema_types`; other formats via
  explicit router), exit-binding YAML for both shapes, and the boundaries:
  explicit routers own their handler set; `None` → not-produced;
  exit-only (EntryPoint still cannot load a bare scalar); `list`/`dict`
  excluded; declared exit types must match producer types.
- **`CLAUDE.md`** — error 4 solution split (scalar names: never register —
  framework default; domain names: `custom_schema_types`); one bullet on the
  exit type cross-check error.

## Non-Goals

Per spec: `list`/`dict` channel values; arbitrary object serialization;
EntryPoint scalar loading; changes to channel representation, decomposition,
filenames, aggregation, or explicit-router replacement semantics; the
sysml-codegen cleanup ticket; landing fusion-tea's workaround deletion
(re-verified here, landed there). D3 does not attempt to resolve types the
validator cannot already resolve.

## Implementation Notes

- The default-router edit should match the spike patch
  (`output_router_eight_handlers.patch`) minus the SPIKE comment; derive
  wrapped names: `f"RootModel[{n}]" for n in _DEFAULT_SCALAR_TYPE_NAMES`.
- D2 is a one-condition change in the helper's registration loop
  (`output_router.py:338-341`): skip names the freshly built default set
  already holds. When `include_builtins=False` there are no defaults to
  preserve — every listed name registers.
- D3 sits inside `_validate_exit_module`; it needs the channel-type map,
  which `validate()` already builds for input validation — pass it in or
  hoist the call. Compare via `getattr(t, "__name__", None)` after
  `_unwrap_optional`; a producer type with no `__name__` counts as
  unresolvable (skip). Error message: binding key, declared name, producer
  name, and the fix ("declare the producer's type").
- Guard/cross-check error wording follows the existing
  `PipelineValidationError(details={...})` style with a `hint` key
  (`pipeline_validator.py:320-328`).
- The e2e fixture needs an entry input JSON; follow
  `tests/fixtures/toy_input.json` + `toy_linear.yaml` conventions.
- CLAUDE.md is generated guidance for agents — surgical edits only.

## Potential Risks

- **B3 exposure: external YAML with mislabeled exit bindings breaks on
  upgrade.** Intentional (that YAML was producing falsely labelled
  artifacts), loud, and self-explaining via the error message. In-tree and
  fusion-tea YAML verified truthful; note it in the changelog line.
- **B2 exposure: an unknown caller wanted the helper's overwrite behavior.**
  No such caller exists in-tree or in fusion-tea; the override path
  (`register_handler`) is documented in the same doc section.
- **Doc drift** — the docs section is the single normative statement;
  concept and CLAUDE.md point at it rather than restating details.

## Integration Strategy

Drop-in for truthful pipelines: no signature changes, no YAML changes, no
consumer migration. Explicit-router users see identical behavior. The one
tightening is D3, which converts silent mislabels into pre-run errors.
After merge, fusion-tea deletes its workaround (their repo) and
sysml-codegen picks up the exit-only cleanup ticket per the concept handoff.

## Validation Approach

1. **Unit — router:** eight handlers exist; exact bytes; byte identity;
   falsy persistence; extension enforcement; unknown-name error;
   defaults-win (a custom `"float"` does not change the handler; a builtin
   name is preserved); `include_builtins=False` behavior; `__name__` pin.
2. **Unit — validator/executor:** fail-fast proof with module side effect
   (M3); D3 accept/reject matrix incl. wrapped/bare confusion both ways and
   unresolvable-skip.
3. **In-repo e2e:** defaults-only toy pipeline writes four bare scalars plus
   a wrapped channel; assert file bytes and manifest `produced` flags.
4. **Regression + cross-repo:** full `pytest` (4 pre-existing
   `test_no_battery_deps.py` env failures are known and unrelated); at
   pre-PR, re-run the spike's reproduction steps against the final commit:
   workaround-free fusion-tea run → 13/13 anchors, byte-identical artifacts.
   The spike proves D1's integration for `float`; D2/D3 evidence comes from
   the new unit tests, not the spike (review M4).

## Next-Stage Handoff

**Fixed:** the eight names and writer pairing (D1, spike-proven);
defaults-win composition (D2); the exit type cross-check with
skip-if-unresolvable semantics (D3, owner-approved scope addition);
private constant (D4); test levels and homes (D5); doc placement (D6).

**Open for implementation:** exact test names; error-message wording; how
the channel-type map reaches `_validate_exit_module` (parameter vs. hoist —
pick whatever the existing `validate()` flow makes cleaner); doc prose.

**Watch during implementation:** D3 against the battery-demo fixtures — if
any in-tree fixture fails the cross-check, that fixture was mislabeled;
fix the fixture, don't weaken the check.

---
Next Step: After approval → `/_my_implement` (single session; a separate
`/_my_plan` is overkill for this size).
