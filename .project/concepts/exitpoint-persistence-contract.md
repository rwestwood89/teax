# Design: ExitPoint Persistence Contract for JSON-Native Values

**Status:** Proposed
**Owner:** Reid W
**Created:** 2026-07-10
**Related:** `.project/backlog/teax-primitive-output-contract.md`, `docs/rootmodel-and-primitives.md`,
`/home/reid/1cfe/fusion-tea/.project/reports/2026-07-05-upstream-findings-register.md` (T-1/T-2)

---

## Overview

The framework moves values between pipeline modules through in-memory
channels, then persists final results to files at the pipeline's exit. These
stages grew separate type systems: the channel stage was deliberately extended
to carry raw numbers, strings, and booleans; the persistence stage still
assumes every value is a named structured record. This design closes the gap
with one rule: **the output boundary must persist every shape the framework
itself can place on a channel.** Plain JSON values become framework-owned;
only domain-named schemas require registration by the caller.

---

## Problem

A pipeline run has an interior and a boundary: module outputs flow through
channels to downstream modules, and an exit step writes selected channels to
disk. The interior's type rules were settled first for structured records
only, then deliberately extended — a single-output module puts a wrapped
scalar on its channel, while a multi-output module is decomposed, leaving
each field, including raw numbers, on its own channel, unwrapped so consumers
receive natural Python values.

The boundary never caught up. Its writer registry only understands named
structured records, so a raw number the framework itself placed on a channel
cannot leave the pipeline: validation rejects it before the run starts, and
even a hand-registered writer crashes because the stock serializer assumes a
structured record. Packages generated from SysML models emit truthful channel
types, so they always hit this wall. Every consumer patches around it by
building a custom router that teaches the framework to write a number as
JSON — framework knowledge duplicated in each harness, defeating the goal of
generated packages running with no hand-written glue.

## Goals

- Make every framework-produced channel value persistable by the default
  output path, with no consumer-written code.
- Let a generated package execute and persist results given only its module
  registry and schema list — no router construction in harnesses.
- Keep validation failing fast, before execution, for unknown output types.
- Keep persisted artifacts identical whether the producer was single-output
  (wrapped) or multi-output (raw) — files never leak internal plumbing — and
  preserve natural module signatures with no new wrapper boilerplate.

## Non-Goals

- Arbitrary object serialization: only JSON-native scalars and Pydantic
  models are covered; anything else needs an explicit handler.
- Changing channel representation, multi-output decomposition, generated code
  shapes, entry-point loading, exit filenames, or result aggregation.
- Changing the rule that an explicitly supplied router replaces the defaults.

## Design Principles

1. **The boundary is closed over the interior.** Any shape the framework's
   own machinery can manufacture on a channel is a shape its default output
   path can persist; if the interior's shape set ever expands again, the
   boundary contract is revisited in the same change. One honesty note: the
   interior's shape set is convention, not enforcement — the introspector
   accepts whatever annotation a `MultiOutput` field carries
   (`module_introspector.py:155-171`), so a `list[float]` field lands on a
   channel today and still cannot exit. This contract closes the boundary
   over the shapes codegen emits and the docs sanction. A `list`/`dict`
   follow-up is plausible and would extend this same mechanism, not replace it.
2. **Serialization knowledge lives with whoever defines the type.** The
   framework defines what channels may carry, so it owns writing JSON-native
   values. A domain package defines its named schemas, so it declares them.
   A harness owns neither and registers nothing.
3. **Fail-fast beats fallback.** An unknown output type is a configuration
   error surfaced before execution. The fix for a missing shape is explicit
   registration, never a "write whatever arrives" path — a generic fallback
   was proposed twice before and rejected both times (Appendix C).
4. **Artifacts are representation-independent.** A written file shows the
   value, not a wrapper object around it. Whether the value traveled wrapped
   or bare is invisible on disk.

## Architectural Bets

- **Fix the boundary, not the interior.** Raw scalars stay on multi-output
  channels; a permanently larger shape set is the price of natural module
  signatures and zero churn in existing pipelines and generated code.
- **Name-keyed handler registry stays** — we extend its default contents, not
  its mechanism.
