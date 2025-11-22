# Custom Schema Registration for Pipeline Entry Points

## Overview

Enable external packages to use custom Pydantic schemas in pipeline EntryPoints with field reference support by adding a unified schema type registration mechanism to `execute_pipeline()`.

### Ticket and Research References

- `/home/reid/fusion_modeling/project/active/phase1_e2e_test/TEAX_ISSUE_custom_schema_registration.md`
- `simkit/core/pipeline_validator.py` - Type resolution for field references
- `simkit/core/pipeline_executor.py` - Entry artifact loading
- `simkit/io/output_router.py` - Existing pattern for custom schema registration (ExitPoint)

## Current Design

### Type Resolution Architecture

**Entry Point Validation** (simkit/core/pipeline_validator.py:82-126):
- `_build_channel_type_map()` constructs a mapping of channel names to type objects
- For EntryPoint modules: resolves types via `getattr(schema, binding.type_name)` (line 109)
- Hardcoded to `simkit.config.schema` module imported at line 7
- Custom schema AttributeError silently caught (line 111-114), causing validation failures later

**Entry Artifact Loading** (simkit/core/pipeline_executor.py:286-292):
- `_resolve_schema_type()` function resolves type name strings to type objects
- Uses `getattr(schema, type_name)` (line 290)
- Hardcoded to built-in schema module
- Raises `ValueError` for unknown types

**Entry Loader Registry** (simkit/core/pipeline_executor.py:356-393):
- Module-level `_ENTRY_LOADERS` dict maps type classes to loader functions
- Built-in loaders:
  - `read_json_model()` for Geography, FinancialParams, etc.
  - `read_parquet_load_profile()` for LoadProfile8760
  - Custom parser for PriceTrajectory
- No mechanism to register custom loaders from external packages

### Field Reference Validation Workflow

When a pipeline uses field references (e.g., `RootModel[float] power_balance_params.p_thermal_electric`):

1. **Build Channel Type Map**: Validator calls `_build_channel_type_map()` to resolve all output channel types
2. **EntryPoint Resolution**: For EntryPoint outputs, attempts `getattr(schema, type_name)`
3. **Custom Schema Failure**: Custom schemas not in `simkit.config.schema` fail silently (caught by except clause)
4. **Validation Error**: Later, field reference validation looks up parent type in `channel_types` dict
5. **Type Not Found**: Gets `None`, raises `PipelineValidationError` at line 365-370

### Existing Extension Point: OutputRouter

The system already provides custom schema support for **ExitPoint** outputs via `create_output_router_with_json_schemas()` (simkit/io/output_router.py:279-346):

- Accepts `custom_schema_types: list[str]` (type names)
- Auto-registers JSON write handlers for custom types
- No equivalent mechanism exists for EntryPoint inputs

**Key Limitation**: Custom schemas can be written at ExitPoint but cannot be read at EntryPoint or validated for field references.

## Proposed Design

Add unified custom schema type registration to `execute_pipeline()` that handles:
1. EntryPoint artifact loading (type resolution + loader registration)
2. Field reference validation (channel type map building)
3. ExitPoint output writing (automatic OutputRouter creation)

### API Signature Change

**Updated `execute_pipeline()` signature** (simkit/core/pipeline.py:65):

```python
def execute_pipeline(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
    registry: PipelineModuleRegistry | None = None,
    output_router: OutputRouter | None = None,
    custom_schema_types: list[type] | None = None,  # NEW
) -> RunResult:
    """Execute pipeline with optional custom module registry and schema types.

    Args:
        spec_path: Path to pipeline YAML specification
        output_dir: Optional output directory (defaults to temp dir)
        registry: Optional custom module registry. If None, uses built-in TEAx modules.
        output_router: Optional custom output router. If None and custom_schema_types
                      provided, auto-creates router with custom types. If both None,
                      uses default router with built-in schemas only.
        custom_schema_types: Optional list of custom Pydantic schema type classes.
                           Enables custom schemas for EntryPoint loading, field
                           reference validation, and ExitPoint writing. All custom
                           types default to JSON serialization (read_json_model/
                           write_json_model). If None, only built-in TEAx schemas
                           are available.

    Returns:
        RunResult with execution outputs, metadata, and provenance
    """
```

