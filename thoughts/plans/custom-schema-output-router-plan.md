# Plan: Custom Schema Support via OutputRouter Parameter

**Created**: 2025-11-08
**Status**: Ready for Implementation
**Estimated Effort**: 0.5-0.75 days
**Related Docs**:
- thoughts/research/exitpoint_custom_schema_challenge.md
- thoughts/specs/custom-module-package-registration.md

## Overview

Enable external packages to use custom schema types in ExitPoint by:
1. Making `OutputRouter` a configurable parameter in `execute_pipeline()`
2. Updating validation to check router handlers instead of hardcoded schema module
3. Adding in-memory mode for OutputRouter (no file writing)
4. Providing helper function for registering JSON-serializable custom schemas

This completes the custom module registration feature by removing the ExitPoint schema limitation.

## Current State Analysis

### What Works
- Custom modules can be registered via `registry` parameter in `execute_pipeline()`
- Custom types flow through channels between modules
- OutputRouter has `register_handler()` method for adding custom handlers

### What Doesn't Work
- ExitPoint validation hardcoded to `simkit.config.schema` module (pipeline_validator.py:113)
- OutputRouter is created internally, not configurable by users
- No way to skip file writing for testing/in-memory pipelines

### Root Cause
**File**: `simkit/core/pipeline_validator.py:113-118`
```python
if not hasattr(schema, type_name):
    raise PipelineValidationError(
        "ExitPoint output references unknown schema type",
        module=module.key,
        details={"output": field, "type": type_name},
    )
```

This checks against the `schema` module import instead of checking if the router has a handler.

## Design Changes

### 1. Add output_router Parameter to execute_pipeline()

**File**: `simkit/core/pipeline.py`

**Current signature**:
```python
def execute_pipeline(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
    registry: PipelineModuleRegistry | None = None,
) -> RunResult:
```

**New signature**:
```python
def execute_pipeline(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
    registry: PipelineModuleRegistry | None = None,
    output_router: OutputRouter | None = None,
) -> RunResult:
    """Execute pipeline with optional custom module registry and output router.

    Args:
        spec_path: Path to pipeline YAML specification
        output_dir: Optional output directory (defaults to temp dir)
        registry: Optional custom module registry. If None, uses built-in TEAx modules.
        output_router: Optional custom output router. If None, uses default router with
                      built-in schema handlers.

    Returns:
        RunResult with execution outputs, metadata, and provenance

    Example:
        >>> # Execute with built-in modules and schemas (backward compatible)
        >>> result = execute_pipeline("demo_pipeline.yaml", "outputs/")

        >>> # Execute with custom modules and schemas
        >>> from simkit.core.registry_builder import create_registry
        >>> from simkit.io.output_router import create_output_router_with_json_schemas
        >>>
        >>> registry = create_registry([MyCustomModule])
        >>> router = create_output_router_with_json_schemas(["MyCustomSchema"])
        >>> result = execute_pipeline(
        ...     "custom_pipeline.yaml",
        ...     "outputs/",
        ...     registry=registry,
        ...     output_router=router,
        ... )
    """
```

**Implementation**:
```python
def execute_pipeline(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
    registry: PipelineModuleRegistry | None = None,
    output_router: OutputRouter | None = None,
) -> RunResult:
    specification = entry_point_validate(spec_path)

    # Use custom registry if provided, otherwise default to builtins
    if registry is None:
        registry = PipelineModuleRegistry.from_static_modules()

    # Use custom router if provided, otherwise default to builtins
    router = output_router or create_default_router()

    executor = SerialPipelineExecutor(registry, output_router=router)
    context = PipelineExecutionContext(registry)

    # ... rest of function unchanged
```

### 2. Pass OutputRouter to PipelineValidator

**File**: `simkit/core/pipeline_validator.py`

**Current constructor**:
```python
class PipelineValidator:
    def __init__(self, registry: PipelineModuleRegistry) -> None:
        self._registry = registry
        self._builder = PipelineDagBuilder()
```

