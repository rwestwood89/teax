# Design: ExitPoint Bare Primitive Type Support

**Status:** Reviewed
**Owner:** Reid Westwood
**Created:** 2026-02-10
**Complexity:** LOW
**Branch:** main
**Commit:** 7623677

---

## Overview

Add native support for bare primitive types (`float`, `int`, `str`, `bool`) in TEAx's ExitPoint (writing) and EntryPoint (reading) paths, enabling sysml-codegen multi-output pipelines to execute without custom setup.

## Related Artifacts

- **Spec:** `.project/active/exitpoint-primitive-types/spec.md`
- **Research:** `.project/research/20260210-exitpoint-primitive-type-support.md`
- **Upstream bug:** `sysml-codegen/.project/active/codegen-bug-fixes/design.md` (Bug 4)

---

## Research Findings

### Existing Code Analyzed

| File | What It Does | Relevance |
|------|-------------|-----------|
| `simkit/io/writers.py:13-28` | `write_json_model()` -- calls `model.model_dump()` | Fails on primitives; need new writer |
| `simkit/io/writers.py:31-49` | `write_json_payload()` -- handles dicts and models | Already handles primitives via `json.dump()` but less explicit |
| `simkit/io/output_router.py:250-273` | `create_default_router()` -- 3 Pydantic model handlers | Add primitive handlers here |
| `simkit/io/output_router.py:276-343` | `create_output_router_with_json_schemas()` -- delegates to `create_default_router()` when `include_builtins=True` | Primitives inherit automatically |
| `simkit/core/pipeline_executor.py:317-352` | `_resolve_schema_type()` -- type name resolution | Fallback path needs primitive support |
| `simkit/core/pipeline_executor.py:404-501` | `_build_schema_type_registry()` -- built-in type registry | Add primitive entries |
| `simkit/core/pipeline_executor.py:504-549` | `_build_entry_loaders()` -- auto-registers custom loaders | Works with `_BUILTIN_ENTRY_LOADERS` |
| `simkit/core/pipeline_executor.py:556-598` | `_BUILTIN_ENTRY_LOADERS` -- loader dict | Add primitive loaders |
| `simkit/core/pipeline_validator.py:116-137` | Entry type resolution fallback | Gracefully skips unresolved types; no changes needed |
| `simkit/core/pipeline_validator.py:285-328` | `_validate_exit_module()` -- delegates to `has_handler()` | No changes needed |
| `simkit/core/pipeline.py:140-170` | `execute_pipeline()` wiring | No changes needed |

### Key Pattern: How Handlers Flow Through the System

When `execute_pipeline()` is called **without** `custom_schema_types` (the common case for sysml-codegen):

```
execute_pipeline(spec_path, output_dir, registry=my_registry)
  │
  ├── schema_type_registry = None  (no custom types)
  ├── entry_loaders = None → uses _BUILTIN_ENTRY_LOADERS directly
  ├── router = create_default_router()  ← primitive handlers go here
  │
  ├── Validator: _validate_exit_module()
  │     └── router.has_handler("float") → True (if registered)  ✓
  │
  ├── Executor: _ensure_exit_handlers()
  │     └── router.has_handler("float") → True  ✓
  │
  ├── Executor: _load_entry_binding()  (if float used in EntryPoint)
  │     ├── _resolve_schema_type("float", None)  ← needs fallback handling
  │     └── _entry_loaders.get(float)  ← needs loader in _BUILTIN_ENTRY_LOADERS
  │
  └── Router: write_outputs()
        └── handler.fn(42.0, path)  ← needs write_json_primitive()
```

When called **with** `custom_schema_types`:

```
execute_pipeline(..., custom_schema_types=[MySchema])
  │
  ├── schema_type_registry = _build_schema_type_registry([MySchema])
  │     └── includes primitives if added to built-in registry  ✓
  ├── entry_loaders = _build_entry_loaders([MySchema])
  │     └── starts from _BUILTIN_ENTRY_LOADERS (includes primitives)  ✓
  ├── router = create_output_router_with_json_schemas(["MySchema"])
  │     └── delegates to create_default_router() (includes primitives)  ✓
  └── ... rest works same as above
```

Both paths are covered by the same set of changes.

### Validator Fallback Is Safe Without Changes

The validator's entry type resolution fallback (`pipeline_validator.py:128-134`) does `getattr(schema, "float")` which fails with `AttributeError`, and the handler `continue`s (skips the type). This means:

- Primitive channels won't have field reference validation at the validator level
- This is correct: primitives have no fields, so there's nothing to validate
- The pipeline still executes normally