- **Default registration over code generation** — the framework ships the
  JSON-native handlers; the code generator emits no persistence glue.

---

## Core Model

### Channel layer (unchanged)

Executor + validator + introspector; operates on real type objects. Its closed
shape set (`pipeline_executor.py:199-229`, `module_introspector.py:157-167`):

| Producer | Channel carries | Declared type name |
|---|---|---|
| Single-output module | whole `RootModel[T]` | `RootModel[float]` etc. |
| Multi-output module field | bare field value | `float`, `int`, `str`, `bool`, or a model name |
| Model-output module | `BaseModel` instance | class name |

### Persistence layer (extended)

`OutputRouter` maps type-name strings to `WriteHandler`s; the exit validator
checks `has_handler(type_name)` pre-run (`pipeline_validator.py:319`).
`create_default_router()` (`output_router.py:250`) gains eight entries:

```python
_JSON_NATIVE_HANDLER = WriteHandler(fn=writers.write_json_payload, extension=".json")
_JSON_MODEL_HANDLER = WriteHandler(fn=writers.write_json_model, extension=".json")
JSON_NATIVE_TYPE_NAMES = ("float", "int", "str", "bool")

def create_default_router(*, in_memory: bool = False) -> OutputRouter:
    handlers = {name: _JSON_NATIVE_HANDLER for name in JSON_NATIVE_TYPE_NAMES}
    handlers |= {f"RootModel[{name}]": _JSON_MODEL_HANDLER for name in JSON_NATIVE_TYPE_NAMES}
    handlers |= { ... existing built-in schema handlers ... }
    return OutputRouter(type_handlers=handlers, in_memory=in_memory)
```

The wrapped names are safe to hard-code — Pydantic generates
`RootModel[float].__name__ == "RootModel[float]"` deterministically, so no
domain class can collide. Both writers already exist: no new code paths.

### The contract, stated once

> The default output path persists every JSON-native channel shape —
> `float`, `int`, `str`, `bool`, and `RootModel` of each — with no
> registration. Domain-named schemas are registered by their package via
> `custom_schema_types` (JSON) or an explicit router (other formats).
> An explicit router replaces the defaults entirely.

### What module authors write (unchanged — what the contract protects)

```python
class PlantOutputs(MultiOutput):
    lcoe_usd_mwh: float          # natural field type; lands bare on a channel
    breakdown: CostBreakdown     # model field; lands as CostBreakdown

class GainCalc(ModuleBase[DriverParams, RootModel[float]]):
    def run(self, energy: float) -> ModuleResult[RootModel[float]]:
        return ModuleResult(data=RootModel[float](energy * GAIN))
```
```yaml
exit:
  module_type: ExitPoint
  outputs:
    lcoe_usd_mwh: float lcoe_usd_mwh.json           # works with defaults
    fusion_gain: RootModel[float] fusion_gain.json  # works with defaults
    breakdown: CostBreakdown breakdown.json         # needs custom_schema_types
```

### What consumers write (the tangible payoff)

```python
# The whole persistence story is two arguments — no router construction:
result = execute_pipeline(PIPELINE, registry=create_ife_tea_registry(),
                          custom_schema_types=CUSTOM_SCHEMA_TYPES)
```

The per-harness workaround this deletes is quoted in Appendix F.

## Required Invariants

- `create_default_router().has_handler(n)` holds for all eight JSON-native
  names and all existing built-in schema names.
- Writing `1.25` under `"float"` and `RootModel[float](1.25)` under
  `"RootModel[float]"` produce byte-identical files containing `1.25`.
- An ExitPoint declaring a name with no handler still raises
  `PipelineValidationError` before any module runs.
- `execute_pipeline(output_router=r)` uses `r` verbatim;
  `include_builtins=False` routers exclude primitives (they count as builtins).
- `custom_schema_types` still rejects non-`BaseModel` entries; existing
  `BaseModel` artifacts serialize byte-identically to today.

## How It Works

**Generated pipeline, no harness glue.** A sysml-codegen package declares
`RootModel[float]` and `float` exit outputs. With no router passed, the
auto-created router starts from the defaults (all eight JSON-native names)
plus JSON handlers per custom schema. Validation passes; scalars write bare.