**New constructor**:
```python
class PipelineValidator:
    def __init__(
        self,
        registry: PipelineModuleRegistry,
        output_router: OutputRouter,
    ) -> None:
        self._registry = registry
        self._output_router = output_router
        self._builder = PipelineDagBuilder()
```

**Update SerialPipelineExecutor to pass router**:

**File**: `simkit/core/pipeline_executor.py`

**Current**:
```python
def __init__(
    self,
    registry: PipelineModuleRegistry | None = None,
    *,
    output_router: OutputRouter | None = None,
) -> None:
    self._registry = registry or PipelineModuleRegistry.from_static_modules()
    self._validator = PipelineValidator(self._registry)
    self._output_router = output_router or create_default_router()
```

**New**:
```python
def __init__(
    self,
    registry: PipelineModuleRegistry | None = None,
    *,
    output_router: OutputRouter | None = None,
) -> None:
    self._registry = registry or PipelineModuleRegistry.from_static_modules()
    self._output_router = output_router or create_default_router()
    self._validator = PipelineValidator(self._registry, self._output_router)
```

### 3. Update ExitPoint Validation Logic

**File**: `simkit/core/pipeline_validator.py`

**Current validation** (lines 113-118):
```python
if not hasattr(schema, type_name):
    raise PipelineValidationError(
        "ExitPoint output references unknown schema type",
        module=module.key,
        details={"output": field, "type": type_name},
    )
```

**New validation**:
```python
if not self._output_router.has_handler(type_name):
    raise PipelineValidationError(
        "ExitPoint output type has no registered write handler",
        module=module.key,
        details={
            "output": field,
            "type": type_name,
            "hint": "Register a handler with output_router.register_handler() or use create_output_router_with_json_schemas()"
        },
    )
```

**Note**: Remove the import of `schema` module from this file if it's only used for this check.

### 4. Add Helper Function for JSON Schemas

**File**: `simkit/io/output_router.py`

Add new function after `create_default_router()`:

```python
def create_output_router_with_json_schemas(
    custom_schema_types: list[str],
    *,
    include_builtins: bool = True,
) -> OutputRouter:
    """Create OutputRouter with custom JSON-serializable schema types.

    This is a convenience function for external packages that want to register
    custom Pydantic schema types for ExitPoint persistence. All custom types
    will use the standard JSON writer.

    Args:
        custom_schema_types: List of schema type names to register with JSON handlers.
                            Type names should match what appears in pipeline YAML
                            (e.g., "FusionParams", "AlphaNeutronSplitOutput").
        include_builtins: If True, includes all built-in TEAx schema handlers.
                         If False, creates router with only custom schemas.
                         Default: True (recommended for most use cases).

    Returns:
        OutputRouter configured with requested handlers

    Raises:
        ValueError: If custom_schema_types contains duplicates

    Example:
        >>> # Register fusion schemas with built-in TEAx schemas
        >>> router = create_output_router_with_json_schemas([
        ...     "FusionParams",
        ...     "AlphaNeutronSplitOutput",
        ... ])
        >>>
        >>> # Use in pipeline
        >>> from simkit.core.pipeline import execute_pipeline
        >>> result = execute_pipeline(
        ...     "fusion_pipeline.yaml",
        ...     "outputs/",
        ...     output_router=router,
        ... )

        >>> # Custom-only (no built-ins)
        >>> router = create_output_router_with_json_schemas(
        ...     ["MySchema"],
        ...     include_builtins=False,
        ... )
    """
    # Check for duplicates
    if len(custom_schema_types) != len(set(custom_schema_types)):
        duplicates = [t for t in custom_schema_types if custom_schema_types.count(t) > 1]
        raise ValueError(
            f"Duplicate schema types in custom_schema_types: {set(duplicates)}"
        )

    # Start with builtins or empty
    if include_builtins:
        router = create_default_router()
    else:
        router = OutputRouter(type_handlers={})

    # Register custom types with JSON handler
    json_handler = WriteHandler(fn=writers.write_json_model, extension=".json")
    for type_name in custom_schema_types:
        router.register_handler(type_name, json_handler)

    return router
```

