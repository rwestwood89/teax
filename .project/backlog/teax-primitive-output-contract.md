# Ticket: Support JSON Primitive Types at the ExitPoint Boundary

**Created:** 2026-07-10 09:31 PDT
**Priority:** High
**Type:** Design / Bug
**Status:** Certified (audit 2026-07-12) — pre-PR fusion-tea verification pending

## Overview

Make a code-generated TEAx pipeline executable without a consumer-supplied
`OutputRouter` when its ExitPoint includes `RootModel[T]` and JSON-native scalar
channels. sysml-codegen emits both shapes by design; TEAx currently handles the
Pydantic wrapper only when the generated schema list is supplied and cannot
persist a plain scalar with its standard JSON writer.

## Description

### User-visible problem

sysml-codegen can generate, validate, wire, and execute the fusion-tea IFE
computation graph with no codegen bridge and no model-value workarounds. The
generated package still cannot use TEAx's normal output path without harness
code that builds a custom router.

The workaround is not domain policy. It teaches TEAx how to write types that
the framework already routes between modules:

```python
router = create_output_router_with_json_schemas(["RootModel[float]"])
router.register_handler(
    "float",
    WriteHandler(
        fn=lambda value, path: Path(path).write_text(json.dumps(value)),
        extension=".json",
    ),
)
```

Reference implementation:
`/home/reid/1cfe/fusion-tea/exploration/ife_e2e/run_anchors.py:119-132`.

### The two failure layers

1. **T-1, validation:** `PipelineValidator._validate_exit_module()` requires a
   registered write handler for every ExitPoint type name. Without one,
   `RootModel[float]` and `float` fail before execution at
   `packages/teax-simkit/simkit/core/pipeline_validator.py:312-327`.
2. **T-2, writing:** registering `float` through the existing JSON-schema helper
   is not sufficient. That helper uses `write_json_model()`, which unconditionally
   calls `model_dump()`. A plain scalar then fails with
   `'float' object has no attribute 'model_dump'` at
   `packages/teax-simkit/simkit/io/writers.py:13-27`.

The original cross-repository finding is recorded in
`/home/reid/1cfe/fusion-tea/.project/reports/2026-07-05-upstream-findings-register.md:118-136`.

## Relevant sysml-codegen Behavior and Changes

The TEAx contract must account for the current generated package, including the
functionality refresh that landed after the original T-1/T-2 report.

### Channel shapes are deliberate

- A single-output module uses a generated primitive alias such as
  `Float = RootModel[float]`. Its channel and ExitPoint type are
  `RootModel[float]`.
- A multi-output module returns a Pydantic output container, but TEAx decomposes
  its fields into separate channels. A field annotated as `float` therefore
  produces a plain-`float` channel and a `float` ExitPoint type.
- sysml-codegen's YAML generator emits the runtime channel type rather than
  disguising a scalar as a model:
  `src/sysml_codegen/generation/pipeline.py:185-203,248-266`.
- This matches TEAx's own guidance: use `RootModel[T]` for a single-output model,
  and plain primitives as fields of a multi-output model. See
  `docs/rootmodel-and-primitives.md`.

### sysml-codegen now registers generated primitive wrappers

- Generated packages include `primitives.py` aliases for `Float`, `Int`,
  `String`, and `Bool`.
- `_collect_exit_point_primitive_types()` inspects single-output graph modules
  and adds the required wrapper classes to the generated package's
  `CUSTOM_SCHEMA_TYPES`:
  `src/sysml_codegen/generation/registry.py:33-66`.
- The generated registry template imports those aliases and publishes them next
  to parameter-group schemas:
  `src/sysml_codegen/templates/registry_function.py.jinja2:12-53`.
- Passing `CUSTOM_SCHEMA_TYPES` to `execute_pipeline()` lets TEAx auto-register
  a handler named `RootModel[float]` because the generated `Float` class has that
  Pydantic type name.

This closes the generated-package half of T-1 for single-output wrappers. It
does not cover plain scalar fields: `custom_schema_types` accepts Pydantic model
classes, not `float`, and its registered handler still assumes `model_dump()`.

### sysml-codegen intentionally does not generate a router

- The generated package exports a module registry and `CUSTOM_SCHEMA_TYPES`.
- It does not export a consumer-specific `OutputRouter`.
- The PIPELINE-TRUTH and TRUTH-DEBT epics removed value and wiring workarounds,
  but explicitly kept the T-1/T-2 router harness-side because the ownership
  contract had not been settled.

