# Design Review: ExitPoint Persistence Contract for JSON-Native Values

**Design:** `.project/active/exitpoint-persistence-contract/design.md`  
**Spec:** `.project/active/exitpoint-persistence-contract/spec.md`  
**Review File:** `.project/active/exitpoint-persistence-contract/design-review.md`  
**Date:** 2026-07-10

---

## Fundamental Assessment

**Assessment: Concerns.** The eight default mappings are the right fundamental
solution. They reuse the existing router and writers, and the spike proves that
this small change fixes the observed fusion-tea failure with byte-identical
artifacts (`spike-exitpoint-default-primitives/findings.md:7-34`). There is no
reason to replace that core approach.

The design should still be revised before implementation. Most of the risk is
outside the spike-proven edit:

- the new collision policy reaches into EntryPoint and type resolution, despite
  being justified as persistence safety;
- the ExitPoint still does not verify that its declared type matches the type of
  the channel it writes, and adding all eight handlers turns some type mistakes
  into successful but falsely labelled artifacts;
- the public contract says "JSON-native" while intentionally excluding several
  JSON-native values and framework-producible channel shapes.

These are correctable without changing the eight-handler foundation, so the
recommendation is **Revise**, not Rework.

---

## Dimensional Review

### 1. Spec Compliance

**Assessment: Concerns**

The design covers the main persistence requirements: eight default handlers,
natural JSON representation, falsy values, explicit-router replacement, an
in-repo pipeline, regression checks, cross-repo reproduction, and documentation
(`design.md:100-146,169-216,271-286`).

Two acceptance items are not actually covered by the proposed tests:

1. The spec requires an unknown ExitPoint type to fail before any module runs
   (`spec.md:49-50,85-87`). The design places an "unknown-name error" in router
   unit tests (`design.md:199-201,275-278`). That exercises
   `OutputRouter.write_outputs`, not the validator's pre-execution behavior.
   Add a validator or executor test with an observable module side effect and
   prove the side effect never occurs.
2. The spec's inferred e2e requirement says all four scalars are exercised "in
   both shapes" (`spec.md:98-102`). D5 covers all four bare values but only one
   wrapped value, `RootModel[float]` (`design.md:132-139,205-208,279-280`). Either
   narrow the spec to match its earlier success criteria or run all eight names
   through `execute_pipeline`.

### 2. Pattern Consistency

**Assessment: Concerns**

Adding handlers in `create_default_router()` follows the existing pattern and
correctly covers both router-construction paths (`output_router.py:250-273`,
`pipeline.py:155-166`, `pipeline_executor.py:94-95`).

D2 does not follow the responsibility of the function it changes.
`_build_schema_type_registry()` supplies EntryPoint loading and field-reference
type resolution (`pipeline_executor.py:404-435`); it is not an output-router
policy hook. `execute_pipeline()` builds that registry before choosing an
explicit or automatic router (`pipeline.py:143-170`). A persistence-name guard
there therefore affects entry-only pipelines and explicit-router callers.

The existing helper also overwrites any default handler named in its string
list (`output_router.py:332-341`). D3 special-cases only four primitive names.
If the intended pattern is "convenience registration never silently replaces a
framework default," enforce that once for every existing handler and leave
`register_handler()` as the deliberate override.

### 3. Abstraction Quality

**Assessment: Fail**

The collision machinery is heavier than the demonstrated problem:

- D2 adds a global reserved namespace and Pydantic class-identity policy.
- D3 adds a second, different name policy at the router helper.
- D4 publishes a new API constant for a four-item tuple.

The spike proved only that the eight mappings are sufficient
(`findings.md:80-97`). It did not prove that either guard or a public constant is
needed.

The simplest safe policy is at the automatic router-composition boundary:
preserve handlers already supplied by `create_default_router()` instead of
silently replacing them. Direct `register_handler()` remains the explicit
override (`output_router.py:54-55`). If a global reserved type namespace is
truly wanted, it needs to be specified as a cross-pipeline rule rather than
introduced as an output persistence detail.

### 4. Duplication Avoidance

**Assessment: Pass**