**Multi-output scalar field.** `PlantOutputs.lcoe_usd_mwh` is decomposed onto
channel `lcoe_usd_mwh` as a bare `float`. The exit binding names type `float`;
the default handler writes `142.7` via `write_json_payload`. Previously:
T-1 validation failure, then T-2 `model_dump()` crash if forced past.

## Edge Cases and Failure Modes

- **Falsy scalars** (`0.0`, `""`, `False`) persist normally; the
  produced/not-produced check is `payload is None`, not truthiness.
- **Declared name vs. payload mismatch.** The router trusts the declared name
  and never inspects payloads — true for models today, true for primitives
  after. ~~Pre-existing looseness, explicitly unchanged.~~ **Superseded at
  design review (C1, owner-approved):** widening the handler set turns loud
  scalar mislabels into silently mislabelled artifacts, so the design adds a
  pre-run cross-check of each exit binding's declared type against its
  producer channel's resolvable type (unresolvable producers are skipped).
  The router itself still never inspects payloads.
- **Custom-only routers.** `include_builtins=False` or a hand-built
  `OutputRouter` has no primitive handlers. Intentional (explicit replaces
  default), but the docs must say so — here "primitives just work" is false.
- **Non-JSON-native scalars** (`bytes`, `Decimal`): not registered; validation
  fails with the existing actionable error, per Principle 3.
- **`None` is the un-persistable JSON-native value.** The router treats
  `payload is None` as "channel not produced" (`output_router.py:107`), so an
  `Optional[float]` field that is legitimately `None` records
  `produced: false` in the manifest instead of writing `null`. Pre-existing
  semantics, kept — but it is a named exception to "every framework-produced
  channel value persists," and the docs must state it.
- **Reserved names can be shadowed.** Nothing stops a custom schema class
  whose `__name__` is literally `float` (legal Python); via the auto-router
  path it would silently override the primitive handler with
  `write_json_model` and resurrect the T-2 crash. Spec-stage decision: reject
  custom schema types whose names collide with the eight reserved names.
- **The boundary is closed at exit only.** A bare-scalar JSON input still
  cannot load at the EntryPoint (a non-goal here); the docs should name the
  asymmetry in one line so nobody reads "primitives just work" as covering
  entry.

## Vocabulary

- **channel layer**: executor/validator/introspector machinery routing values
  between modules in memory; works with type objects.
- **persistence layer**: ExitPoint + `OutputRouter` + writers turning
  channels into files; works with type-name strings.
- **JSON-native shape**: `float`, `int`, `str`, `bool`, or `RootModel` of one
  of these; serialization is framework knowledge.
- **domain-named schema**: any other `BaseModel` subclass; registered by its
  defining package. **write handler**: `(fn, extension)` under a type name.

## Validation Strategy

- Unit: eight default handlers exist; exact payload bytes per scalar and
  wrapped scalar; extension enforcement; unknown-name error intact.