No changes to `pipeline_validator.py` are needed.

### Return Type of `_resolve_schema_type()`

Currently annotated `-> type[schema.StrictBaseModel]`. With primitive support it can return `float`, `int`, etc. The annotation should be widened to `-> type`. The only caller (`_load_entry_binding` at line 300) uses the result as a dict key for loader lookup, so widening the annotation has no runtime impact.

---

## Proposed Design

### Component 1: Primitive Writer (`writers.py`)

**Purpose:** Serialize bare Python primitives to JSON files.

**Location:** `simkit/io/writers.py` -- add after `write_json_payload()` (after line 49)

**Function signature:**

```python
def write_json_primitive(value: float | int | str | bool, path: str | Path) -> Path:
```

**Behavior:**
- Create parent directories (`resolved.parent.mkdir(parents=True, exist_ok=True)`) -- same pattern as all other writers
- Write raw JSON: `json.dump(value, handle)` -- produces `42.0`, `"hello"`, `true`, `7`
- Return resolved path

**JSON format rationale (FR-2):** Raw value, not wrapped. `json.dump(42.0, f)` produces valid JSON. This matches `RootModel[float](42.0).model_dump(mode="json")` which also returns `42.0`. Downstream consumers see identical format regardless of single-output vs multi-output source.

**No `indent` parameter:** For scalar values, indentation has no visual effect. Omit for consistency -- but including `indent=2` is also fine (harmless). Choose whichever matches the existing writer pattern. Existing writers use `indent=2`, so use `indent=2` for consistency.

### Component 2: Default Router Registration (`output_router.py`)

**Purpose:** Make primitive types available in the default OutputRouter with zero user configuration.

**Location:** `simkit/io/output_router.py` -- modify `create_default_router()` (lines 250-273)

**Change:** Add four primitive handler entries to the `handlers` dict:

```python
"float": WriteHandler(fn=writers.write_json_primitive, extension=".json"),
"int": WriteHandler(fn=writers.write_json_primitive, extension=".json"),
"str": WriteHandler(fn=writers.write_json_primitive, extension=".json"),
"bool": WriteHandler(fn=writers.write_json_primitive, extension=".json"),
```

These go alongside the existing Pydantic model handlers (`FinancialResults`, `MockForecastSeries`, `SyncGuidanceSeries`).

**Why the same handler for all four:** `json.dump()` handles all Python primitives natively. A single `write_json_primitive` function is sufficient -- the JSON encoder dispatches correctly for each type.

**Propagation to `create_output_router_with_json_schemas()`:** When `include_builtins=True` (default), this function calls `create_default_router()` which includes primitives. When `include_builtins=False`, primitives are excluded. This is correct per spec: primitives are built-in types.

### Component 3: Schema Type Registry (`pipeline_executor.py`)

**Purpose:** Enable `_resolve_schema_type("float")` to return `float` for both the registry path and the fallback path.

#### 3a. Single Source of Truth: `_PRIMITIVE_TYPES` Constant

**Location:** `simkit/core/pipeline_executor.py` -- new module-level constant, near line 315

```python
_PRIMITIVE_TYPES: dict[str, type] = {
    "float": float,
    "int": int,
    "str": str,
    "bool": bool,
}
```

This constant is the **single source of truth** for primitive type mapping. It is referenced by both the registry builder and the fallback path -- never duplicated inline.

#### 3b. Built-in Registry (`_build_schema_type_registry`)

**Location:** `simkit/core/pipeline_executor.py:451-460` (the `registry` dict)

**Change:** Spread `_PRIMITIVE_TYPES` into the built-in registry dict:

```python
registry: dict[str, type] = {
    schema.FinancialParams.__name__: schema.FinancialParams,
    # ... existing Pydantic model entries ...
    **_PRIMITIVE_TYPES,  # Single source of truth for primitives
}
```

This covers the case when `custom_schema_types` is provided (the registry is built and includes primitives). No inline duplication of the four primitive entries.

**Impact on `test_all_user_facing_schemas_registered`:** The test at `test_custom_schema_registration.py:126` asserts `len(registry) == 8`. After adding 4 primitives, this becomes 12. Update the test to expect 12 and add assertions for primitive types.

#### 3c. Fallback Path (`_resolve_schema_type`)

**Location:** `simkit/core/pipeline_executor.py:317-352`

**Change:** Add a primitive type lookup (referencing `_PRIMITIVE_TYPES`) before the final `raise ValueError` in the `else` branch (fallback when `type_registry` is None):