## Proposed Contract Change

TEAx's ExitPoint contract should be:

> ExitPoint JSON persistence supports both Pydantic models and JSON-native
> scalar channel values. A caller must register domain-specific schema names,
> but must not register handlers merely to persist `float`, `int`, `str`, or
> `bool` values produced by a valid TEAx module.

### TEAx responsibilities

1. `create_default_router()` registers JSON handlers for the YAML type names
   `float`, `int`, `str`, and `bool`.
2. Those primitive handlers use a writer that accepts JSON-native payloads,
   such as the existing `write_json_payload()`, rather than
   `write_json_model()`.
3. `create_output_router_with_json_schemas()` continues registering named
   Pydantic/RootModel types supplied by domain packages. Its handler must remain
   valid for `RootModel[T]` and ordinary `BaseModel` instances.
4. Pipeline validation continues to fail before execution for an ExitPoint type
   with no registered handler. Supporting primitives must not weaken unknown-type
   validation.
5. The written representation remains the natural JSON value:
   `float -> 1.25`, `int -> 2`, `str -> "value"`, `bool -> true`.
   Pydantic output serialization remains unchanged.

### sysml-codegen responsibilities after the contract change

1. Continue emitting `RootModel[T]` for single-output channels and primitive
   field types for multi-output channels.
2. Continue publishing generated wrapper classes in `CUSTOM_SCHEMA_TYPES` so
   TEAx can resolve and write `RootModel[T]` ExitPoints.
3. Pass the generated registry and `CUSTOM_SCHEMA_TYPES` to `execute_pipeline()`.
4. Do not generate or require an `OutputRouter` for standard JSON output.

### Explicit-router behavior

This ticket does not change the current rule that an explicitly supplied
`output_router` is used as-is. Custom routers may intentionally replace the
defaults. The acceptance path for generated packages is to omit
`output_router` and let TEAx combine its default primitive handlers with the
generated `CUSTOM_SCHEMA_TYPES`.

## Acceptance Criteria

- A pipeline with a single-output `RootModel[float]` module executes with
  `custom_schema_types=[Float]`, no explicit router, and writes the scalar JSON
  value successfully.
- A pipeline with a multi-output model containing a plain `float` field executes
  with no explicit router and writes that channel successfully.
- Default-router tests cover `float`, `int`, `str`, and `bool`, including exact
  JSON payloads and file extensions.
- Existing `BaseModel` and `RootModel` output tests remain green with unchanged
  serialized content.
- An unknown ExitPoint type still fails validation with the existing actionable
  error.
- fusion-tea can delete the router construction and `WriteHandler` lambda from
  `exploration/ife_e2e/run_anchors.py`, execute with its generated registry plus
  `CUSTOM_SCHEMA_TYPES`, and reproduce the existing anchor outputs.
- Documentation states the ExitPoint persistence contract and distinguishes
  default JSON primitives from domain-specific schema registration.

## Out of Scope

- Changing sysml-codegen's channel representation or generated pipeline YAML.
- Wrapping fields of a multi-output Pydantic model in `RootModel[T]`.
- Generating an OutputRouter in every sysml-codegen package.
- Changing explicit-router replacement/augmentation semantics.
- Arbitrary object serialization. This ticket covers Pydantic models and the
  JSON-native scalar types `float`, `int`, `str`, and `bool` only.
- Hierarchical result aggregation or changing ExitPoint filenames.
- EntryPoint loading behavior.
- Constraint execution or other SysML semantics.

## Likely Implementation Surface

- `packages/teax-simkit/simkit/io/output_router.py`
  - Add default handlers for the four JSON-native scalar type names.
- `packages/teax-simkit/simkit/io/writers.py`
  - Reuse or narrow `write_json_payload()` as the primitive writer.
- `packages/teax-simkit/simkit/tests/`
  - Add validator, router, writer, and end-to-end ExitPoint tests for both
    single-output RootModel and multi-output scalar channels.
- `docs/rootmodel-and-primitives.md`
  - Document output persistence alongside the existing channel-type rules.

## Validation Notes

The cross-repository acceptance test should use a generated package rather than
only a hand-written YAML fixture. The failure arose at the boundary between
truthful sysml-codegen types and TEAx's router, so a component-only test would
not prove that the contract is closed.

Estimated implementation size is small, but the contract decision is
load-bearing: default JSON primitive support should be explicit and tested
rather than retained as a fusion-tea harness convention.
