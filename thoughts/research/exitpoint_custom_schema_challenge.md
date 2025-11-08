# ExitPoint Custom Schema Challenge

## Executive Summary

**Problem**: While the recent custom module registration work enables external packages to register modules via `execute_pipeline(registry=...)`, there are **two hard dependencies** that prevent ExitPoint from working with custom schemas:

1. **Schema validation** hardcoded to `simkit.config.schema` module
2. **Output router** only has write handlers for built-in types

This blocks external packages like `fusion_modeling` from persisting custom output types through ExitPoint.

## The Registration Gap

### What Works (Modules) ✅

The custom module registration implementation (`registry_builder.py`) successfully allows external packages to register modules:

```python
# External package creates registry
from fusion_simkit import create_fusion_registry
from simkit.core.pipeline import execute_pipeline

registry = create_fusion_registry()  # Contains custom modules
result = execute_pipeline("fusion_pipeline.yaml", "outputs/", registry=registry)
```

**File**: `/home/reid/teax/simkit/core/pipeline.py:62-98`

### What Breaks (ExitPoint Schema) ❌

ExitPoint validation fails for custom schemas at **two checkpoints**:

## Checkpoint 1: Schema Type Validation

**File**: `/home/reid/teax/simkit/core/pipeline_validator.py:113-118`

```python
if not hasattr(schema, type_name):
    raise PipelineValidationError(
        "ExitPoint output references unknown schema type",
        module=module.key,
        details={"output": field, "type": type_name},
    )
```

**Problem**: This uses `hasattr(schema, type_name)` where `schema` is hardcoded to `simkit.config.schema`.

**Impact**: Custom schema types like `FusionParams` from external packages are **always rejected**, even if they're valid Pydantic models.

**Example failure**:
```yaml
exit_point:
  module_type: ExitPoint
  outputs:
    fusion_params: FusionParams fusion_params.json  # ❌ Fails validation
```

Error: `"ExitPoint output references unknown schema type: FusionParams"`

## Checkpoint 2: Output Router Handler Registration

**File**: `/home/reid/teax/simkit/core/pipeline_executor.py:183-193`

```python
def _ensure_exit_handlers(self, module_spec: PipelineModuleSpec) -> None:
    for binding in module_spec.outputs.values():
        type_name = binding.type_name
        if type_name is None:
            raise OutputRouterError(
                f"ExitPoint binding '{binding.channel_name}' is missing a type declaration"
            )
        if not self._output_router.has_handler(type_name):
            raise OutputRouterError(
                f"No writer registered for ExitPoint output type '{type_name}'"
            )
```

**Problem**: The default output router only has handlers for built-in TEAx types.

**Default router handlers** (`output_router.py:144-166`):
```python
handlers: MutableMapping[str, WriteHandler] = {
    schema.RateInfo.__name__: WriteHandler(fn=writers.write_json_model, extension=".json"),
    schema.BatteryConfig.__name__: WriteHandler(fn=writers.write_json_model, extension=".json"),
    schema.CostBreakdown.__name__: WriteHandler(fn=writers.write_json_model, extension=".json"),
    schema.FinancialResults.__name__: WriteHandler(fn=writers.write_json_model, extension=".json"),
    schema.BatteryTelemetry8760.__name__: WriteHandler(fn=writers.write_parquet_telemetry, extension=".parquet"),
    # ... etc for built-in types only
}
```

**Impact**: Even if schema validation passes, ExitPoint execution fails because there's no write handler registered for `FusionParams`.

## Current Workaround in fusion_modeling

The fusion_modeling team is **aware** of this limitation. Evidence from their pipeline:

**File**: `/home/reid/fusion_modeling/tests/teax_simkit/fixtures/fusion_pipeline.yaml:54-60`

```yaml
exit_point:
  module_type: ExitPoint
  outputs:
    fusion_params: FusionParams fusion_params.json

# Comment in file (lines 55-56):
# NOTE: ExitPoint requires schema types, not primitives
# GAP: Need wrapper schemas for float outputs or skip ExitPoint for Phase 4
```