```python
else:
    # Fall back to built-in schema module only
    type_obj = getattr(schema, type_name, None)
    if type_obj is not None:
        return type_obj
    # Check primitive types (uses same _PRIMITIVE_TYPES constant as registry builder)
    primitive = _PRIMITIVE_TYPES.get(type_name)
    if primitive is not None:
        return primitive
    raise ValueError(f"Unknown schema type '{type_name}'")
```

**Also add primitive check in the `if type_registry is not None` branch:** The custom registry already includes primitives from 3b (via `**_PRIMITIVE_TYPES` spread), so this is handled automatically. No additional change needed.

#### 3d. Return Type Annotation

**Change:** Widen `_resolve_schema_type` return type from `-> type[schema.StrictBaseModel]` to `-> type`. The function can now return primitive types which are not `StrictBaseModel` subclasses.

### Component 4: Entry Loaders (`pipeline_executor.py`)

**Purpose:** Enable EntryPoint loading of bare primitives from JSON files (FR-3, symmetric API).

**Location:** `simkit/core/pipeline_executor.py:564-568` (after existing `_BUILTIN_ENTRY_LOADERS` entries)

**Change:** Add a helper function and four primitive loaders to `_BUILTIN_ENTRY_LOADERS`:

```python
def _load_json_primitive(path: Path, expected_type: type) -> float | int | str | bool:
    """Load a bare primitive from a JSON file with type checking."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, expected_type):
        raise TypeError(
            f"Expected {expected_type.__name__} from '{path}', "
            f"got {type(value).__name__}: {value!r}"
        )
    return value

_BUILTIN_ENTRY_LOADERS[float] = lambda path: _load_json_primitive(path, float)
_BUILTIN_ENTRY_LOADERS[int] = lambda path: _load_json_primitive(path, int)
_BUILTIN_ENTRY_LOADERS[str] = lambda path: _load_json_primitive(path, str)
_BUILTIN_ENTRY_LOADERS[bool] = lambda path: _load_json_primitive(path, bool)
```

**Type checking over silent coercion:** All four loaders use `isinstance` checking rather than type coercion. This prevents silent data corruption from externally modified files (e.g., `int(json.loads("42.5"))` silently truncating to `42`). If the JSON value doesn't match the expected type, the loader raises `TypeError` with a clear message.

**Note on `isinstance(True, int)`:** In Python, `bool` is a subclass of `int`, so `isinstance(True, int)` returns `True`. This means the `int` loader would accept booleans. However, in practice this only matters for externally crafted files -- ExitPoint roundtrips always produce the correct JSON type (`true`/`false` for bool, integer for int). The `bool` loader is checked first if the binding type is `bool`, and the `int` loader is only reached for `int` bindings where `true`/`false` would fail `isinstance(value, int)` -- wait, `isinstance(True, int)` is True. So we need the bool loader to handle this correctly. Since `json.loads("true")` returns `True` (a `bool`) and `isinstance(True, int)` is `True`, the int loader would accept `true`. This is an edge case from malformed files only; ExitPoint writes `true` for bool and `7` for int, never cross-types.

**Why add to `_BUILTIN_ENTRY_LOADERS` dict (not `_build_entry_loaders`):** `_BUILTIN_ENTRY_LOADERS` is the source of truth for both paths -- `_build_entry_loaders()` starts from a copy of it, and the executor uses it directly when `entry_loaders` is None. Adding to the source covers both paths.

**Annotation update:** The `_BUILTIN_ENTRY_LOADERS` type annotation is `Dict[type[BaseModel], Any]`. With primitives, the key type should be `Dict[type, Any]`. Update the annotation.

---

## Files Modified (Summary)

| File | Changes | Lines Affected |
|------|---------|---------------|
| `simkit/io/writers.py` | Add `write_json_primitive()` | After line 49 (new function) |
| `simkit/io/output_router.py` | Add 4 primitive handlers to `create_default_router()` | Lines 262-272 |
| `simkit/core/pipeline_executor.py` | Add `_PRIMITIVE_TYPES` constant (single source of truth) | New, near line 315 |
| `simkit/core/pipeline_executor.py` | Add primitive check in `_resolve_schema_type()` fallback | Lines 347-352 |
| `simkit/core/pipeline_executor.py` | Widen return type of `_resolve_schema_type()` | Line 320 |
| `simkit/core/pipeline_executor.py` | Spread `**_PRIMITIVE_TYPES` into `_build_schema_type_registry()` | Lines 451-460 |
| `simkit/core/pipeline_executor.py` | Add `_load_json_primitive()` helper and 4 primitive loaders to `_BUILTIN_ENTRY_LOADERS` | After line 568 |
| `simkit/core/pipeline_executor.py` | Widen `_BUILTIN_ENTRY_LOADERS` type annotation | Line 564 |

