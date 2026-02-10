---
date: 2026-02-10T12:00:00+00:00
researcher: Claude
topic: "ExitPoint bare primitive type support for sysml-codegen multi-output modules"
tags: [research, exitpoint, primitives, output-router, sysml-codegen]
status: complete
last_updated: 2026-02-10
---

# Research: ExitPoint Bare Primitive Type Support

**Date**: 2026-02-10T12:00:00+00:00
**Researcher**: Claude
**Research Type**: Codebase / Architecture / Integration

## Research Question

The `sysml-codegen` project generates TEAx pipeline YAML where multi-output modules produce bare `float` values on channels. The generated ExitPoint declares `float` as the output type for these channels. TEAx currently has no write handler for bare primitive types (`float`, `int`, `str`, `bool`), causing `OutputRouterError: No writer registered for ExitPoint output type 'float'`. What TEAx changes are needed to support this?

**Source**: Bug 4 from `sysml-codegen/.project/active/codegen-bug-fixes/design.md` explicitly identifies this as a **TEAx fix, not sysml-codegen**.

## Summary

- **The gap is narrow and well-scoped**: TEAx's OutputRouter dispatch requires registered `WriteHandler` entries keyed by type name string. No handler exists for `"float"`, `"int"`, `"str"`, or `"bool"`.
- **Three code paths block bare primitives**: (1) `_validate_exit_module()` in `pipeline_validator.py:319` rejects unknown type names at validation time, (2) `_ensure_exit_handlers()` in `pipeline_executor.py:243` rejects at execution time, (3) `write_outputs()` in `output_router.py:98` rejects at write time.
- **The existing `write_json_payload()` writer can already serialize primitives** (it falls through to `json.dump(data, ...)` for non-BaseModel values). A new dedicated `write_json_primitive()` is cleaner but `write_json_payload` already works.
- **The fix requires changes to 3 files**: `writers.py` (new writer function), `output_router.py` (register primitive handlers in default router), and `pipeline_executor.py` (register primitive types in schema registry and entry loaders).
- **No changes needed to pipeline_validator.py** -- it delegates handler checks to `OutputRouter.has_handler()`, so registering handlers in the router is sufficient.

## Detailed Findings

### Why Multi-Output Modules Produce Bare Primitives

This is a fundamental architectural asymmetry in TEAx that was already documented:

**Single-output modules** (e.g., `ToyDoublerModule`):
- Return `ModuleResult[RootModel[float]]`
- Executor stores the **entire RootModel object** in the channel (`pipeline_executor.py:222-223`)
- Channel contains `RootModel[float](42.0)` -- a Pydantic model
- ExitPoint type is `RootModel[float]` -- has registered handler

**Multi-output modules** (e.g., a module using `MultiOutput`):
- Return `ModuleResult[MyMultiOutput]` where `MyMultiOutput` has fields like `value_a: float`
- Executor calls `data.to_channel_dict()` and stores **each extracted field** separately (`pipeline_executor.py:200-211`)
- Channel contains bare `42.0` -- a Python float
- ExitPoint type is `float` -- **no registered handler**

The sysml-codegen project generates modules of both kinds. CalcUsage modules with single outputs use `RootModel[float]`, but CalcUsage modules with multiple outputs produce bare `float` fields. The generated pipeline YAML correctly declares `float` for multi-output channels at the ExitPoint.

### Current Type Handler Registration

**Default router** (`output_router.py:250-273`):
```python
handlers = {
    "FinancialResults": WriteHandler(fn=writers.write_json_model, extension=".json"),
    "MockForecastSeries": WriteHandler(fn=writers.write_mock_forecast_series, extension=".json"),
    "SyncGuidanceSeries": WriteHandler(fn=writers.write_sync_guidance_series, extension=".json"),
}
```

**Custom schema router** (`output_router.py:276-343`):
- `create_output_router_with_json_schemas()` registers type names with `write_json_model`
- But `write_json_model` calls `model.model_dump()` which fails on bare primitives

**RootModel[float] pattern** (test_toy_pipeline.py:35-41):
```python
return create_output_router_with_json_schemas(
    ["RootModel[float]"],
    include_builtins=True,
)
```
This works because `RootModel[float]` is a Pydantic BaseModel and `model_dump()` succeeds.

### Three Validation Checkpoints That Block Primitives

1. **Pipeline Validator** (`pipeline_validator.py:319-328`):
   ```python
   if not self._output_router.has_handler(type_name):
       raise PipelineValidationError(
           "ExitPoint output type has no registered write handler", ...)
   ```

2. **Executor pre-check** (`pipeline_executor.py:236-246`):
   ```python
   if not self._output_router.has_handler(type_name):
       raise OutputRouterError(
           f"No writer registered for ExitPoint output type '{type_name}'")
   ```