The core change correctly reuses `write_json_payload()` and
`write_json_model()` and puts the mappings in the one default factory shared by
both execution paths (`design.md:30-40,100-104`). No new writer or router layer
is justified.

The design also sensibly adds a focused toy rather than mutating unrelated toy
fixtures. The remaining duplication risk is policy, not code volume: D2 and D3
would maintain two definitions of which default names may be registered.

### 5. Data Structure Clarity

**Assessment: Concerns**

The handlers are necessarily keyed by YAML type-name strings, but the design
does not close the loop between those strings and the producer's actual channel
type. `PipelineValidator` already builds a channel-to-type map
(`pipeline_validator.py:59-73,94-155`), while `_validate_exit_module()` checks
only destination shape and handler existence (`pipeline_validator.py:285-328`).

The proposed public name `JSON_NATIVE_TYPE_NAMES` is also inaccurate. It
contains only four scalar names. `list`, `dict`, and `None` are JSON-native, but
the spec excludes the first two and treats `None` as not produced
(`spec.md:88-91,119-123`). If a constant remains, call it something like
`DEFAULT_SCALAR_TYPE_NAMES`; keep it private unless a concrete runtime consumer
needs it.

### 6. Route Safety

**Assessment: Fail**

The design explicitly keeps the rule that the router trusts the ExitPoint's
declared type name (`design.md:164-167`). That becomes materially less safe when
all eight names are registered.

For example, a module output declared and validated as `float` can be bound at
the ExitPoint as `bool`. Today it fails accidentally because no `bool` handler
exists. After D1 it passes validation, `write_json_payload()` writes `1.25`, and
the manifest claims the artifact type is `bool`. The generic writer accepts any
JSON-serializable payload and even Pydantic models (`writers.py:31-48`), so the
handler does not catch the mismatch at write time.

Use the existing channel type map to compare each ExitPoint binding's
`type_name` with its provider type before execution. Add negative tests for bare
and wrapped scalar mismatches. If the project deliberately allows an ExitPoint
to relabel a channel, that must be an explicit contract decision; the current
design treats it as harmless pre-existing looseness, but D1 expands its effect.

### 7. Bets & Decisions Integrity

**Assessment: Fail**

The design has three bet problems:

1. **Hidden bet: ExitPoint YAML is always truthful.** The spike's generated YAML
   is truthful, so it cannot test the mismatch described above. This belief is
   load-bearing once all primitive handlers exist and should be removed through
   validation rather than accepted silently.
2. **B1 is broader than the evidence and its test does not pin the bet.** B1
   depends on `RootModel[T] is RootModel[T]` (`design.md:83-88`), but the listed
   invariant and test pin only `__name__` (`design.md:185,275-278`). The package
   supports unbounded `pydantic>=2.5` (`packages/teax-simkit/pyproject.toml:7`),
   while the spike used only 2.13.4. If identity policing remains, test identity
   for all four wrappers. Prefer removing this dependency by dropping the
   wrapped-name impostor guard; D3 already says wrapped re-registration uses the
   same handler and is harmless (`design.md:118-125`).
3. **B3's escape hatch is false.** It says an affected consumer can use an
   explicit router (`design.md:93-96`), but schema registry construction and D2
   run before the explicit router is selected (`pipeline.py:143-170`). An
   explicit router does not escape D2.

The spike also proves less than "no technical risk" (`design.md:297-299`). Its
generated pipeline covers wrapped and bare `float` only
(`findings.md:52-54`). `int`, `str`, and `bool` were exercised directly through
the router, and the spike explicitly says no generated pipeline covers them
(`findings.md:94-97,156-158`). The spike proves D1 for the observed integration;
it does not prove D2-D4 or B2.

### 8. Reader Comprehension

**Assessment: Concerns**

The document is otherwise clear: it leads with the small mechanism, separates
bets from decisions, and gives useful code and test locations.

The core label blocks an accurate mental model. "Every JSON-native channel
shape" (`design.md:10-14,64-74`) sounds closed, while the concept admits that
the framework can place `list[float]` and other annotations on channels
(`concept.md:65-74`), and the spec excludes list/dict/None behavior. B2 quietly
narrows the real contract to what codegen emits (`design.md:89-92`). State that
plainly in the overview: the default output path supports the four sanctioned
JSON scalar types and their `RootModel` wrappers. Do not call it closure over
all JSON-native or framework-producible values.