They've defined custom schemas (`fusion_schemas.py`) but cannot use them:

**File**: `/home/reid/fusion_modeling/tests/teax_simkit/fusion_schemas.py:10-35`

```python
class FusionParams(BaseModel):
    """Fusion reactor parameters for Phase 0 validation."""
    p_fusion: float = Field(..., gt=0, description="Total fusion power [MW]")
    p_input: float = Field(..., gt=0, description="Auxiliary heating power [MW]")
    # ... etc

# Re-export module Output types for use in ExitPoint
from tests.teax_simkit.modules.alphaneutronsplit import AlphaNeutronSplitOutput
from tests.teax_simkit.modules.blanketthermalpower import BlanketThermalPowerOutput
from tests.teax_simkit.modules.grosselectricpower import GrossElectricPowerOutput
```

These schemas are **structurally valid** (they inherit from `BaseModel`), but the pipeline system **cannot recognize or persist them**.

## Why This Matters

### Scope Correctness from Original Spec

The original custom module registration spec explicitly stated:

**File**: `/home/reid/teax/thoughts/specs/custom-module-package-registration.md:78-97`

```markdown
### Out of Scope
- Global registry pattern (deferred as Option B future enhancement)
- Entry point auto-discovery via Python entry points (deferred as Option C future enhancement)
- Creating or modifying the `PipelineModuleRegistry` class itself (already exists in TEAx)
- Auto-generating registry creation code in code generators (that's fusion_modeling Phase 1+)
- Merging multiple registries together
- Advanced validation (type compatibility checking, circular dependency detection, semantic validation)
- **Registry versioning or migration**
- Hot-reloading of registry during execution
```

**However**: Schema registration was **not explicitly listed** as out-of-scope, which suggests it was **overlooked** rather than deferred.

### Data Flow Analysis

Custom modules work fine for **intermediate channels**:

```yaml
alpha_neutron_split:
  module_type: AlphaNeutronSplitModule
  inputs:
    fusion_params: FusionParams fusion_params  # ✅ Works fine
  outputs:
    p_alpha: float p_alpha  # ✅ Routing works
    p_neutron: float p_neutron  # ✅ Routing works

gross_electric:
  module_type: GrossElectricPowerModule
  inputs:
    p_alpha: float p_alpha  # ✅ Can consume custom outputs
```

**Reference**: `/home/reid/fusion_modeling/tests/teax_simkit/fixtures/fusion_pipeline.yaml:25-52`

The pipeline can route custom types **between modules** without issues because:
- Channel routing is type-agnostic (just stores Python objects)
- Module introspection extracts type metadata from module class definitions
- Validation only checks that YAML types match ModuleDescriptor types

**The ONLY place** where the system needs to "know about" schema types is **ExitPoint**.

## Technical Root Cause

### Architecture Decision: ExitPoint as Special Case

ExitPoint is intentionally **not a regular module**. Looking at the validator:

**File**: `/home/reid/teax/simkit/core/pipeline_validator.py:44-46`

```python
if module.is_exit:
    self._validate_exit_module(module)
    continue
```

ExitPoint doesn't have:
- A `ModuleDescriptor` in the registry
- Input/output type introspection from module classes
- A factory function

Instead, its validation is **hardcoded** to check against the `simkit.config.schema` module.

### Why Was It Done This Way?

Examining the ExitPoint validation logic (`_validate_exit_module`), the system needs to:

1. **Verify type names exist** before execution (fail-fast)
2. **Ensure write handlers are available** for those types
3. **Validate filename constraints** (no duplicates, no paths)

The `hasattr(schema, type_name)` check serves as a **namespace guard**: it ensures that all ExitPoint type declarations refer to known, validated Pydantic models from the TEAx schema module.