- Regression: battery demo and existing simkit output tests byte-identical.
- Cross-repo acceptance (load-bearing): fusion-tea deletes its router
  workaround from `run_anchors.py` and reproduces anchor outputs using a
  *generated* package — a hand-written fixture would not prove the boundary
  is closed (backlog ticket's validation note).
  **Already demonstrated by the 2026-07-10 spike** (see Next-Stage Handoff):
  with the eight-handler edit alone and the workaround deleted, all 13
  fusion-tea anchor checks pass and artifacts are byte-identical. The
  remaining acceptance work is committing the change and landing the
  workaround deletion in fusion-tea, not proving feasibility.

## Next-Stage Handoff

**Settled here:** the contract statement, the eight default names, handler
choice (`write_json_payload` / `write_json_model`), ownership split, and that
explicit routers / `include_builtins=False` exclude primitives.
**Sufficiency is spike-confirmed** (2026-07-10): with the eight-handler edit
alone and the router workaround deleted, all 13 fusion-tea anchor checks pass,
persisted artifacts are byte-identical to the workaround run, falsy scalars
persist, and the teax suite has zero new failures. T-1 reproduced exactly as
described before the edit. Full log and reproduction:
`.project/active/spike-exitpoint-default-primitives/findings.md`.

**Spec detail still needed:** exact test list; doc edits
(`docs/rootmodel-and-primitives.md` gains an ExitPoint section; `CLAUDE.md`
error table updated; docs state the `None`/`Optional` exception and the
exit-only asymmetry); whether `JSON_NATIVE_TYPE_NAMES` is public API; whether
custom schema names colliding with the eight reserved names are rejected
(recommended) or allowed to override.

**Follow-up (separate sysml-codegen ticket):** with wrapped names
default-registered, `_collect_exit_point_primitive_types()` and generated
`primitives.py` exit plumbing become removable. **Scope it to exit-only:**
`CUSTOM_SCHEMA_TYPES` also feeds entry loaders and field-reference resolution
(`pipeline_validator.py:117-136`) — this contract replaces only the exit-router
role, and the spike did not test the removal. If codegen ever emits a
`RootModel`-typed entry artifact, the wrappers become load-bearing again on
the entry side.

## Summary

The interior deliberately produces bare and wrapped scalars on channels, but
the output boundary only knew named models — so every consumer re-taught the
framework to write a float. Closing the boundary over the interior's shapes
(eight default handler names, two existing writers, zero new mechanism) makes
every valid pipeline a persistable pipeline and deletes harness glue.

---

## Appendix: Rejected Alternatives and History

**A. Wrap multi-output fields in `RootModel` at decomposition** (shrink the
interior's shape set instead of extending the boundary). Rejected: breaks the
settled invariant "channel type = what the executor stores" (chosen over
unwrap-at-source in `thoughts/specs/rootmodel-single-output-introspection-bug.md`);
contradicts the documented rule "never `RootModel` as a model field"
(`docs/rootmodel-and-primitives.md`); forces `.root` extraction into every
downstream binding; requires coordinated changes in sysml-codegen, the battery
demo, and fusion-tea. Highest blast radius of any option, for no consumer gain.

**B. Code generator emits an `OutputRouter` per package.** Rejected:
distributes framework serialization knowledge into every generated package;
harnesses must plumb the router; violates Principle 2. sysml-codegen's
PIPELINE-TRUTH epic deliberately kept routers out of generated packages.

**C. Duck-typed fallback writer** ("if it's JSON-able, write it"). Rejected
twice in this codebase's history: the 2025-09-22 output-routing plan's risk
register noted-and-declined it, and Option C of
`thoughts/research/exitpoint_custom_schema_challenge.md` rejected it for
losing fail-fast validation and extension checking. Violates Principle 3.

**D. Make `write_json_model` tolerant** (branch on `hasattr(model_dump)`).
Rejected: hides real type errors for model payloads and fixes only T-2,
leaving T-1 validation failures in place.

**E. Bare names only (the backlog ticket's minimal shape), without the four
wrapped names.** Workable but lopsided: bare scalars would be free while
their sanctioned wrappers still require `custom_schema_types` plumbing whose
only purpose is feeding the exit router. Registering the deterministic
wrapped names costs four dict entries and lets sysml-codegen delete its
primitive-wrapper collection machinery later.

**F. The deleted workaround (for reference).** From
`fusion-tea/exploration/ife_e2e/run_anchors.py:119-132`, repeated in every
consumer harness until this change:

```python
router = create_output_router_with_json_schemas(["RootModel[float]"])
router.register_handler("float", WriteHandler(
    fn=lambda value, path: Path(path).write_text(json.dumps(value)), extension=".json"))
result = execute_pipeline(PIPELINE, registry=..., output_router=router,
                          custom_schema_types=CUSTOM_SCHEMA_TYPES)
```

**Decision trail (for auditors):** primitives deferred in
`thoughts/designs/generalized_teax_type_system_design.md` (commit `067dbf0`);
`MultiOutput` decomposition with unwrapped fields (`683132b`); `RootModel[T]`
adopted over executor auto-wrapping (`4723f8a`); single/multi wrapping
asymmetry fixed in the introspector (`429a519`); default router stripped to
generic handlers in the package split (Phase 5, `ea13013`); gap first hit by
generated pipelines in fusion-tea WI-013/WI-015 (T-1/T-2, upstream findings
register 2026-07-05).