**No changes to:**
- `simkit/core/pipeline_validator.py` -- fallback gracefully skips; primitives have no fields
- `simkit/core/pipeline.py` -- wiring works as-is
- `simkit/config/pipeline_schema.py` -- type name parsing is string-based, already works

---

## Potential Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Primitive type name collides with future Pydantic schema named "float" | Extremely low | Medium | Primitive names are Python builtins; nobody would name a schema "float" |
| `json.dump(True)` writes `true` but `json.loads("True")` fails | Low | Low | Entry loader uses `json.loads` which expects JSON `true`, not Python `True`. This is correct JSON behavior. |
| `_build_schema_type_registry` rejects primitives as "not BaseModel" | None | N/A | Primitives are added via `**_PRIMITIVE_TYPES` spread in the static registry dict, not via the `custom_types` validation loop (lines 469-501). |
| `isinstance(True, int)` -- bool is subclass of int in Python | Very low | Very low | Only affects externally crafted files with cross-type values. ExitPoint roundtrips always produce the correct JSON type. |
| Existing test `len(registry) == 8` fails | Certain | None (test update) | Update to `len(registry) == 12` and add primitive assertions |

---

## Integration Strategy

### How This Fits Into the Existing System

Primitive support plugs into four existing extension points -- no new abstractions or mechanisms:

1. **WriteHandler registration** -- same pattern as `FinancialResults` handler
2. **Schema type registry** -- same dict, new entries
3. **Entry loaders** -- same dict, new entries
4. **Type resolution fallback** -- new check before existing `raise ValueError`

### Backward Compatibility

- Existing `RootModel[float]` pipelines unchanged -- handlers keyed by `"RootModel[float]"` still work
- Existing Pydantic model ExitPoint types unchanged
- `create_output_router_with_json_schemas()` still works identically
- All existing tests pass without modification (except the `len(registry) == 8` count)

---

## Validation Approach

### Unit Tests

**Test file:** `simkit/tests/io/test_output_router.py` (extend existing)

1. **`test_write_json_primitive_float`**: Write `42.0`, read file, verify content is `42.0`
2. **`test_write_json_primitive_int`**: Write `7`, read file, verify content is `7`
3. **`test_write_json_primitive_str`**: Write `"hello"`, read file, verify content is `"hello"`
4. **`test_write_json_primitive_bool`**: Write `True`, read file, verify content is `true`
5. **`test_default_router_has_primitive_handlers`**: `create_default_router().has_handler("float")` for all four
6. **`test_output_router_writes_primitive_float`**: Full OutputRouter.write_outputs() with float binding

**Test file:** `simkit/tests/core/test_custom_schema_registration.py` (extend existing)

7. **`test_schema_registry_includes_primitives`**: `_build_schema_type_registry()["float"]` is `float` for all four
8. **`test_all_user_facing_schemas_registered`**: Update expected count from 8 to 12
9. **`test_resolve_schema_type_primitives_with_registry`**: With registry, `_resolve_schema_type("float", registry)` returns `float`
10. **`test_resolve_schema_type_primitives_fallback`**: Without registry, `_resolve_schema_type("float", None)` returns `float`

**Test file:** `simkit/tests/core/test_custom_schema_registration.py` (extend existing)

11. **`test_primitive_entry_loaders_registered`**: `float in _BUILTIN_ENTRY_LOADERS` for all four
12. **`test_primitive_entry_loader_reads_float`**: Write `42.0` to temp JSON, load via loader, verify `float` type and value

### Integration Tests

**Test file:** `simkit/tests/test_toy_pipeline.py` (extend existing)

13. **`test_toy_pipeline_with_primitive_exit_type`**: Create a pipeline YAML that uses `float` as ExitPoint type (not `RootModel[float]`), execute to disk, verify JSON output file contains raw `42.0`
14. **`test_toy_pipeline_with_primitive_exit_in_memory`**: Same pipeline YAML, but execute with in-memory OutputRouter. Verify the manifest records the primitive ExitPoint binding correctly (produced=True, type_name="float").

Both tests require:
- A new YAML fixture (e.g., `toy_linear_primitive_exit.yaml`) that uses bare `float` in the ExitPoint
- A multi-output toy module that produces bare float fields (or reuse ToyDoublerModule but declare exit type as `float` with channel field extraction)

### Manual Verification

After implementation, verify the sysml-codegen E2E pipeline executes with multi-output `float` channels serialized to JSON.

---

**Next Step:** After approval -> `/_my_implement` or `/_my_plan`