This was likely done for:
- **Safety**: Catch typos in type names early
- **Consistency**: All schemas come from a single source of truth
- **Writer registration**: Schema module and output router handlers are kept in sync

## Design Options

### Option A: Schema Namespace Parameter

**Approach**: Allow users to pass a custom schema module/namespace to the validator.

**Implementation**:
```python
def execute_pipeline(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
    registry: PipelineModuleRegistry | None = None,
    schema_namespace: object | None = None,  # New parameter
) -> RunResult:
    # ...
    validator = PipelineValidator(registry, schema_namespace=schema_namespace)
```

**Validator changes**:
```python
class PipelineValidator:
    def __init__(
        self,
        registry: PipelineModuleRegistry,
        schema_namespace: object | None = None
    ) -> None:
        self._registry = registry
        self._schema_namespace = schema_namespace or schema  # Default to simkit.config.schema

    def _validate_exit_module(self, module: PipelineModuleSpec) -> None:
        # ...
        if not hasattr(self._schema_namespace, type_name):
            raise PipelineValidationError(
                "ExitPoint output references unknown schema type",
                # ...
            )
```

**Pros**:
- Simple, minimal code change
- Clear separation: modules via registry, schemas via namespace
- Backward compatible (defaults to built-in schema)

**Cons**:
- User must maintain a module with all schema classes (awkward for scattered schemas)
- Doesn't solve output router handler registration
- Two separate registration mechanisms (registry + schema_namespace)

### Option B: Schema Registry with Output Router

**Approach**: Create a `SchemaRegistry` class that bundles type validation + write handlers.

**Implementation**:
```python
@dataclass
class SchemaRegistration:
    type_class: type[BaseModel]
    write_handler: WriteHandler

class SchemaRegistry:
    def __init__(self):
        self._schemas: Dict[str, SchemaRegistration] = {}

    def register(self, name: str, type_class: type[BaseModel], handler: WriteHandler):
        self._schemas[name] = SchemaRegistration(type_class, handler)

    def has_schema(self, name: str) -> bool:
        return name in self._schemas

    def get_type(self, name: str) -> type[BaseModel]:
        return self._schemas[name].type_class

    def get_handler(self, name: str) -> WriteHandler:
        return self._schemas[name].write_handler

def execute_pipeline(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
    registry: PipelineModuleRegistry | None = None,
    schema_registry: SchemaRegistry | None = None,  # New parameter
) -> RunResult:
    # ...
```

**Validator changes**:
```python
def _validate_exit_module(self, module: PipelineModuleSpec) -> None:
    # ...
    if not self._schema_registry.has_schema(type_name):
        raise PipelineValidationError(
            "ExitPoint output references unknown schema type",
            # ...
        )
```

**Pros**:
- Single registration point for schema type + writer
- Extensible: can add more metadata (version, deprecation, etc.)
- Mirrors the `PipelineModuleRegistry` design pattern
- Clean separation from module registry