### 5. Add In-Memory Mode to OutputRouter

**File**: `simkit/io/output_router.py`

Add parameter to control file writing behavior:

**Current constructor**:
```python
def __init__(
    self,
    type_handlers: Mapping[str, WriteHandler],
    *,
    manifest_writer: Callable[[Any, Path], Path] | None = None,
) -> None:
    self._type_handlers: Dict[str, WriteHandler] = dict(type_handlers)
    self._manifest_writer = manifest_writer or writers.write_json_payload
```

**New constructor**:
```python
def __init__(
    self,
    type_handlers: Mapping[str, WriteHandler],
    *,
    manifest_writer: Callable[[Any, Path], Path] | None = None,
    in_memory: bool = False,
) -> None:
    """Create OutputRouter for persisting pipeline outputs.

    Args:
        type_handlers: Mapping of schema type names to write handlers
        manifest_writer: Optional custom manifest writer function
        in_memory: If True, validate outputs but don't write files.
                  Useful for testing and programmatic pipeline execution.
                  Default: False (write files normally).
    """
    self._type_handlers: Dict[str, WriteHandler] = dict(type_handlers)
    self._manifest_writer = manifest_writer or writers.write_json_payload
    self._in_memory = in_memory
```

**Update write_outputs() method**:

Add early return for in-memory mode after validation but before file writing.

**Current write_outputs() structure**:
```python
def write_outputs(
    self,
    exit_bindings: Mapping[str, PipelineChannelBinding],
    channel_values: Mapping[str, Any],
    *,
    base_output_dir: Path | None = None,
    run_name: str | None = None,
    pipeline_metadata: object | None = None,
) -> OutputRouterResult:
    resolution = environment.resolve_output_dir(preferred=base_output_dir, run_name=run_name)
    run_dir, short_id = self._prepare_run_directory(resolution.base_dir, resolution.run_name)

    artifacts: list[schema.RunArtifactRecord] = []
    used_filenames: set[str] = set()

    # Validation and writing loop
    for alias, binding in exit_bindings.items():
        # ... validation ...
        # ... file writing ...
        artifacts.append(...)

    # Create manifest
    manifest = schema.RunManifest(...)
    manifest_path = run_dir / "manifest.json"
    self._manifest_writer(manifest, manifest_path)

    return OutputRouterResult(...)
```

**New write_outputs() structure**:
```python
def write_outputs(
    self,
    exit_bindings: Mapping[str, PipelineChannelBinding],
    channel_values: Mapping[str, Any],
    *,
    base_output_dir: Path | None = None,
    run_name: str | None = None,
    pipeline_metadata: object | None = None,
) -> OutputRouterResult:
    # In-memory mode: validate and collect without writing
    if self._in_memory:
        return self._collect_outputs_in_memory(
            exit_bindings,
            channel_values,
            run_name=run_name,
            pipeline_metadata=pipeline_metadata,
        )

    # Normal mode: validate and write to disk
    resolution = environment.resolve_output_dir(preferred=base_output_dir, run_name=run_name)
    run_dir, short_id = self._prepare_run_directory(resolution.base_dir, resolution.run_name)

    # ... rest of existing implementation unchanged ...
```