---

## Issues by Severity

### Critical

- **C1 — ExitPoint type declarations are not checked against provider types.**
  Adding all eight handlers makes scalar type-name mistakes pass validation and
  produce falsely typed manifests. Compare ExitPoint bindings with the existing
  channel type map before execution. — Route Safety / Data Structure Clarity

### Major

- **M1 — The reserved-name guard is in the wrong subsystem.** D2 applies
  persistence policy to EntryPoint/type-resolution registration and also breaks
  the claimed explicit-router escape hatch. Move collision handling to automatic
  router composition or explicitly specify and test a global reserved namespace.
  — Pattern Consistency / Abstraction Quality
- **M2 — The contract overclaims JSON-native closure.** Lists, dictionaries,
  `None`, and other framework-producible shapes are excluded. Rename the contract
  and constant around the four supported scalar types, or expand scope. — Reader
  Comprehension / Data Structure Clarity
- **M3 — Required fail-fast evidence is missing.** Add a validator/executor test
  proving an unknown ExitPoint handler prevents every module from running. An
  `OutputRouter.write_outputs` error test is not equivalent. — Spec Compliance
- **M4 — The spike is used to retire risks it did not test.** It proves the
  eight-handler happy path for generated float outputs, not collision semantics,
  the public constant, Pydantic identity across supported versions, or generated
  int/str/bool behavior. — Bets & Decisions Integrity
- **M5 — E2E shape coverage disagrees with the spec.** The spec asks for all
  four scalars in both forms; D5 runs all bare forms plus wrapped float only.
  Align the spec and design. — Spec Compliance

### Minor

- **m1 — The public constant is unjustified API surface.** Documentation is not
  a runtime consumer, and the sysml-codegen cleanup is explicitly unproven.
  Keep the tuple private unless a concrete downstream import is required. —
  Abstraction Quality
- **m2 — The `include_builtins=False` invariant is too absolute.** The helper
  can still add a wrapped primitive when the caller explicitly includes
  `"RootModel[float]"`. Say that primitives are not included automatically. —
  Data Structure Clarity
- **m3 — B1's proposed test checks the wrong property.** If class identity stays
  load-bearing, assert identity for all four wrappers, not only the generated
  class name. — Bets & Decisions Integrity

---

## Recommendations

1. Keep D1: add the eight default mappings exactly as spike-proven.
2. Add fail-fast ExitPoint source-type validation before relying on the broader
   default handler set.
3. Remove D2's global identity-based guard. At the automatic router boundary,
   preserve existing default handlers rather than overwriting them; reserve
   `register_handler()` for deliberate replacement.
4. Describe and name the feature as default JSON scalar persistence, not closure
   over all JSON-native channel values.
5. Add the two missing acceptance tests: unknown handler prevents execution, and
   the e2e shape matrix agreed with the spec.
6. Keep the scalar-name tuple private unless a real downstream runtime import is
   identified.
7. Rewrite the risk statement to distinguish what the spike proves from what
   remains to be validated.

---

## Resolutions

Design-agent responses, 2026-07-10. **Owner rulings (same day): C1 — fold
the narrow exit-binding cross-check into this ticket (Option A); M5 — amend
the spec, keep the design's shape-category e2e.** All resolutions below are
now applied: design.md rev 2, spec.md amendments (requirements + success
criteria + open questions), and the concept's "explicitly unchanged"
mismatch edge case marked superseded.