**Cons**:
- More upfront design/implementation work
- Adds a new abstraction layer
- User must register schemas explicitly (can't reuse existing Pydantic models directly)

### Option C: Relaxed Validation with Convention-Based Writers

**Approach**: Remove schema namespace check entirely; use duck typing + conventional write handlers.

**Implementation**:
```python
def _validate_exit_module(self, module: PipelineModuleSpec) -> None:
    # ...
    # REMOVE the hasattr(schema, type_name) check
    # Trust that if a channel exists with that type, it's valid
```

**Output router changes**:
```python
def write_outputs(self, ...):
    # ...
    handler = self._type_handlers.get(type_name)
    if handler is None:
        # Fallback to generic JSON writer for any BaseModel
        if isinstance(payload, BaseModel):
            handler = WriteHandler(fn=writers.write_json_model, extension=".json")
        else:
            raise OutputRouterError(f"No writer registered for type '{type_name}'")
```

**Pros**:
- Minimal code change
- Works with any Pydantic model automatically
- No explicit registration required

**Cons**:
- Loses fail-fast validation (typos only caught at execution time)
- Cannot enforce custom write handlers (everything becomes JSON)
- Loses ability to validate extension matches handler (e.g., `.parquet` for telemetry)
- Less explicit, harder to debug

### Option D: Merge Schema into Module Registry (Single Registry Pattern)

**Approach**: Extend `ModuleDescriptor` to optionally include schema registrations.

**Implementation**:
```python
@dataclass
class ModuleDescriptor:
    module_type: str
    factory: Callable[[], ModuleBase]
    required_inputs: Dict[str, type[BaseModel]]
    optional_inputs: Dict[str, type[BaseModel]]
    outputs: Dict[str, type[BaseModel]]
    version: str
    # NEW: Optional schema + handler for ExitPoint compatibility
    exit_schema: type[BaseModel] | None = None
    exit_handler: WriteHandler | None = None

class PipelineModuleRegistry:
    def register_exit_schema(self, type_name: str, schema_class: type[BaseModel], handler: WriteHandler):
        """Register a schema type for use in ExitPoint."""
        # Store in separate internal dict
        self._exit_schemas[type_name] = (schema_class, handler)

    def has_exit_schema(self, type_name: str) -> bool:
        return type_name in self._exit_schemas
```

**Usage**:
```python
registry = create_registry([MyModule])
registry.register_exit_schema(
    "FusionParams",
    FusionParams,
    WriteHandler(fn=writers.write_json_model, extension=".json")
)
result = execute_pipeline("pipeline.yaml", "outputs/", registry=registry)
```

**Pros**:
- Single registry object (easier for users)
- Consistent with existing module registration pattern
- Can extend `create_registry()` to auto-register module I/O types for ExitPoint

**Cons**:
- Registry becomes more complex (handles both modules and schemas)
- Naming collision risk (module_type vs schema type names)
- Not as clean separation of concerns

## Recommended Solution: Option B (Schema Registry)

### Rationale

1. **Mirrors existing pattern**: Just as we have `PipelineModuleRegistry` for modules, we create `SchemaRegistry` for schemas
2. **Clean separation**: Modules are about computation; schemas are about data persistence
3. **Extensibility**: Schema registry can grow to include validation rules, migration logic, etc.
4. **Explicit registration**: Users clearly declare what can be persisted, avoiding surprises
5. **Type safety**: Maintains the fail-fast validation guarantee

### Implementation Plan

**Phase 1: Core Registry**
1. Create `SchemaRegistry` class in `simkit/core/schema_registry.py`
2. Add `schema_registry` parameter to `execute_pipeline()`
3. Update `PipelineValidator._validate_exit_module()` to check schema registry
4. Update `SerialPipelineExecutor._ensure_exit_handlers()` to use schema registry handlers

**Phase 2: Builder Helper**
1. Create `create_schema_registry()` helper in `simkit/core/registry_builder.py`
2. Pattern:
   ```python
   def create_schema_registry(
       schemas: Dict[str, type[BaseModel]],
       handlers: Dict[str, WriteHandler] | None = None,
       include_builtins: bool = False,
   ) -> SchemaRegistry:
       # ...
   ```

**Phase 3: Auto-Registration from Modules**
1. Extend `create_registry()` to optionally extract and register module I/O types
2. Pattern:
   ```python
   def create_registry(
       modules: List[Type[ModuleBase]],
       auto_register_schemas: bool = False,  # New param
   ) -> tuple[PipelineModuleRegistry, SchemaRegistry]:
       # ...
       if auto_register_schemas:
           # Extract input/output types from module introspection
           # Auto-create schema registry with JSON handlers
       # ...
   ```

### Usage Example

**External package code** (`fusion_simkit/registry.py`):
```python
from simkit.core.registry_builder import create_registry, create_schema_registry
from simkit.io.output_router import WriteHandler
from simkit.io import writers
from tests.teax_simkit.fusion_schemas import (
    FusionParams,
    AlphaNeutronSplitOutput,
    BlanketThermalPowerOutput,
    GrossElectricPowerOutput,
)
from tests.teax_simkit.modules.alphaneutronsplit import AlphaNeutronSplitModule
from tests.teax_simkit.modules.blanketthermalpower import BlanketThermalPowerModule
from tests.teax_simkit.modules.grosselectricpower import GrossElectricPowerModule

def create_fusion_registry():
    """Create module registry for fusion pipeline."""
    return create_registry([
        AlphaNeutronSplitModule,
        BlanketThermalPowerModule,
        GrossElectricPowerModule,
    ])

def create_fusion_schema_registry():
    """Create schema registry for fusion data types."""
    schemas = {
        "FusionParams": FusionParams,
        "AlphaNeutronSplitOutput": AlphaNeutronSplitOutput,
        "BlanketThermalPowerOutput": BlanketThermalPowerOutput,
        "GrossElectricPowerOutput": GrossElectricPowerOutput,
    }
    # Use default JSON handler for all (can override per-type if needed)
    handlers = {
        name: WriteHandler(fn=writers.write_json_model, extension=".json")
        for name in schemas.keys()
    }
    return create_schema_registry(schemas, handlers, include_builtins=True)
```

**User code**:
```python
from fusion_simkit import create_fusion_registry, create_fusion_schema_registry
from simkit.core.pipeline import execute_pipeline

module_registry = create_fusion_registry()
schema_registry = create_fusion_schema_registry()

result = execute_pipeline(
    "fusion_pipeline.yaml",
    "outputs/",
    registry=module_registry,
    schema_registry=schema_registry,
)
```

### Backward Compatibility

**Default behavior** (no schema_registry provided):
```python
# In execute_pipeline()
if schema_registry is None:
    schema_registry = create_default_schema_registry()

# In simkit/core/schema_registry.py
def create_default_schema_registry() -> SchemaRegistry:
    """Create registry with built-in TEAx schemas."""
    from ..config import schema
    from ..io import writers

    registry = SchemaRegistry()

    # Register all built-in types
    registry.register("RateInfo", schema.RateInfo,
                     WriteHandler(fn=writers.write_json_model, extension=".json"))
    registry.register("BatteryConfig", schema.BatteryConfig,
                     WriteHandler(fn=writers.write_json_model, extension=".json"))
    # ... etc for all built-in types

    return registry
```

**Result**: Existing code continues to work without modification.

## Estimated Implementation Effort

### Phase 1: Core Registry (Required for MVP)
- **Effort**: 0.5-1 day
- **Files**:
  - NEW: `simkit/core/schema_registry.py` (~80 lines)
  - MODIFY: `simkit/core/pipeline.py` (~10 lines)
  - MODIFY: `simkit/core/pipeline_validator.py` (~15 lines)
  - MODIFY: `simkit/core/pipeline_executor.py` (~20 lines)
  - NEW: `simkit/tests/core/test_schema_registry.py` (~150 lines)

### Phase 2: Builder Helper (Convenience)
- **Effort**: 0.25 day
- **Files**:
  - MODIFY: `simkit/core/registry_builder.py` (~50 lines)
  - MODIFY: `simkit/tests/core/test_registry_builder.py` (~80 lines)

### Phase 3: Auto-Registration (Future Enhancement)
- **Effort**: 0.5 day
- **Files**:
  - MODIFY: `simkit/core/registry_builder.py` (~100 lines)
  - MODIFY: `simkit/tests/core/test_registry_builder.py` (~120 lines)

**Total effort**: 1.25-1.75 days for Phases 1+2 (MVP usable by fusion_modeling)

## Acceptance Criteria

The solution is complete when:

1. **fusion_modeling pipeline executes successfully**:
   ```python
   result = execute_pipeline(
       "fusion_pipeline.yaml",
       "outputs/",
       registry=fusion_module_registry,
       schema_registry=fusion_schema_registry,
   )
   assert result.manifest is not None
   assert (result.run_dir / "fusion_params.json").exists()
   ```

2. **Custom schemas validated correctly**:
   - ExitPoint with `FusionParams` passes validation
   - Custom write handlers are invoked
   - Output files contain serialized custom types

3. **Backward compatibility maintained**:
   - All existing TEAx pipeline tests pass
   - `execute_pipeline(path, output_dir)` works without schema_registry parameter
   - Built-in schemas continue to work as before

4. **Clear error messages**:
   - Missing schema: "ExitPoint output 'foo' references unregistered schema type 'Bar'"
   - Missing handler: "No write handler registered for schema type 'Bar'"
   - Type mismatch: (if validation is extended later)

5. **Documentation complete**:
   - Usage example in CLAUDE.md
   - Docstrings for `SchemaRegistry` class
   - Migration guide for external packages

## Alternative: Defer to Future Work?

### If we decide NOT to implement this now:

**Workaround for fusion_modeling**:
1. Skip ExitPoint in pipeline YAML
2. Manually persist outputs in test code:
   ```python
   result = execute_pipeline("fusion_pipeline.yaml", None, registry=...)
   fusion_params = result.outputs["fusion_params"]
   with open("outputs/fusion_params.json", "w") as f:
       json.dump(fusion_params.model_dump(), f)
   ```

**Document as known limitation**:
- Add to CLAUDE.md: "ExitPoint currently only supports built-in TEAx schema types"
- Add to custom-module-package-registration.md under "Known Limitations"
- Create a ticket for future work: "Implement schema registration for custom ExitPoint types"

**Pros of deferring**:
- Reduces immediate scope
- Allows fusion_modeling to proceed with manual workaround
- Gives time to observe usage patterns before committing to design

**Cons of deferring**:
- Incomplete solution (modules work, but ExitPoint doesn't)
- Manual output persistence defeats purpose of pipeline system
- Confusion for external package authors ("Why can I register modules but not schemas?")
- Technical debt accumulates

## Recommendation: Implement Now (Phases 1+2)

**Rationale**:
1. **Small incremental cost**: Only ~1.25 days additional work on top of module registration
2. **Completes the feature**: Makes custom module registration truly useful
3. **Maintains design consistency**: Schema registry mirrors module registry pattern
4. **Unblocks fusion_modeling**: They can use full pipeline capabilities immediately
5. **Prevents workarounds from becoming permanent**: Manual output persistence code is harder to migrate later

The custom module registration work is **90% complete** but **unusable in practice** without schema registration. Finishing this now provides a **complete, coherent solution** for external packages.

## References

### Key Files Analyzed

**Pipeline System**:
- `/home/reid/teax/simkit/core/pipeline.py:62-98` - execute_pipeline() entry point
- `/home/reid/teax/simkit/core/pipeline_validator.py:79-118` - ExitPoint validation
- `/home/reid/teax/simkit/core/pipeline_executor.py:183-193` - Exit handler check
- `/home/reid/teax/simkit/io/output_router.py:31-166` - OutputRouter class and default handlers

**Registration System**:
- `/home/reid/teax/simkit/core/registry_builder.py:9-128` - create_registry() implementation
- `/home/reid/teax/simkit/core/pipeline_registry.py` - PipelineModuleRegistry class

**Fusion Example**:
- `/home/reid/fusion_modeling/tests/teax_simkit/fixtures/fusion_pipeline.yaml:54-60` - ExitPoint with custom schema
- `/home/reid/fusion_modeling/tests/teax_simkit/fusion_schemas.py:10-35` - FusionParams definition
- `/home/reid/fusion_modeling/tests/teax_simkit/modules/alphaneutronsplit.py:31-40` - Module output type

**Design Docs**:
- `/home/reid/teax/thoughts/specs/custom-module-package-registration.md` - Original spec