**Add new helper method**:
```python
def _collect_outputs_in_memory(
    self,
    exit_bindings: Mapping[str, PipelineChannelBinding],
    channel_values: Mapping[str, Any],
    *,
    run_name: str | None = None,
    pipeline_metadata: object | None = None,
) -> OutputRouterResult:
    """Validate outputs without writing to disk (in-memory mode).

    Performs all validation checks but skips file I/O. Returns an OutputRouterResult
    with synthetic paths for compatibility with pipeline executor.
    """
    artifacts: list[schema.RunArtifactRecord] = []
    used_filenames: set[str] = set()

    # Validate all bindings (same validation as normal mode)
    for alias, binding in exit_bindings.items():
        destination = binding.destination_filename
        if not destination:
            raise OutputRouterError(f"ExitPoint binding '{alias}' is missing a destination filename")
        if destination in used_filenames:
            raise OutputRouterError(f"Destination filename '{destination}' declared more than once")
        used_filenames.add(destination)

        type_name = binding.type_name
        if type_name is None:
            raise OutputRouterError(f"ExitPoint binding '{alias}' is missing a type declaration")

        handler = self._type_handlers.get(type_name)
        if handler is None:
            raise OutputRouterError(f"No writer registered for type '{type_name}'")
        if handler.extension and not destination.endswith(handler.extension):
            raise OutputRouterError(
                f"Destination filename '{destination}' does not match expected extension '{handler.extension}'"
            )

        channel_name = binding.channel_name
        payload = channel_values.get(channel_name)

        # Record artifact without writing
        artifacts.append(
            schema.RunArtifactRecord(
                channel=channel_name,
                type_name=type_name,
                relative_path=destination if payload is not None else None,
                produced=payload is not None,
            )
        )

    # Create metadata payload (same as normal mode)
    metadata_payload = None
    if pipeline_metadata is not None:
        if hasattr(pipeline_metadata, "model_dump"):
            metadata_payload = pipeline_metadata.model_dump()
        elif isinstance(pipeline_metadata, Mapping):
            metadata_payload = dict(pipeline_metadata)
        else:
            raise OutputRouterError(
                "pipeline_metadata must be a mapping or provide a model_dump() method"
            )

    # Create manifest with synthetic paths (since we didn't create directories)
    final_run_name = run_name or "in_memory_run"
    short_id = "mem"

    manifest = schema.RunManifest(
        run_name=final_run_name,
        run_directory=f"{final_run_name}-{short_id}",
        base_output_dir="<in-memory>",
        short_id=short_id,
        metadata=metadata_payload,
        artifacts=artifacts,
    )

    # Return result with synthetic paths
    from pathlib import Path
    synthetic_run_dir = Path("<in-memory>") / f"{final_run_name}-{short_id}"
    synthetic_manifest_path = synthetic_run_dir / "manifest.json"

    return OutputRouterResult(
        run_dir=synthetic_run_dir,
        manifest=manifest,
        manifest_path=synthetic_manifest_path,
    )
```

**Update helper functions to support in_memory**:

```python
def create_default_router(*, in_memory: bool = False) -> OutputRouter:
    """Create an OutputRouter populated with default schema type handlers.

    Args:
        in_memory: If True, router validates but doesn't write files.
                  Default: False.
    """
    handlers: MutableMapping[str, WriteHandler] = {
        # ... existing handlers ...
    }
    return OutputRouter(type_handlers=handlers, in_memory=in_memory)


def create_output_router_with_json_schemas(
    custom_schema_types: list[str],
    *,
    include_builtins: bool = True,
    in_memory: bool = False,
) -> OutputRouter:
    """Create OutputRouter with custom JSON-serializable schema types.

    Args:
        custom_schema_types: List of schema type names to register
        include_builtins: If True, includes built-in handlers
        in_memory: If True, router validates but doesn't write files
    """
    # ... validation ...

    if include_builtins:
        router = create_default_router(in_memory=in_memory)
    else:
        router = OutputRouter(type_handlers={}, in_memory=in_memory)

    # ... register custom handlers ...

    return router
```

## Implementation Steps

### Step 1: Update OutputRouter (in_memory feature)
**File**: `simkit/io/output_router.py`

1. Add `in_memory: bool = False` parameter to `OutputRouter.__init__()`
2. Store as `self._in_memory`
3. Add early return in `write_outputs()` if `self._in_memory` is True
4. Implement `_collect_outputs_in_memory()` method
5. Update `create_default_router()` to accept `in_memory` parameter
6. Update existing docstrings

**Estimated time**: 1-2 hours

### Step 2: Add Helper Function
**File**: `simkit/io/output_router.py`

1. Implement `create_output_router_with_json_schemas()` function
2. Add comprehensive docstring with examples
3. Add input validation (check for duplicates)

**Estimated time**: 30 minutes

### Step 3: Update PipelineValidator
**File**: `simkit/core/pipeline_validator.py`