- **C1 (exit bindings unchecked against provider types) — AGREE on the gap,
  partial push-back on framing; user decision needed on scope.**
  Push-back: this is not new exposure created by the design — the router has
  never inspected payloads, and a model channel mislabeled as any other
  *registered model name* already writes a falsely labelled artifact today
  (both names resolve to `write_json_model`). The concept reviewed and kept
  this looseness explicitly ("Declared name vs. payload mismatch …
  explicitly unchanged"). Agree, however, that D1 widens the *scalar* surface:
  a `float`-as-`bool` typo failed loudly before and would succeed after, and
  generated YAML being truthful means the spike could never catch it.
  The fix is genuinely cheap — `_validate_exit_module` can compare
  `binding.type_name` against the validator's existing channel-type map
  (`pipeline_validator.py:110-155`), skipping channels whose producer type is
  unresolvable. Recommendation: fold this narrow check in. But it amends the
  concept's explicit "unchanged" decision and can reject
  previously-passing (mislabeled-but-working) pipelines, so it is a scope
  call for the owner, not the design agent.
- **M1 (guard in wrong subsystem; false escape hatch) — ACCEPT in full.**
  Verified: `_build_schema_type_registry` runs at `pipeline.py:147`, before
  router selection at `pipeline.py:155-170` — D2 would hit explicit-router
  and entry-only callers, and B3's escape hatch was false. D2 is dropped
  entirely; no reserved namespace, no identity policy, no pydantic-caching
  bet. D3 is replaced by the reviewer's uniform rule at the composition
  boundary: `create_output_router_with_json_schemas` never overwrites a
  handler that `create_default_router()` supplied; `register_handler()` is
  the deliberate override. Verified safe: every current builtin's writer
  produces bytes identical to `write_json_model`, so defaults-win changes no
  existing caller's output; and `write_json_payload` serializes BaseModel
  payloads via `model_dump` (`writers.py:43-44`), so even a worst-case
  impostor named `float` writes correctly under the preserved default.
- **M2 (JSON-native overclaim) — ACCEPT.** The contract and all prose are
  renamed around "the four supported scalar types (`float`, `int`, `str`,
  `bool`) and their `RootModel` wrappers." No claim of closure over
  JSON-native or framework-producible values; the overview states plainly
  that `list`/`dict`/`None` are excluded.
- **M3 (fail-fast evidence missing) — ACCEPT.** Add an executor-level test:
  a pipeline whose ExitPoint declares an unregistered type and whose module
  records execution; assert `PipelineValidationError` and that the module
  never ran. Router-unit error tests are kept but not counted as evidence
  for this criterion.
- **M4 (spike overreach) — ACCEPT.** The risk statement will say precisely:
  the spike proves D1 for wrapped/bare `float` through a generated pipeline
  and all eight names at the router unit level; it proves nothing about
  collision policy (now largely deleted per M1) or generated `int`/`str`/
  `bool` pipelines. Most of the overreach disappears with D2.
- **M5 (e2e shape matrix vs. spec) — PUSH BACK; amend the spec instead.**
  Wrapped `int`/`str`/`bool` traverse literally the same code paths as
  wrapped `float` at every stage: the introspector branches on
  `is_rootmodel` only (`module_introspector.py:162-167`), the executor
  stores the whole object regardless of parameter, and the router calls
  `write_json_model` regardless of parameter. The type parameter never
  branches. Running all eight through `execute_pipeline` costs three more
  toy module classes to prove code paths already proven; the e2e's job is
  shape *categories* (bare × 4 through decomposition, wrapped × 1 through
  single-output), with the full 8-name matrix at router level. The spec's
  [INFERRED] "both shapes" wording will be corrected to say this — the spec
  was the imprecise artifact, not the design. If the owner disagrees, the
  cost of full-matrix e2e is three toy modules, not a redesign.
- **m1 (public constant) — ACCEPT.** With D2 gone there is no runtime
  consumer; the tuple stays private (`_DEFAULT_SCALAR_TYPE_NAMES`), promoted
  if the sysml-codegen cleanup ever needs it.
- **m2 (`include_builtins=False` wording) — ACCEPT.** Invariant reworded:
  primitives are "not included automatically"; a caller may still register
  wrapped names explicitly.
- **m3 (B1 identity test) — MOOT via M1.** Class identity is no longer
  load-bearing anywhere. The `RootModel[float].__name__ == "RootModel[float]"`
  pin stays — that *is* load-bearing for the hard-coded wrapped names.

---

**Overall:** Revise  
**Next Steps:** Resolve the issues above in this review, then re-run `my-design`
(or return to the design-agent session) and point it at this file. The reviewer
does not edit `design.md`.