3. **OutputRouter write** (`output_router.py:97-99`):
   ```python
   handler = self._type_handlers.get(type_name)
   if handler is None:
       raise OutputRouterError(f"No writer registered for type '{type_name}'")
   ```

All three check `has_handler(type_name)` which requires a registered handler for the type name string (e.g., `"float"`).

### Schema Type Registry Gap

The schema type registry (`pipeline_executor.py:404-501`) maps type name strings to type classes for EntryPoint loading and field reference validation. It currently only handles Pydantic BaseModel subclasses:

```python
registry = {
    "FinancialParams": schema.FinancialParams,
    "FinancialResults": schema.FinancialResults,
    # ... all BaseModel types
}
```

Bare primitives (`float`, `int`, `str`, `bool`) are not in this registry. The `_resolve_schema_type()` function (`pipeline_executor.py:317-352`) will raise `ValueError: Unknown schema type 'float'` if a primitive type name is encountered in an EntryPoint binding.

However, for the sysml-codegen use case, **primitives are only used at ExitPoint**, not EntryPoint. EntryPoint inputs are always Pydantic models (loaded from JSON files). So the schema type registry gap is less urgent but should still be addressed for completeness.

### Writer Function Analysis

**`write_json_model()`** (`writers.py:13-28`):
- Calls `model.model_dump(mode="json")` -- **fails on bare primitives** (AttributeError)
- Only works with Pydantic BaseModel instances

**`write_json_payload()`** (`writers.py:31-49`):
- Has `isinstance(payload, BaseModel)` check, falls through to `json.dump(data, ...)` for non-models
- **Already works with bare primitives** -- `json.dump(42.0, ...)` is valid JSON
- However, using this directly would serialize `42.0` as just `42.0` in the file (valid JSON but unusual for a file)

### What the Generated YAML Looks Like

From sysml-codegen, a multi-output CalcUsage might produce:

```yaml
modules:
  cost_calc:
    module_type: CostCalculator
    inputs:
      config: BatteryConfig battery_config
    outputs:
      total_cost: float total_cost
      labor_cost: float labor_cost

  exit:
    module_type: ExitPoint
    outputs:
      total_cost: float total_cost.json
      labor_cost: float labor_cost.json
```

The ExitPoint declares `float` as the type and expects to write it to `total_cost.json`.

## Code References

- `simkit/io/output_router.py:54-58` - `register_handler()` and `has_handler()` -- the dispatch mechanism
- `simkit/io/output_router.py:97-99` - Write-time handler lookup (raises OutputRouterError)
- `simkit/io/output_router.py:250-273` - `create_default_router()` -- only registers 3 Pydantic model handlers
- `simkit/io/output_router.py:276-343` - `create_output_router_with_json_schemas()` -- uses `write_json_model` (fails on primitives)
- `simkit/io/writers.py:13-28` - `write_json_model()` -- requires Pydantic BaseModel (calls `.model_dump()`)
- `simkit/io/writers.py:31-49` - `write_json_payload()` -- already handles non-model values via `json.dump()`
- `simkit/core/pipeline_executor.py:236-246` - `_ensure_exit_handlers()` -- pre-execution validation
- `simkit/core/pipeline_executor.py:317-352` - `_resolve_schema_type()` -- type name resolution (no primitives)
- `simkit/core/pipeline_executor.py:404-501` - `_build_schema_type_registry()` -- only BaseModel types
- `simkit/core/pipeline_validator.py:319-328` - Exit module validation rejects unregistered types
- `simkit/tests/test_toy_pipeline.py:35-41` - Current workaround using `RootModel[float]` handler

## Architecture Insights

### The Primitive Type Gap Is By-Design (Historical)

TEAx was originally designed around Pydantic model I/O. The entire pipeline system assumes outputs are Pydantic models:
- OutputRouter dispatches by type name (always a class `__name__`)
- Writers call `.model_dump()` for serialization
- EntryPoint loaders call `readers.read_json_model()` for deserialization

The `RootModel[float]` pattern was the intended solution for primitive values -- wrap them in Pydantic. This works for single-output modules where the entire RootModel object is stored in the channel.

The gap only manifests with **multi-output modules** where `MultiOutput.to_channel_dict()` extracts bare field values. This is a newer pattern (MultiOutput was added after the initial RootModel design).

### Consistency with Existing Patterns

The `custom_schema_types` parameter in `execute_pipeline()` already provides a precedent for auto-registering types:
1. Build schema type registry (`_build_schema_type_registry`)
2. Build entry loaders (`_build_entry_loaders`)
3. Build output router with JSON handlers (`create_output_router_with_json_schemas`)

Primitive types should follow the same three-step registration but with primitive-appropriate handlers.

### JSON Serialization Format Decision

For a bare `float` like `42.0`, there are two reasonable JSON formats:

**Option A: Raw value** -- `42.0` (valid JSON)
```json
42.0
```