1. Add `output_router: OutputRouter` parameter to `__init__()`
2. Store as `self._output_router`
3. Update `_validate_exit_module()` to check `self._output_router.has_handler(type_name)` instead of `hasattr(schema, type_name)`
4. Update error message to include helpful hint
5. Remove import of `schema` module if no longer needed (check all usages first)

**Estimated time**: 30 minutes

### Step 4: Update SerialPipelineExecutor
**File**: `simkit/core/pipeline_executor.py`

1. Move `self._output_router = ...` line before `self._validator = ...` line
2. Pass `self._output_router` to `PipelineValidator` constructor
3. Update any docstrings if needed

**Estimated time**: 15 minutes

### Step 5: Update execute_pipeline()
**File**: `simkit/core/pipeline.py`

1. Add `output_router: OutputRouter | None = None` parameter
2. Update line 96: `router = output_router or create_default_router()`
3. Update comprehensive docstring with examples
4. Ensure backward compatibility (test without parameters)

**Estimated time**: 30 minutes

### Step 6: Add Import Exports
**File**: `simkit/io/__init__.py`

Add to exports:
```python
from .output_router import (
    OutputRouter,
    create_default_router,
    create_output_router_with_json_schemas,  # NEW
)
```

**Estimated time**: 5 minutes

### Step 7: Update CLAUDE.md Documentation
**File**: `CLAUDE.md`

Add section on custom schema registration:

```markdown
## Custom Schema Registration for ExitPoint

External packages can register custom schema types for ExitPoint persistence:

### Option 1: Using Helper Function (Recommended)

```python
from simkit.core.pipeline import execute_pipeline
from simkit.io.output_router import create_output_router_with_json_schemas
from fusion_simkit import create_fusion_registry

# Register custom schemas that will be serialized as JSON
router = create_output_router_with_json_schemas([
    "FusionParams",
    "AlphaNeutronSplitOutput",
    "BlanketThermalPowerOutput",
])

result = execute_pipeline(
    "fusion_pipeline.yaml",
    "outputs/",
    registry=create_fusion_registry(),
    output_router=router,
)
```

### Option 2: Manual Registration (Advanced)

```python
from simkit.io.output_router import create_default_router, WriteHandler
from simkit.io import writers

# Create router with built-in handlers
router = create_default_router()

# Register custom handler with specific serialization
router.register_handler(
    "MyCustomType",
    WriteHandler(fn=writers.write_json_model, extension=".json")
)

# Or use custom writer function
def write_custom_format(payload, path):
    # Custom serialization logic
    ...

router.register_handler(
    "MySpecialType",
    WriteHandler(fn=write_custom_format, extension=".custom")
)
```

### In-Memory Mode (Testing)

For unit tests or programmatic pipeline execution without file I/O:

```python
from simkit.io.output_router import create_output_router_with_json_schemas

router = create_output_router_with_json_schemas(
    ["MySchema"],
    in_memory=True,  # Validate but don't write files
)

result = execute_pipeline("pipeline.yaml", None, output_router=router)
# Access outputs programmatically
my_data = result.outputs["my_channel"]
```
```

**Estimated time**: 30 minutes

## Testing Requirements

### Unit Tests

**File**: `simkit/tests/io/test_output_router.py`

Add new tests:

1. **test_create_output_router_with_json_schemas_builtins**
   - Verify router includes built-in handlers when `include_builtins=True`
   - Verify custom schemas are added
   - Verify `has_handler()` returns True for both built-in and custom types

2. **test_create_output_router_with_json_schemas_custom_only**
   - Verify router has only custom handlers when `include_builtins=False`
   - Verify `has_handler()` returns False for built-in types

3. **test_create_output_router_with_json_schemas_duplicates**
   - Verify ValueError raised when custom_schema_types contains duplicates
   - Check error message lists duplicate types

4. **test_output_router_in_memory_mode**
   - Create router with `in_memory=True`
   - Call `write_outputs()` with valid bindings
   - Verify OutputRouterResult returned with synthetic paths
   - Verify no files created on disk
   - Verify manifest contains correct artifact records

