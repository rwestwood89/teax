# Spec: ExitPoint Bare Primitive Type Support

**Status:** Complete
**Owner:** Reid Westwood
**Created:** 2026-02-10
**Complexity:** LOW
**Branch:** main

---

## Business Goals

### Why This Matters

The `sysml-codegen` project generates TEAx pipeline YAML from SysMLv2 models. Multi-output CalcUsage modules produce bare `float` values on channels, and the generated ExitPoint correctly declares `float` as the output type. However, TEAx has no write handler for bare primitive types, so these pipelines fail at validation time with `OutputRouterError: No writer registered for ExitPoint output type 'float'`.

This is Bug 4 of 7 identified during sysml-codegen E2E validation. The sysml-codegen design doc confirms the generated YAML is correct and this is a TEAx gap.

### Success Criteria

- [x] A pipeline YAML with `float` ExitPoint output type executes without error and writes valid JSON
- [x] Same for `int`, `str`, `bool`
- [x] A pipeline YAML with `float` EntryPoint input type loads from JSON without error
- [x] Bare `float` channels produce the same JSON format (`42.0`) regardless of whether they originated from a single-output `RootModel[float]` module or a multi-output module
- [x] Zero-config: primitive handlers are built-in, no user setup required
- [x] All existing tests pass (full backward compatibility)

### Priority

Blocking for sysml-codegen E2E validation. This is the only one of the 7 identified codegen bugs that requires a TEAx fix.

---

## Problem Statement

### Current State

TEAx's pipeline output system is built around Pydantic model serialization. Three validation checkpoints reject any ExitPoint type without a registered write handler:

1. `PipelineValidator._validate_exit_module()` (`pipeline_validator.py:319`)
2. `SerialPipelineExecutor._ensure_exit_handlers()` (`pipeline_executor.py:243`)
3. `OutputRouter.write_outputs()` (`output_router.py:98`)

The default router only registers handlers for `FinancialResults`, `MockForecastSeries`, and `SyncGuidanceSeries`. The `write_json_model()` writer calls `.model_dump()` which fails on bare primitives (AttributeError).

The existing workaround is wrapping primitives in `RootModel[float]`, which works for single-output modules (the entire RootModel is stored in the channel). But multi-output modules extract bare field values from `MultiOutput.to_channel_dict()`, producing unwrapped primitives in channels.

Additionally, the schema type registry (`_build_schema_type_registry`) and entry loaders (`_BUILTIN_ENTRY_LOADERS`) have no entries for primitive types, so `_resolve_schema_type("float")` raises `ValueError` and EntryPoint loading of primitives is impossible.

### Desired Outcome

TEAx natively supports `float`, `int`, `str`, and `bool` as first-class types in both ExitPoint (writing) and EntryPoint (reading) contexts. Primitive types are registered in the default router, schema type registry, and entry loaders with no user configuration required.

---

## Scope

### In Scope

- Primitive write handler for JSON serialization of bare `float`, `int`, `str`, `bool`
- Registration of primitive handlers in the default OutputRouter
- Registration of primitive types in the schema type registry
- Registration of primitive entry loaders for JSON deserialization
- Unit tests for all new functionality
- Integration test: pipeline with primitive ExitPoint type

### Out of Scope

- Generic container types (`list[float]`, `dict[str, int]`, etc.)
- Custom serialization formats for primitives (Parquet, HDF5)
- Changes to `RootModel[float]` behavior (unchanged)
- Changes to sysml-codegen (the fix is entirely in TEAx)
- Changes to `PipelineValidator` (it delegates handler checks to `OutputRouter.has_handler()`)

### Edge Cases & Considerations

- **`_resolve_schema_type()` fallback path**: When `custom_schema_types` is `None`, the executor falls back to `getattr(schema, type_name, None)` which won't find `float` on the schema module. Primitive types MUST be handled in this fallback path too.
- **`create_output_router_with_json_schemas()` with `include_builtins=False`**: Primitives are part of the default router (builtins). When builtins are excluded, primitives are excluded. This is correct -- primitives are built-in types.
- **JSON format invariant**: A bare `float` MUST serialize as raw JSON (`42.0`), not wrapped (`{"value": 42.0}`). This ensures consistency with `RootModel[float].model_dump(mode="json")` which also produces `42.0`. Downstream consumers reading ExitPoint outputs MUST NOT need to know whether a float came from a single-output or multi-output module.

---

## Requirements

### Functional Requirements

> Requirements below are from user's request unless marked [INFERRED].

1. **FR-1**: ExitPoint MUST support `float`, `int`, `str`, and `bool` as output types, serializing them to JSON files.
2. **FR-2**: Primitive JSON format MUST be raw value (e.g., `42.0`), not wrapped (e.g., `{"value": 42.0}`). This preserves format consistency with `RootModel[T].model_dump(mode="json")`.
3. **FR-3**: EntryPoint MUST support loading `float`, `int`, `str`, and `bool` from JSON files. Symmetric API contract: if ExitPoint can write a type, EntryPoint SHOULD be able to read it.
4. **FR-4**: Primitive handlers MUST be registered in the default OutputRouter. Users MUST NOT need custom setup to use primitive ExitPoint types.
5. **FR-5**: Primitive types MUST be recognized by the schema type registry so `_resolve_schema_type("float")` returns `float`.
6. **FR-6**: [INFERRED] The `_resolve_schema_type()` fallback path (when `type_registry` is `None`) MUST also handle primitive type names, since `execute_pipeline()` only builds `schema_type_registry` when `custom_schema_types` is provided.
7. **FR-7**: [INFERRED] All changes MUST be fully backward compatible. Existing `RootModel[float]` pipelines MUST continue to work unchanged.

---

## Acceptance Criteria

### Core Functionality
- [x] `write_json_primitive(42.0, path)` writes `42.0` to file (raw JSON)
- [x] `write_json_primitive("hello", path)` writes `"hello"` to file
- [x] `write_json_primitive(True, path)` writes `true` to file
- [x] `create_default_router().has_handler("float")` returns `True`
- [x] `create_default_router().has_handler("int")` returns `True`
- [x] `create_default_router().has_handler("str")` returns `True`
- [x] `create_default_router().has_handler("bool")` returns `True`
- [x] `_build_schema_type_registry()["float"]` returns `float`
- [x] `_resolve_schema_type("float")` returns `float` (even without custom type registry)
- [x] Entry loader for `float` reads `42.0` from JSON file and returns Python `float`
- [x] Pipeline with `float` ExitPoint type executes and writes valid JSON output

### Quality & Integration
- [x] All existing tests pass (`pytest` from root) -- 197 passed
- [x] New unit tests cover all four primitive types for both writing and reading
- [x] Integration test demonstrates end-to-end pipeline with primitive ExitPoint

---

## Related Artifacts

- **Research:** `.project/research/20260210-exitpoint-primitive-type-support.md`
- **Design:** `.project/active/exitpoint-primitive-types/design.md`
- **Plan:** `.project/active/exitpoint-primitive-types/plan.md`
- **Upstream bug:** `sysml-codegen/.project/active/codegen-bug-fixes/design.md` (Bug 4)
- **Commit:** `b2f91f2`

---

**Completed:** 2026-02-10