**Option B: Wrapped value** -- `{"value": 42.0}`
```json
{
  "value": 42.0
}
```

**Recommendation: Raw value (Option A)**. This is the natural JSON serialization of a primitive and is consistent with how `RootModel[float].model_dump(mode="json")` behaves (returns `42.0`, not `{"root": 42.0}`). Using `json.dump(42.0, f)` is valid and produces the simplest, most interoperable output.

## Feasibility Assessment

**Can it be implemented?** Yes, straightforwardly.

**Effort estimate:** Small -- approximately 4 well-scoped changes across 3 files, plus tests.

**Risk:** Low. The changes are additive (new handlers, new registry entries). No existing behavior is modified. Existing tests will continue to pass because primitive types were previously rejected, so no existing code path relies on them.

**Backward compatibility:** Full. Adding handlers for new type names doesn't affect existing type names. Existing pipelines using `RootModel[float]` continue to work unchanged.

## Recommendations

### Proposed Changes

#### 1. Add `write_json_primitive()` to `writers.py`

```python
def write_json_primitive(value: float | int | str | bool, path: str | Path) -> Path:
    """Write a bare primitive value to a JSON file."""
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
    return resolved
```

This is cleaner than reusing `write_json_payload()` because:
- Explicit about what it handles (primitives only)
- No BaseModel check overhead
- Clear intent in OutputRouter handler registration

#### 2. Register primitive handlers in `create_default_router()` (`output_router.py`)

```python
PRIMITIVE_TYPE_NAMES = ("float", "int", "str", "bool")

def create_default_router(*, in_memory: bool = False) -> OutputRouter:
    handlers = {
        # ... existing Pydantic model handlers ...
        # Bare primitive handlers
        "float": WriteHandler(fn=writers.write_json_primitive, extension=".json"),
        "int": WriteHandler(fn=writers.write_json_primitive, extension=".json"),
        "str": WriteHandler(fn=writers.write_json_primitive, extension=".json"),
        "bool": WriteHandler(fn=writers.write_json_primitive, extension=".json"),
    }
    return OutputRouter(type_handlers=handlers, in_memory=in_memory)
```

This ensures primitives work with the default router (no custom setup needed).

#### 3. Register primitives in `_build_schema_type_registry()` (`pipeline_executor.py`)

Add primitive types to the built-in registry so `_resolve_schema_type("float")` returns `float`:

```python
registry: dict[str, type] = {
    # ... existing Pydantic types ...
    # Bare primitive types (for multi-output channels)
    "float": float,
    "int": int,
    "str": str,
    "bool": bool,
}
```

#### 4. Register primitive entry loaders in `_BUILTIN_ENTRY_LOADERS` (`pipeline_executor.py`)

For completeness (even though sysml-codegen doesn't use primitive EntryPoints):

```python
def _load_json_primitive(path: Path, type_cls: type) -> float | int | str | bool:
    """Load a bare primitive value from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return type_cls(data)

_BUILTIN_ENTRY_LOADERS.update({
    float: lambda path: _load_json_primitive(path, float),
    int: lambda path: _load_json_primitive(path, int),
    str: lambda path: _load_json_primitive(path, str),
    bool: lambda path: _load_json_primitive(path, bool),
})
```

### Testing Strategy

1. **Unit test `write_json_primitive()`**: Write float, int, str, bool to file, verify content
2. **Unit test primitive handler registration**: `create_default_router().has_handler("float")` is True
3. **Unit test schema type registry**: `_build_schema_type_registry()["float"]` is `float`
4. **Integration test**: Create a pipeline YAML with ExitPoint using `float` type, execute, verify JSON output
5. **Regression**: All existing tests pass (especially `test_toy_pipeline.py` with `RootModel[float]`)

### Implementation Order

1. `writers.py` -- Add `write_json_primitive()` (no dependencies)
2. `output_router.py` -- Register primitive handlers in `create_default_router()` (depends on writer)
3. `pipeline_executor.py` -- Add primitives to schema type registry and entry loaders
4. Tests -- Unit and integration tests

## Open Questions

1. **Should `create_output_router_with_json_schemas()` also auto-include primitives?** Currently it delegates to `create_default_router()` when `include_builtins=True`, so primitives would be included automatically. If `include_builtins=False`, primitives would NOT be available. Is this the right behavior? (Likely yes -- primitives are built-in, not custom schemas.)

2. **Should `_resolve_schema_type()` handle primitives when `type_registry` is None?** Currently it falls back to `getattr(schema, type_name, None)` which won't find `float` on the schema module. Adding explicit primitive handling in the fallback path ensures primitives work even without `custom_schema_types`. This is important because `execute_pipeline()` only builds `schema_type_registry` when `custom_schema_types is not None`.

3. **What about `list[float]` or other generic types?** For now, only the four basic primitives are needed. Generic container types can be addressed in a future enhancement if sysml-codegen produces them.