5. **test_output_router_in_memory_validation_still_works**
   - Create in-memory router
   - Call `write_outputs()` with invalid binding (missing handler)
   - Verify OutputRouterError raised
   - Verify error message correct

**File**: `simkit/tests/core/test_pipeline_validator.py`

Add new tests:

6. **test_validate_exit_custom_schema_with_handler**
   - Create OutputRouter with custom handler registered
   - Create pipeline spec with ExitPoint referencing custom schema
   - Verify validation passes

7. **test_validate_exit_custom_schema_without_handler**
   - Create OutputRouter without custom handler
   - Create pipeline spec with ExitPoint referencing custom schema
   - Verify PipelineValidationError raised
   - Verify error message includes helpful hint

**File**: `simkit/tests/core/test_pipeline_executor.py`

Add new tests:

8. **test_execute_pipeline_with_custom_output_router**
   - Create custom OutputRouter with test schema handler
   - Execute pipeline with custom router
   - Verify outputs written using custom handlers
   - Verify manifest correct

**File**: `simkit/tests/test_pipeline.py` (integration test)

Add new test:

9. **test_execute_pipeline_custom_schema_end_to_end**
   - Define custom Pydantic model not in simkit.config.schema
   - Create custom module that outputs this type
   - Register module in registry
   - Register schema in output router
   - Create minimal pipeline YAML with ExitPoint referencing custom schema
   - Execute pipeline
   - Verify output file created with correct content

10. **test_execute_pipeline_in_memory_mode**
    - Create router with `in_memory=True`
    - Execute pipeline
    - Verify `result.outputs` contains data
    - Verify `result.manifest` is populated
    - Verify no output directory created
    - Verify data accessible programmatically

**Estimated time**: 2-3 hours

### Backward Compatibility Tests

Run ALL existing tests to ensure no regressions:
```bash
pytest simkit/tests/
```

Verify these specific scenarios still work:
- `execute_pipeline(spec_path, output_dir)` without any optional parameters
- Built-in TEAx schemas work in ExitPoint without custom router
- All demo pipelines in `tests/fixtures/pipeline_configs/` execute successfully

**Estimated time**: 30 minutes

## Acceptance Criteria

The implementation is complete when:

### Core Functionality
- [ ] `execute_pipeline()` accepts `output_router` parameter
- [ ] When `output_router=None`, default router is used (backward compatible)
- [ ] When custom router provided, it's used for ExitPoint validation and writing
- [ ] PipelineValidator checks `output_router.has_handler()` instead of `hasattr(schema, ...)`
- [ ] Custom schema types registered in router pass validation
- [ ] Custom schema types not in router fail validation with helpful error

### Helper Function
- [ ] `create_output_router_with_json_schemas()` exists and works
- [ ] `include_builtins=True` includes all built-in handlers
- [ ] `include_builtins=False` creates router with only custom types
- [ ] Duplicate schema types raise ValueError
- [ ] JSON handler assigned to all custom types

### In-Memory Mode
- [ ] OutputRouter accepts `in_memory=True` parameter
- [ ] In-memory mode validates outputs without writing files
- [ ] OutputRouterResult returned with synthetic paths
- [ ] Manifest contains correct artifact records
- [ ] All validation still occurs (missing handlers, duplicate filenames, etc.)
- [ ] `create_default_router(in_memory=True)` works
- [ ] `create_output_router_with_json_schemas(..., in_memory=True)` works

### Testing
- [ ] All new unit tests pass
- [ ] All existing tests pass (no regressions)
- [ ] Integration test with custom schema works end-to-end
- [ ] In-memory mode test verifies no file I/O

### Documentation
- [ ] Docstrings complete for all new/modified functions
- [ ] CLAUDE.md updated with usage examples
- [ ] Error messages include helpful hints for users

### External Package Compatibility
- [ ] fusion_modeling can use pattern:
  ```python
  router = create_output_router_with_json_schemas([
      "FusionParams",
      "AlphaNeutronSplitOutput",
  ])
  result = execute_pipeline("fusion_pipeline.yaml", "outputs/",
                           registry=fusion_registry, output_router=router)
  ```