### Type Resolution Enhancement

**New Helper: Schema Type Registry Builder** (simkit/core/pipeline_executor.py):

```python
def _build_schema_type_registry(
    custom_types: list[type] | None = None
) -> dict[str, type]:
    """Build unified schema type lookup from built-ins and custom types.

    Args:
        custom_types: Optional list of custom schema type classes

    Returns:
        Dict mapping type name strings to type objects

    Example:
        >>> registry = _build_schema_type_registry([PowerBalanceParams])
        >>> registry["PowerBalanceParams"]
        <class 'PowerBalanceParams'>
        >>> registry["Geography"]  # Built-in
        <class 'simkit.config.schema.Geography'>
    """
```

Replaces hardcoded `getattr(schema, type_name)` pattern with dictionary lookup.

**Updated `_resolve_schema_type()` signature** (simkit/core/pipeline_executor.py:286):

```python
def _resolve_schema_type(
    type_name: str | None,
    type_registry: dict[str, type],  # NEW parameter
) -> type[schema.StrictBaseModel]:
    """Resolve type name to type object using provided registry.

    Args:
        type_name: String name of schema type
        type_registry: Mapping of type names to type objects

    Returns:
        Resolved type object

    Raises:
        ValueError: If type_name is None or not in registry
    """
```

### Entry Loader Auto-Registration

**Enhanced `_build_entry_loaders()` function** (simkit/core/pipeline_executor.py):

```python
def _build_entry_loaders(
    custom_types: list[type] | None = None
) -> dict[type, Callable[[Path], Any]]:
    """Build entry loader registry from built-ins and custom types.

    All custom types default to read_json_model() unless they have special
    requirements (e.g., Parquet, custom parsing). Future enhancement could
    add custom_entry_loaders parameter for override.

    Args:
        custom_types: Optional list of custom schema type classes

    Returns:
        Dict mapping type objects to loader functions
    """
    loaders = dict(_BUILTIN_ENTRY_LOADERS)  # Copy built-ins

    if custom_types:
        for type_cls in custom_types:
            # Auto-register with generic JSON loader
            loaders[type_cls] = lambda path, cls=type_cls: readers.read_json_model(path, cls)

    return loaders
```

**Rename existing `_ENTRY_LOADERS`** → `_BUILTIN_ENTRY_LOADERS` for clarity.

### Validator Type Registry Integration

**Updated `PipelineValidator.__init__()` signature** (simkit/core/pipeline_validator.py:38):

```python
def __init__(
    self,
    registry: PipelineModuleRegistry,
    output_router: OutputRouter,
    schema_type_registry: dict[str, type] | None = None,  # NEW
) -> None:
    """Initialize validator with module registry and optional schema type registry.

    Args:
        registry: Module registry for validation
        output_router: Output router for exit point validation
        schema_type_registry: Optional mapping of schema type names to type objects.
                            If None, uses built-in simkit.config.schema types only.
    """
    self._registry = registry
    self._output_router = output_router
    self._schema_type_registry = schema_type_registry
    self._builder = PipelineDagBuilder()
```

**Updated `_build_channel_type_map()` logic** (simkit/core/pipeline_validator.py:104-114):

```python
if module_spec.is_entry:
    # Entry module: types come from artifact bindings (resolve from registry)
    for binding in module_spec.outputs.values():
        if binding.type_name is not None:
            if self._schema_type_registry is not None:
                # Use custom schema registry
                type_obj = self._schema_type_registry.get(binding.type_name)
                if type_obj is None:
                    # Not in custom registry, skip (will error later if used)
                    continue
            else:
                # Backward compat: fall back to built-in schema module
                try:
                    type_obj = getattr(schema, binding.type_name)
                except AttributeError:
                    continue

            channel_types[binding.channel_name] = type_obj
```

### Automatic OutputRouter Creation

**Enhanced router logic in `execute_pipeline()`** (simkit/core/pipeline.py:106-108):