- [ ] ExitPoint with `FusionParams` passes validation
- [ ] fusion_params.json file created with correct content

## Files to Modify

### Core Implementation
1. **simkit/io/output_router.py** (Major changes)
   - Add `in_memory` parameter to `OutputRouter.__init__()`
   - Add `_collect_outputs_in_memory()` method
   - Add `create_output_router_with_json_schemas()` function
   - Update `create_default_router()` to accept `in_memory`
   - Update `write_outputs()` to handle in-memory mode

2. **simkit/core/pipeline_validator.py** (Minor changes)
   - Add `output_router` parameter to `__init__()`
   - Update `_validate_exit_module()` validation logic
   - Update error message

3. **simkit/core/pipeline_executor.py** (Trivial changes)
   - Reorder initialization to create router before validator
   - Pass router to validator constructor

4. **simkit/core/pipeline.py** (Minor changes)
   - Add `output_router` parameter to `execute_pipeline()`
   - Update docstring with examples
   - Use provided router or create default

5. **simkit/io/__init__.py** (Trivial changes)
   - Export `create_output_router_with_json_schemas`

### Documentation
6. **CLAUDE.md** (Minor additions)
   - Add section on custom schema registration
   - Add examples for manual and helper function approaches
   - Add in-memory mode example

### Tests
7. **simkit/tests/io/test_output_router.py** (New tests)
   - Tests for helper function
   - Tests for in-memory mode

8. **simkit/tests/core/test_pipeline_validator.py** (New tests)
   - Tests for custom schema validation

9. **simkit/tests/core/test_pipeline_executor.py** (New tests)
   - Tests for custom router in executor

10. **simkit/tests/test_pipeline.py** (New integration test)
    - End-to-end test with custom schema
    - End-to-end test with in-memory mode

## Example Usage Patterns

### Pattern 1: External Package Helper Function

**In fusion_simkit package**:
```python
# fusion_simkit/registry.py
from simkit.io.output_router import create_output_router_with_json_schemas

def create_fusion_output_router(in_memory: bool = False):
    """Create OutputRouter configured for fusion schemas."""
    return create_output_router_with_json_schemas(
        [
            "FusionParams",
            "AlphaNeutronSplitOutput",
            "BlanketThermalPowerOutput",
            "GrossElectricPowerOutput",
        ],
        in_memory=in_memory,
    )
```

**User code**:
```python
from fusion_simkit import create_fusion_registry, create_fusion_output_router
from simkit.core.pipeline import execute_pipeline

result = execute_pipeline(
    "fusion_pipeline.yaml",
    "outputs/",
    registry=create_fusion_registry(),
    output_router=create_fusion_output_router(),
)

assert (result.run_dir / "fusion_params.json").exists()
```

### Pattern 2: Manual Registration with Custom Writer

```python
from simkit.io.output_router import create_default_router, WriteHandler
from simkit.io import writers
import json
from pathlib import Path

# Custom writer for special format
def write_fusion_telemetry(payload, path: Path):
    """Write fusion telemetry in custom binary format."""
    # Custom serialization logic
    with open(path, 'wb') as f:
        # ... custom binary writing ...
        pass

# Create router and register custom handler
router = create_default_router()
router.register_handler(
    "FusionTelemetry",
    WriteHandler(fn=write_fusion_telemetry, extension=".ftel")
)

result = execute_pipeline(
    "pipeline.yaml",
    "outputs/",
    output_router=router,
)
```

### Pattern 3: Testing with In-Memory Mode

```python
def test_my_pipeline():
    """Test pipeline logic without file I/O."""
    from simkit.io.output_router import create_output_router_with_json_schemas
    from simkit.core.pipeline import execute_pipeline

    # Create in-memory router
    router = create_output_router_with_json_schemas(
        ["MyTestSchema"],
        in_memory=True,
    )

    # Execute pipeline (no files written)
    result = execute_pipeline(
        "test_pipeline.yaml",
        None,  # No output dir needed
        output_router=router,
    )

    # Validate outputs programmatically
    assert result.outputs["my_channel"].value == 42
    assert result.manifest.artifacts[0].produced is True

    # Verify no files created
    # (in-memory mode doesn't touch filesystem)
```

### Pattern 4: Custom Schemas Without Built-ins

```python
from simkit.io.output_router import create_output_router_with_json_schemas

# Create router with ONLY custom schemas (no TEAx built-ins)
router = create_output_router_with_json_schemas(
    ["CustomType1", "CustomType2"],
    include_builtins=False,
)

# This router will REJECT built-in TEAx types like BatteryConfig
# Use when you have a completely custom pipeline
```

## Error Messages

Ensure clear, actionable error messages:

### Missing Handler Error
```
PipelineValidationError: ExitPoint output type has no registered write handler

Module: exit_point
Details:
  output: fusion_params
  type: FusionParams
  hint: Register a handler with output_router.register_handler() or use create_output_router_with_json_schemas()
```

### Duplicate Schema Error
```
ValueError: Duplicate schema types in custom_schema_types: {'FusionParams'}

Ensure each schema type appears only once in the list.
```

### In-Memory Validation Error
```
OutputRouterError: No writer registered for type 'UnknownType'

Note: Router is in in-memory mode, but validation still requires registered handlers.
Register the handler even if you don't plan to write files.
```

## Rollout Strategy

### Phase 1: Core Implementation (Day 1 Morning)
1. Implement in-memory mode in OutputRouter
2. Add helper function
3. Update validation logic
4. Wire up execute_pipeline parameter

### Phase 2: Testing (Day 1 Afternoon)
1. Write unit tests
2. Write integration test
3. Run backward compatibility tests
4. Fix any issues

### Phase 3: Documentation (Day 1 End of Day)
1. Update CLAUDE.md
2. Update docstrings
3. Create example in thoughts/examples/ if needed

### Phase 4: Validation with fusion_modeling (Day 2 if needed)
1. Update fusion_simkit to use new pattern
2. Run fusion pipeline end-to-end
3. Verify ExitPoint works with custom schemas
4. Document any issues for future work

## Success Metrics

The implementation succeeds when:

1. ✅ All tests pass (existing + new)
2. ✅ fusion_modeling can execute pipelines with custom schemas
3. ✅ Code review shows no regressions
4. ✅ Documentation is clear and complete
5. ✅ Error messages are helpful
6. ✅ In-memory mode works for testing use cases
7. ✅ Implementation is ~200-300 LOC total (lean, focused solution)

## Notes for Implementer

### Code Style
- Follow existing patterns in the codebase
- Use type hints for all new functions
- Add docstrings in Google style
- Keep functions focused and single-purpose

### Testing Strategy
- Test one feature at a time
- Use pytest fixtures for common setup
- Mock file I/O where appropriate
- Write descriptive test names

### Git Workflow
- Create feature branch: `git checkout -b feature/custom-schema-output-router`
- Commit logical chunks (not whole feature at once)
- Suggested commits:
  1. "Add in_memory mode to OutputRouter"
  2. "Add create_output_router_with_json_schemas helper"
  3. "Update validation to use output_router"
  4. "Wire up output_router parameter to execute_pipeline"
  5. "Add tests for custom schema support"
  6. "Update documentation"

### Common Pitfalls to Avoid
- Don't forget to update `simkit/io/__init__.py` exports
- Don't break backward compatibility (always test without optional params)
- Don't forget to handle `in_memory=True` in helper functions
- Don't skip validation in in-memory mode (still need to check handlers exist)
- Remember to update both `create_default_router()` and helper function with `in_memory` parameter

### Questions During Implementation

If you encounter ambiguity:
1. Check existing patterns in the codebase (e.g., how registry parameter was added)
2. Prioritize backward compatibility
3. Prefer explicit over implicit (clear error messages)
4. When in doubt, ask the user

Good luck! This is a high-value, focused feature that completes the custom module registration work.