```python
# Use custom router if provided, otherwise auto-create from custom_schema_types
if output_router is None and custom_schema_types is not None:
    # Auto-create router with custom types + built-ins
    type_name_strings = [t.__name__ for t in custom_schema_types]
    router = create_output_router_with_json_schemas(
        type_name_strings,
        include_builtins=True,
    )
elif output_router is None:
    # No custom types, use default built-in router
    router = create_default_router()
else:
    # User provided explicit router, use as-is
    router = output_router
```

### Executor Integration

**Updated `SerialPipelineExecutor` initialization** (simkit/core/pipeline_executor.py:71-79):

Store schema type registry and entry loaders as instance attributes:

```python
def __init__(
    self,
    registry: PipelineModuleRegistry | None = None,
    *,
    output_router: OutputRouter | None = None,
    schema_type_registry: dict[str, type] | None = None,  # NEW
    entry_loaders: dict[type, Callable] | None = None,  # NEW
) -> None:
    self._registry = registry or PipelineModuleRegistry.from_static_modules()
    self._output_router = output_router or create_default_router()
    self._schema_type_registry = schema_type_registry
    self._entry_loaders = entry_loaders or dict(_BUILTIN_ENTRY_LOADERS)
    self._validator = PipelineValidator(
        self._registry,
        self._output_router,
        schema_type_registry=schema_type_registry,
    )
```

**Updated `_load_entry_binding()` signature** (simkit/core/pipeline_executor.py:225):

```python
def _load_entry_binding(
    self,
    module_key: str,
    binding: PipelineChannelBinding,
    base_dir: Path,
) -> tuple[Any, Path]:
    # ... path resolution logic unchanged ...

    # Use instance registries instead of module-level lookups
    type_cls = _resolve_schema_type(binding.type_name, self._schema_type_registry)
    loader = self._entry_loaders.get(type_cls)
    if loader is None:
        raise ValueError(f"No loader registered for entry binding type '{binding.type_name}'")
    return loader(resolved_path), resolved_path
```

### Usage Example

**External package (fusion_simkit) using custom schemas:**

```python
# fusion_simkit/schemas/power_balance_params.py
from simkit.config.schema import StrictBaseModel

class PowerBalanceParams(StrictBaseModel):
    """Custom fusion parameter group."""
    p_thermal_electric: float
    f_pcppf: float
    p_input: float

# fusion_simkit/__init__.py
from simkit.core.registry_builder import create_registry
from .modules import CoolantPumpPowerModule
from .schemas import PowerBalanceParams, PlasmaParams

def create_fusion_simkit_registry():
    """Create module registry with fusion modules."""
    return create_registry([CoolantPumpPowerModule], include_builtins=True)

# User script
from simkit.core.pipeline import execute_pipeline
from fusion_simkit import create_fusion_simkit_registry
from fusion_simkit.schemas import PowerBalanceParams, PlasmaParams

result = execute_pipeline(
    spec_path="fusion_simkit/pipelines/catf_fusion.yaml",
    output_dir="outputs/",
    registry=create_fusion_simkit_registry(),
    custom_schema_types=[PowerBalanceParams, PlasmaParams],  # NEW
)
```

**Pipeline YAML with field references:**

```yaml
modules:
  entry_fusion:
    module_type: EntryPoint
    inputs:
      power_balance_params: PowerBalanceParams power_balance_params.json
    outputs:
      power_balance_params: PowerBalanceParams power_balance_params

  coolantpumppower:
    module_type: CoolantPumpPowerModule
    inputs:
      p_thermal_electric: RootModel[float] power_balance_params.p_thermal_electric  # Works!
    outputs:
      pump_power: RootModel[float] coolantpumppower_pump_power

  exit_point:
    module_type: ExitPoint
    outputs:
      pump_power: RootModel[float] pump_power.json  # Auto-writes via router
```

**Data Flow:**

1. User calls `execute_pipeline()` with `custom_schema_types=[PowerBalanceParams]`
2. `_build_schema_type_registry()` creates unified type lookup
3. `_build_entry_loaders()` auto-registers `PowerBalanceParams` with `read_json_model()`
4. Auto-creates OutputRouter with PowerBalanceParams write handler
5. Validator `_build_channel_type_map()` resolves `PowerBalanceParams` from registry
6. Field reference `power_balance_params.p_thermal_electric` validates successfully
7. Executor loads `power_balance_params.json` using registered loader
8. Runtime field extraction works (already functional)
9. ExitPoint writes outputs using auto-created router

## Implementation Benefits

- **Unblocks external users**: Fusion modeling and other domain packages can use custom schemas
- **Consistent API pattern**: Mirrors existing `registry` parameter for modules
- **Minimal code duplication**: Single `custom_schema_types` parameter handles all three systems
- **Backward compatible**: Defaults to built-in schemas when parameter omitted
- **Smart defaults**: 90% use case (JSON schemas) works automatically
- **Future extensible**: Can add `custom_entry_loaders` parameter later if needed
- **Type-safe**: Uses actual type objects, not strings (IDE autocomplete, prevents typos)
- **Self-documenting**: Type list explicitly shows what schemas pipeline depends on

## Potential Risks

### Name Collision Risk

**Scenario**: Custom schema has same `__name__` as built-in schema

```python
# External package defines:
class Geography(StrictBaseModel):
    # Different fields than simkit.config.schema.Geography
    pass

# User passes:
custom_schema_types=[Geography]  # Which Geography?
```

**Mitigation**: Type registry builder should check for collisions and raise clear error. Built-in schemas take precedence by default, or require explicit override flag.

**Test**: Collision detection in `_build_schema_type_registry()` with helpful error message listing conflicting names.

---

### Entry Loader Mismatch

**Scenario**: Custom schema requires special loader (e.g., Parquet, CSV, custom JSON format) but auto-registers with `read_json_model()`

```python
class CustomParquetSchema(StrictBaseModel):
    # Needs read_parquet_custom() not read_json_model()
    pass
```

**Current Design**: No override mechanism (Decision 2: Option A)

**Mitigation**: Document in error message when loading fails. Future enhancement: add `custom_entry_loaders: dict[type, Callable]` parameter.

**Test**: Verify clear error message when loader fails (e.g., JSON parsing error on Parquet file).

---

### OutputRouter Override Confusion

**Scenario**: User passes both `output_router` and `custom_schema_types`

```python
execute_pipeline(
    ...,
    output_router=my_router,  # Explicit router
    custom_schema_types=[CustomSchema],  # Expects auto-registration
)
```

**Behavior**: Explicit `output_router` takes precedence, `custom_schema_types` only affects EntryPoint/validation.

**Mitigation**: Document clearly in docstring. Consider warning log if both provided and router doesn't have handlers for custom types.

**Test**: Verify explicit router used when both parameters provided.

---

### Optional Field Reference Runtime Error

**Scenario**: Field reference targets Optional field that is None at runtime

```python
class ParentSchema(StrictBaseModel):
    optional_field: float | None = None

# YAML: inputs: { value: "RootModel[float] parent.optional_field" }
# Runtime: parent.optional_field is None
```

**Behavior**: Executor raises `PipelineExecutionError` (already implemented at line 333-337)

**Risk**: Validation passes (field exists, type matches) but runtime fails.

**Mitigation**: Existing runtime check is correct. Document that Optional fields must have non-None values when used in field references.

**Test**: Existing test coverage in `test_optional_field_none_runtime_error()` (simkit/tests/test_pipeline_field_reference_e2e.py:228-259).

---

### Missing Type in Custom List

**Scenario**: Pipeline YAML references custom schema not in `custom_schema_types` list

```yaml
entry_point:
  inputs:
    forgotten_schema: ForgottenSchema data.json  # Not in custom_schema_types
```

**Behavior**: Type resolution fails with `ValueError` or validation error

**Mitigation**: Clear error message identifying missing type and suggesting addition to `custom_schema_types` list.

**Test**: Verify helpful error message when EntryPoint references unregistered custom type.
