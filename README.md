# TEAx User Guide

**Version:** 0.1
**Status:** Production-ready for external users

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Pipeline Specification (YAML)](#pipeline-specification-yaml)
   - [Field Referencing](#field-referencing)
4. [Channel-Based DAG System](#channel-based-dag-system)
5. [Module Development](#module-development)
6. [I/O System](#io-system)
7. [Custom Module Registration](#custom-module-registration)
8. [Debugging Guide](#debugging-guide)
9. [API Reference](#api-reference)
10. [Migration Guide](#migration-guide)

---

## Overview

**TEAx (Techno-Economic Analysis framework)** is a modular, type-safe pipeline system for building simulation frameworks. The repository contains two packages:

- **teax-simkit** (`packages/teax-simkit/`): Core framework for building typed pipeline systems
- **battery-tea-demo** (`packages/battery-tea-demo/`): Example implementation for battery energy storage TEA

The framework enables users to:

- **Define pipelines** via declarative YAML specifications
- **Compose modules** into directed acyclic graphs (DAGs) with typed channels
- **Develop custom modules** using any Pydantic `BaseModel` schemas
- **Register external packages** with automatic type introspection
- **Execute simulations** with full provenance tracking

### Core Concepts

1. **Modules**: Functional units with typed inputs and outputs (`ModuleBase[InputModel, OutputModel]`)
2. **Channels**: Named data flows connecting module outputs to downstream inputs
3. **Pipeline**: DAG of modules defined in YAML, validated and executed in topological order
4. **Registry**: Catalog of available modules with metadata for validation
5. **Provenance**: Automatic tracking of module versions, config hashes, and execution metadata

---

## Quick Start

### Installation

```bash
# Install core framework
pip install -e packages/teax-simkit

# Install battery demo (includes teax-simkit dependency)
pip install -e packages/battery-tea-demo

# Or install both for development
pip install -e packages/teax-simkit[dev]
pip install -e packages/battery-tea-demo[dev]
```

### Minimal Example (using battery-tea-demo)

**1. Create a pipeline specification (`demo.yaml`):**

```yaml
metadata:
  run_description: My first pipeline

modules:
  entry_point:
    module_type: EntryPoint
    inputs:
      geo: Geography ../geography_us_ca_pge.json

  rate_data:
    module_type: RateData
    inputs:
      geography: Geography geo
    outputs:
      rate_info: RateInfo rate_info

  exit_point:
    module_type: ExitPoint
    outputs:
      rate_info: RateInfo rate_info.json
```

**2. Execute the pipeline:**

```python
from battery_tea import create_battery_registry
from battery_tea.schemas import Geography, RateInfo
from simkit.core.pipeline import execute_pipeline

# Create registry with battery modules
registry = create_battery_registry()

# Execute pipeline with custom registry and schemas
result = execute_pipeline(
    "demo.yaml",
    output_dir="outputs/",
    registry=registry,
    custom_schema_types=[Geography, RateInfo],
)
print(result.outputs)  # {'rate_info': RateInfo(...)}
print(result.manifest)  # RunManifest with file locations
print(result.provenance)  # Provenance with config hash and module versions
```

---

## Pipeline Specification (YAML)

### Structure

```yaml
metadata:                     # Optional metadata
  run_description: string     # Human-readable description
  output_folder: string       # Output directory name hint

modules:                      # Required: module declarations
  <module_key>:               # Unique identifier for this module instance
    module_type: string       # Module class name (from registry)
    inputs:                   # Input bindings (field -> channel)
      <field>: <Type> <channel_or_path>
    outputs:                  # Output bindings (field -> channel)
      <field>: <Type> <channel>
```

### Input Binding Syntax

| Pattern | Meaning | Example |
|---------|---------|---------|
| `Type channel_name` | Read from channel | `Geography geo` |
| `Type channel.field` | Extract field from channel | `BlanketConfig fusion_params.blanket_config` |
| `Type path/to/file.json` | Load from file (EntryPoint only) | `Geography ../geo.json` |
| `None -> default_name` | Use module's default value | `None -> design_pref_default` |

### Output Binding Syntax

| Pattern | Meaning | Example |
|---------|---------|---------|
| `Type channel_name` | Write to channel (internal modules) | `RateInfo rate_info` |
| `Type filename.ext` | Write to file (ExitPoint only) | `RateInfo rate_info.json` |

### Special Modules

#### EntryPoint
Loads input data from files and initializes channels. Must appear exactly once.

```yaml
entry_point:
  module_type: EntryPoint
  inputs:
    geo: Geography ../data/geography.json           # JSON -> Geography model
    load: LoadProfile8760 ../data/load.parquet      # Parquet -> LoadProfile8760 (battery-tea-demo)
```

**Note:** Custom types like `Geography` and `LoadProfile8760` must be registered via `custom_schema_types` parameter.

**Path Resolution:**
1. Try relative to YAML file location
2. Fall back to `$PYRONDO_INPUT_DIR/<path>` (env var)
3. Fall back to `run_data/inputs/<path>` (project default)

#### ExitPoint
Declares which channels to persist as pipeline outputs. Must appear exactly once.

```yaml
exit_point:
  module_type: ExitPoint
  outputs:
    rate_info: RateInfo rate_info.json              # Serialize to JSON
    telemetry: BatteryTelemetry8760 telemetry.json  # Serialize to JSON
```

Outputs are written to: `<output_dir>/<run_name>/<timestamp>/<filename>`

**Note:** By default, all types serialize to JSON. For specialized formats (Parquet), use custom output handlers.

### Field Referencing

**Field Referencing** allows modules to bind inputs to **specific fields** of upstream channel values, rather than consuming entire models. This enables fine-grained data routing without requiring intermediate "unpacker" modules.

#### Motivation

Consider a large configuration model with many fields:

```python
class FusionParams(StrictBaseModel):
    p_thermal_electric: float
    p_fusion: float
    blanket_config: BlanketConfig
    coolant_config: CoolantConfig
    plasma_config: PlasmaConfig
    # ... 45 more fields
```

**Without field referencing:** Each module must accept the entire `FusionParams` object, even if it only needs one field:

```yaml
blanket_thermal:
  inputs:
    fusion_params: FusionParams fusion_params  # Receives entire object
    # Module must extract blanket_config internally
```

**With field referencing:** Modules receive only the fields they need:

```yaml
blanket_thermal:
  inputs:
    blanket: BlanketConfig fusion_params.blanket_config  # Receives only blanket_config field
```

#### Syntax

```
<Type> <channel_name>.<field_path>
```

- **Type**: Expected type of the field
- **channel_name**: Name of the upstream channel
- **field_path**: Field name to extract (single-level only in current version)

#### Example Pipeline

```yaml
modules:
  entry_point:
    module_type: EntryPoint
    inputs:
      fusion_params: FusionParams ../fusion_params.json

  blanket_thermal:
    module_type: BlanketThermalModule
    inputs:
      blanket: BlanketConfig fusion_params.blanket_config  # Extract blanket_config field
    outputs:
      thermal_result: ThermalOutput thermal_output

  coolant_flow:
    module_type: CoolantFlowModule
    inputs:
      coolant: CoolantConfig fusion_params.coolant_config  # Extract coolant_config field
    outputs:
      flow_result: FlowOutput flow_output

  exit_point:
    module_type: ExitPoint
    outputs:
      thermal_output: ThermalOutput thermal_result.json
      flow_output: FlowOutput flow_result.json
```

In this example, both `blanket_thermal` and `coolant_flow` modules extract different fields from the same `fusion_params` channel, allowing specialized modules to receive only the data they need.

#### Validation

Field references are validated at pipeline load time:

1. **Field existence**: Field must exist in the parent type
2. **Type compatibility**: Field type must match declared binding type exactly
3. **Non-private fields**: Cannot extract fields starting with `_`
4. **Non-computed fields**: Cannot extract `@computed_field` properties (current version)

**Validation errors provide helpful context:**

```
PipelineValidationError: Module 'blanket_thermal' input 'blanket':
Type 'FusionParams' has no field 'blanket_cfg'.
Available fields: p_thermal_electric, p_fusion, blanket_config, coolant_config, plasma_config
```

#### Runtime Behavior

At runtime, the executor:

1. Fetches the parent channel value
2. Extracts the specified field using `getattr()`
3. Validates the field value is not `None` (for Optional fields)
4. Passes only the extracted field to the module

**Optional field handling:**

If a field is typed as `Optional[T]`, validation passes, but runtime raises an error if the value is `None`:

```python
class FusionParams(StrictBaseModel):
    blanket_config: BlanketConfig
    optional_blanket: BlanketConfig | None = None  # Optional field
```

```yaml
# This validates successfully
blanket_thermal:
  inputs:
    blanket: BlanketConfig fusion_params.optional_blanket
```

But if `optional_blanket` is `None` at runtime:

```
PipelineExecutionError: Field 'optional_blanket' on channel 'fusion_params' is None
(expected BlanketConfig). Optional fields must have non-None values at runtime.
```

#### Current Limitations

- **Single-level only**: Nested paths like `channel.field.subfield` are not supported
- **Exact type matching**: No subclass polymorphism
- **No computed fields**: Cannot extract `@computed_field` properties

#### Key Files

- **Parsing:** `simkit/config/pipeline_schema.py:240-303` - YAML parsing for `channel.field` syntax
- **Validation:** `simkit/core/pipeline_validator.py:162-238` - Field reference validation logic
- **Execution:** `simkit/core/pipeline_executor.py:352-398` - Runtime field extraction

---

## Channel-Based DAG System

### How Channels Work

Channels are **named, typed data flows** that connect modules. Think of them as strongly-typed pipes:

```yaml
# Module A produces channel "rate_info" of type RateInfo
rate_data:
  outputs:
    rate_info: RateInfo rate_info

# Module B consumes channel "rate_info"
configure_battery:
  inputs:
    rate_info: RateInfo rate_info  # Must match type and channel name
```

### Validation and DAG Building

When you call `execute_pipeline()`, the system:

1. **Parses YAML** → `PipelineSpecification` (see `simkit/io/readers.py:84`)
2. **Validates structure** → Checks for cycles, missing channels, type mismatches (see `simkit/core/pipeline_validator.py`)
3. **Builds DAG** → `PipelineGraph` with topological order (see `simkit/core/pipeline_graph.py`)
4. **Executes modules** → In order, routing data through channels (see `simkit/core/pipeline_executor.py`)

**Key File:** `simkit/config/pipeline_schema.py:67-100` - Defines spec structure and validation rules

### Type Checking Rules

The validator enforces:

- **Channel uniqueness**: No two modules can produce the same channel
- **Type compatibility**: Producer type must match consumer type exactly
- **Required inputs**: All required module inputs must be bound
- **Optional inputs**: May use `None -> default` or omit entirely
- **Output handlers**: ExitPoint outputs must have registered serializers

**Key File:** `simkit/core/pipeline_validator.py` - Contains all validation logic

---

## Module Development

### Module Interface

All modules inherit from `ModuleBase[InputModel, OutputModel]` where both types are Pydantic `BaseModel` subclasses.

**Key File:** `simkit/core/base.py:19-29` - Defines `ModuleBase` interface

```python
from pydantic import BaseModel
from simkit.core.base import ModuleBase, ModuleResult

class MyInput(BaseModel):
    value: float

class MyOutput(BaseModel):
    result: float

class MyModule(ModuleBase[MyInput, MyOutput]):
    name = "my_module"      # Required: module identifier
    version = "v1.0"        # Required: version for provenance

    def validate_and_fill_default(self, **kwargs) -> MyInput:
        """Validate inputs and fill defaults before execution."""
        return MyInput(**kwargs)

    def run(self, **kwargs) -> ModuleResult[MyOutput]:
        """Execute module logic with validated inputs."""
        inputs = self.validate_and_fill_default(**kwargs)
        return ModuleResult(data=MyOutput(result=inputs.value * 2))
```

### Single-Output Modules

Most modules produce **one typed output** assigned to one channel.

```python
class PowerCalculatorOutput(BaseModel):
    power_kw: float

class PowerCalculatorModule(ModuleBase[MyInput, PowerCalculatorOutput]):
    name = "power_calc"
    version = "v1.0"

    def run(self, **kwargs) -> ModuleResult[PowerCalculatorOutput]:
        return ModuleResult(data=PowerCalculatorOutput(power_kw=123.4))
```

**YAML:**
```yaml
power_calc:
  module_type: PowerCalculatorModule
  inputs:
    # ... inputs
  outputs:
    power_calculator_output: PowerCalculatorOutput power_data  # Single output
```

The entire `PowerCalculatorOutput` object is assigned to the `power_data` channel.

### Multi-Output Modules

Modules that need to **route different data types to different channels** use the `MultiOutput` pattern.

**Key File:** `simkit/config/schema.py:28-74` - Defines `MultiOutput` base class

```python
from simkit.config.schema import MultiOutput

# 1. Define output container inheriting from MultiOutput
class AlphaNeutronSplitOutput(MultiOutput):
    """Each field becomes a separate channel."""
    p_alpha: PowerValue      # Field 1: will be routed to one channel
    p_neutron: PowerValue    # Field 2: will be routed to another channel

# 2. Use MultiOutput as OutputModel
class AlphaNeutronSplitModule(ModuleBase[MyInput, AlphaNeutronSplitOutput]):
    name = "alpha_neutron_split"
    version = "v1.0"

    def run(self, **kwargs) -> ModuleResult[AlphaNeutronSplitOutput]:
        return ModuleResult(
            data=AlphaNeutronSplitOutput(
                p_alpha=PowerValue(value=520.5),
                p_neutron=PowerValue(value=2079.4),
            )
        )
```

**YAML:**
```yaml
split:
  module_type: AlphaNeutronSplitModule
  inputs:
    # ... inputs
  outputs:
    p_alpha: PowerValue alpha_channel      # Field 1 → alpha_channel
    p_neutron: PowerValue neutron_channel  # Field 2 → neutron_channel
```

**How it works:**

1. Module returns `MultiOutput` instance
2. Executor detects `isinstance(data, MultiOutput)` (see `simkit/core/pipeline_executor.py:195-206`)
3. Executor calls `data.to_channel_dict()` to extract fields
4. Each field is routed to its declared channel

**Why use MultiOutput?**

- ✅ Type-safe (no `# type: ignore` needed)
- ✅ Introspectable by `create_registry()` (auto-registration works)
- ✅ Self-documenting (signals multi-output intent)
- ✅ Better than legacy `Dict[str, BaseModel]` pattern

**Key Files:**
- `simkit/config/schema.py:28-74` - `MultiOutput` class
- `simkit/core/pipeline_executor.py:195-228` - Multi-output detection and routing

---

## I/O System

### Loading Input Data

The `EntryPoint` module loads data files using type-specific readers.

**Key File:** `simkit/io/readers.py` - Core file loading functions

**Core formats (teax-simkit):**

| File Type | Loader Function | Model Type |
|-----------|-----------------|------------|
| JSON | `read_json_model()` | Any `BaseModel` subclass |

**Battery demo formats (battery_tea.io):**

| File Type | Loader Function | Model Type |
|-----------|-----------------|------------|
| Parquet (load) | `read_parquet_load_profile()` | `LoadProfile8760` |
| Parquet (PV) | `read_parquet_pv_profile()` | `PVProfile8760` |

**Entry loader registry:** `simkit/core/pipeline_executor.py` - EntryPoint loading and path resolution

**Adding custom loaders:**

**Using custom schemas:**

The recommended approach is to use the `custom_schema_types` parameter in `execute_pipeline()`. This automatically registers custom types for EntryPoint loading, field reference validation, and ExitPoint writing:

```python
from simkit.core.pipeline import execute_pipeline
from custom_pkg.schemas import MyCustomType

result = execute_pipeline(
    "pipeline.yaml",
    "outputs/",
    custom_schema_types=[MyCustomType],  # Auto-registers JSON loader
)
```

All custom types default to JSON serialization via `read_json_model()`. For schemas requiring special loaders (Parquet, custom parsing), you can manually create entry loaders and pass them via the executor (advanced use case).

### Saving Output Data

The `ExitPoint` module serializes outputs using the `OutputRouter`.

**Key File:** `simkit/io/output_router.py` - Handles output serialization

**Core output handlers (teax-simkit):**

| Model Type | Serialization | Extension |
|------------|---------------|-----------|
| Any `BaseModel` | JSON | `.json` |

**Battery demo handlers (battery_tea.io):**

| Model Type | Serialization | Extension |
|------------|---------------|-----------|
| `BatteryTelemetry8760` | Parquet | `.parquet` |
| `SyncTelemetrySeries` | Parquet | `.parquet` |

**Directory structure:**
```
outputs/
  <run_name>_<timestamp>/
    rate_info.json
    telemetry.parquet
    manifest.json          # RunManifest with provenance
```

**Adding custom handlers:**

There are two approaches for custom schema serialization:

**Option 1: Using `custom_schema_types` parameter (recommended):**

```python
from custom_pkg.schemas import MyCustomType

# Automatically creates OutputRouter with custom types registered for JSON
result = execute_pipeline(
    "spec.yaml",
    "outputs/",
    custom_schema_types=[MyCustomType],
)
```

**Option 2: Manual OutputRouter creation:**

```python
from simkit.io.output_router import create_output_router_with_json_schemas

# Register custom schemas for JSON serialization
router = create_output_router_with_json_schemas(["MyCustomType"])

# Pass to execute_pipeline
result = execute_pipeline("spec.yaml", "outputs/", output_router=router)
```

**Key Function:** `simkit/io/output_router.py:create_output_router_with_json_schemas()` - Registers JSON handlers

---

## Custom Module Registration

### Using `create_registry()`

TEAx provides **automatic module registration** through type introspection, eliminating manual `ModuleDescriptor` creation.

**Key File:** `simkit/core/registry_builder.py:9-128` - Registry builder implementation

### Custom Schema Registration

TEAx supports **custom Pydantic schema types** for use in EntryPoint inputs, ExitPoint outputs, and field references. This enables external packages to define their own data models without modifying TEAx core.

**Using `custom_schema_types` parameter:**

```python
from simkit.core.pipeline import execute_pipeline
from custom_pkg.schemas import FusionParams, PlasmaParams

# Register custom schemas for use in pipeline
result = execute_pipeline(
    "fusion_pipeline.yaml",
    "outputs/",
    custom_schema_types=[FusionParams, PlasmaParams],
)
```

**What `custom_schema_types` enables:**

1. **EntryPoint loading**: Custom types can be loaded from JSON files in EntryPoint inputs
2. **Field reference validation**: Custom types can be used in field references (e.g., `fusion_params.blanket_config`)
3. **ExitPoint writing**: Custom types are automatically registered for JSON serialization

**Requirements:**
- Each custom type must be a Pydantic `BaseModel` subclass
- Type names must be unique (cannot conflict with built-in types or other custom types)
- All custom types default to JSON serialization

**Key Files:**
- `simkit/core/pipeline_executor.py:401-509` - Schema type registry building
- `simkit/core/pipeline_executor.py:512-540` - Entry loader building

**Basic usage:**

```python
from simkit.core.registry_builder import create_registry
from simkit.core.pipeline import execute_pipeline

# Define your modules (must inherit ModuleBase[InputModel, OutputModel])
class MyModule1(ModuleBase[Input1, Output1]):
    name = "my_module_1"
    version = "v1.0"
    # ... implement validate_and_fill_default() and run()

class MyModule2(ModuleBase[Input2, Output2]):
    name = "my_module_2"
    version = "v1.0"
    # ... implement validate_and_fill_default() and run()

# Create registry from module classes
registry = create_registry([MyModule1, MyModule2])

# Execute pipeline with custom registry
result = execute_pipeline("pipeline.yaml", "outputs/", registry=registry)
```

### Using Domain-Specific Modules

The core framework has no built-in modules. Use domain packages like `battery-tea-demo`:

```python
# Use battery demo modules
from battery_tea import create_battery_registry
from battery_tea.schemas import Geography, RateInfo

registry = create_battery_registry()
result = execute_pipeline(
    "pipeline.yaml",
    registry=registry,
    custom_schema_types=[Geography, RateInfo],
)
```

### Overriding Module Names

```python
# Change module_type names (useful for avoiding conflicts)
registry = create_registry(
    [MyModule1],
    module_type_override={
        MyModule1: "CustomName"  # Use "CustomName" in YAML instead of "MyModule1"
    }
)
```

### External Package Pattern

External packages should provide a convenience function (see `battery-tea-demo` for a complete example):

```python
# In my_domain/__init__.py
from simkit.core.registry_builder import create_registry
from .modules import MyModule1, MyModule2
from .schemas import MySchema1, MySchema2

def create_my_domain_registry():
    """Create registry with all domain modules."""
    return create_registry([MyModule1, MyModule2])

# Users import and use
from my_domain import create_my_domain_registry
from my_domain.schemas import MySchema1, MySchema2
from simkit.core.pipeline import execute_pipeline

registry = create_my_domain_registry()
result = execute_pipeline(
    "my_pipeline.yaml",
    "outputs/",
    registry=registry,
    custom_schema_types=[MySchema1, MySchema2],
)
```

### Requirements for Auto-Registration

Your module **must**:

1. ✅ Inherit directly from `ModuleBase[InputModel, OutputModel]`
2. ✅ Use Pydantic `BaseModel` subclasses for both type parameters
3. ✅ Define `name` class attribute (string)
4. ✅ Define `version` class attribute (string)

Auto-registration **will fail** if:

- ❌ InputModel or OutputModel are not `BaseModel` subclasses
- ❌ Module uses indirect inheritance (e.g., abstract base class between your module and `ModuleBase`)
- ❌ Type parameters are not explicitly specified

**Key File:** `simkit/core/module_introspector.py` - Introspection logic for extracting module metadata

---

## Debugging Guide

### Common Issues and Solutions

#### 1. Pipeline Validation Errors

**Error:** `PipelineValidationError: Channel 'xyz' not produced during execution`

**Cause:** YAML references a channel that no module produces.

**Debug:**
1. Check `simkit/core/pipeline_validator.py:validate()` - Validates channel bindings
2. Verify all input bindings reference existing output channels
3. Check for typos in channel names

#### 2. Module Not Found

**Error:** `ModuleNotFoundError: Module type 'MyModule' not registered`

**Cause:** Module not in registry.

**Debug:**
1. Verify `create_registry([YourModule])` includes your module class
2. Check `module_type` in YAML matches class name (or override)
3. Inspect `simkit/core/pipeline_registry.py:40-51` - Registry lookup logic

#### 3. Type Mismatch

**Error:** `PipelineValidationError: Type mismatch for channel 'xyz'`

**Cause:** Producer outputs type A, consumer expects type B.

**Debug:**
1. Check `simkit/core/pipeline_validator.py` - Type checking logic
2. Verify output type in producer's YAML matches input type in consumer's YAML
3. Types must match **exactly** (no subclass polymorphism)

#### 4. Multi-Output Field Missing

**Error:** `RuntimeError: Module 'xyz' MultiOutput missing field 'abc'`

**Cause:** YAML declares output field not present in `MultiOutput` container.

**Debug:**
1. Check `simkit/core/pipeline_executor.py:195-228` - Multi-output extraction logic
2. Verify all fields in YAML `outputs:` exist in your `MultiOutput` subclass
3. Check spelling and capitalization

#### 5. EntryPoint File Not Found

**Error:** `FileNotFoundError: File not found: /path/to/file.json`

**Cause:** Input file path cannot be resolved.

**Debug:**
1. Check `simkit/core/pipeline_executor.py:230-307` - Path resolution logic
2. Verify file exists relative to YAML location
3. Check `$PYRONDO_INPUT_DIR` environment variable
4. Try absolute paths for testing

#### 6. Field Reference Validation Error

**Error:** `PipelineValidationError: Type 'ParentType' has no field 'field_name'`

**Cause:** Field reference points to non-existent field.

**Debug:**
1. Check `simkit/core/pipeline_validator.py:162-238` - Field reference validation logic
2. Verify field name spelling matches parent model exactly
3. Check error message for list of available fields
4. Ensure field is not private (starts with `_`) or computed (`@computed_field`)

#### 7. Field Reference Runtime Error

**Error:** `PipelineExecutionError: Field 'xyz' on channel 'abc' is None`

**Cause:** Optional field has None value at runtime.

**Debug:**
1. Check `simkit/core/pipeline_executor.py:352-398` - Runtime extraction logic
2. Verify field is populated in parent object before extraction
3. Consider using standard binding if field can be None

### Execution Flow (For Debugging)

Understanding the execution flow helps trace issues:

```
1. execute_pipeline(spec_path, output_dir, registry, output_router, custom_schema_types)
   ↓
2. entry_point_validate(spec_path)  [simkit/core/pipeline.py:33]
   → Loads and validates YAML specification
   ↓
3. Build schema registries (if custom_schema_types provided)
   → _build_schema_type_registry() - Maps type names to classes
   → _build_entry_loaders() - Maps types to loader functions
   ↓
4. PipelineValidator.validate(spec)  [simkit/core/pipeline_validator.py]
   → Type checks all bindings, validates field references, builds DAG
   ↓
5. SerialPipelineExecutor.build_graph(spec)  [simkit/core/pipeline_executor.py:101]
   → Returns PipelineGraph with topological order
   ↓
6. SerialPipelineExecutor.run(graph, context)  [simkit/core/pipeline_executor.py:104]
   → Executes modules in topological order:
     a. _execute_entry() - Loads EntryPoint files using entry loaders
     b. _execute_module() - Runs each module
        - Gathers inputs from channels (with field extraction if needed)
        - Calls module.run(**kwargs)
        - Routes outputs to channels (MultiOutput extraction if needed)
     c. ExitPoint - Collects outputs for persistence
   ↓
7. OutputRouter.write_outputs()  [simkit/io/output_router.py:60]
   → Serializes outputs to files using registered handlers
   ↓
8. Build provenance and metadata
   → _build_provenance() - Creates config hash, module versions
   → _build_pipeline_metadata() - Creates run metadata
   ↓
9. Returns RunResult with outputs, manifest, provenance, pipeline_metadata
```

### Key Files for Debugging

| Issue | File | Line |
|-------|------|------|
| YAML parsing | `simkit/io/readers.py` | 84 |
| Field reference parsing | `simkit/config/pipeline_schema.py` | 240-303 |
| Pipeline validation | `simkit/core/pipeline_validator.py` | entire file |
| Field reference validation | `simkit/core/pipeline_validator.py` | 162-238 |
| DAG building | `simkit/core/pipeline_graph.py` | entire file |
| Module execution | `simkit/core/pipeline_executor.py` | 178-228 |
| Field extraction | `simkit/core/pipeline_executor.py` | 295-341 |
| Multi-output routing | `simkit/core/pipeline_executor.py` | 195-228 |
| EntryPoint loading | `simkit/core/pipeline_executor.py` | 164-177 |
| Output serialization | `simkit/io/output_router.py` | entire file |
| Type introspection | `simkit/core/module_introspector.py` | entire file |
| Registry building | `simkit/core/registry_builder.py` | 9-128 |
| Schema type registry | `simkit/core/pipeline_executor.py` | 401-509 |
| Entry loader building | `simkit/core/pipeline_executor.py` | 512-540 |

---

## API Reference

### Core Functions

#### `execute_pipeline()`

**Location:** `simkit/core/pipeline.py:71-210`

```python
def execute_pipeline(
    spec_path: str | Path,
    output_dir: str | Path | None = None,
    registry: PipelineModuleRegistry | None = None,
    output_router: OutputRouter | None = None,
    custom_schema_types: list[type] | None = None,
) -> RunResult:
    """Execute pipeline with optional custom module registry and schema types."""
```

**Parameters:**
- `spec_path`: Path to YAML pipeline specification
- `output_dir`: Directory for outputs (defaults to temp dir)
- `registry`: Custom module registry (defaults to built-in modules)
- `output_router`: Custom output handler. If None and `custom_schema_types` provided, auto-creates router with custom types registered for JSON serialization. If both None, uses default router with built-in schemas only.
- `custom_schema_types`: Optional list of custom Pydantic schema type classes. Enables three features for custom schemas:
  1. EntryPoint artifact loading (auto-registers JSON loaders)
  2. Field reference validation (resolves types in validator)
  3. ExitPoint output writing (auto-creates OutputRouter unless explicit router provided)
  
  All custom types default to JSON serialization. For schemas requiring special loaders (Parquet, custom parsing), future enhancement will add `custom_entry_loaders` parameter.

**Returns:** `RunResult` with:
- `outputs`: Dict of channel names → values
- `manifest`: File locations and provenance
- `module_versions`: Module versions used in execution
- `pipeline_metadata`: Pipeline run metadata
- `provenance`: Execution provenance with config hash

**Example:**
```python
# Execute with built-in modules and schemas (backward compatible)
result = execute_pipeline("demo_pipeline.yaml", "outputs/")

# Execute with custom modules and schemas
from simkit.core.registry_builder import create_registry
from custom_pkg import CustomModule
from custom_pkg.schemas import CustomSchema

registry = create_registry([CustomModule])
result = execute_pipeline(
    "custom_pipeline.yaml",
    "outputs/",
    registry=registry,
    custom_schema_types=[CustomSchema],
)
```

#### `create_registry()`

**Location:** `simkit/core/registry_builder.py`

```python
def create_registry(
    modules: List[Type[ModuleBase]],
    module_type_override: Dict[Type[ModuleBase], str] | None = None,
) -> PipelineModuleRegistry:
    """Create PipelineModuleRegistry from module classes via introspection."""
```

**Parameters:**
- `modules`: List of `ModuleBase` subclasses to register
- `module_type_override`: Map module classes to custom names

**Returns:** `PipelineModuleRegistry` ready for pipeline execution

**Raises:**
- `ModuleIntrospectionError`: Module structure invalid
- `ValueError`: Duplicate module names detected

### Data Classes

#### `ModuleBase[InputModel, OutputModel]`

**Location:** `simkit/core/base.py:19-29`

Base class for all pipeline modules.

**Attributes:**
- `name: str` - Module identifier
- `version: str` - Version string for provenance

**Methods:**
- `validate_and_fill_default(**kwargs) -> InputModel` - Validate inputs
- `run(**kwargs) -> ModuleResult[OutputModel]` - Execute module logic

#### `ModuleResult[OutputModel]`

**Location:** `simkit/core/base.py:14-16`

Container for module execution results.

**Attributes:**
- `data: OutputModel` - Module output data
- `notes: str | None` - Optional execution notes

#### `MultiOutput`

**Location:** `simkit/config/schema.py:28-74`

Base class for multi-output modules.

**Methods:**
- `to_channel_dict() -> Dict[str, BaseModel]` - Extract fields for routing

#### `RunResult`

**Location:** `simkit/core/pipeline_executor.py:52-60`

Pipeline execution results.

**Attributes:**
- `outputs: Mapping[str, Any]` - Output channel values
- `manifest: RunManifest | None` - File locations and metadata
- `module_versions: Mapping[str, str]` - Module versions used
- `pipeline_metadata: PipelineRunMetadata | None` - Pipeline metadata
- `provenance: Provenance | None` - Execution provenance

---

## Design Philosophy

### Type Safety

TEAx enforces **compile-time and runtime type safety**:

- Pydantic models validate data at module boundaries
- Pipeline validator checks type compatibility before execution
- Type introspection enables automatic registry building

### Functional Composition

Modules are **pure functions** with no side effects:

- Inputs → Outputs (no hidden state)
- I/O isolated to EntryPoint/ExitPoint boundaries
- Enables testing, caching, and parallel execution (future)

### Provenance and Reproducibility

Every execution tracks:

- Module versions used
- Config hash (deterministic YAML fingerprint)
- Input file locations
- Output file locations
- Execution timestamp

**Key Files:**
- `simkit/config/schema.py` - `Provenance`, `RunManifest` models
- `simkit/core/pipeline.py:41-62` - Provenance building logic

### Progressive Enhancement

The system supports **multiple usage modes**:

1. **Domain packages** - Use pre-built packages like `battery-tea-demo`
2. **Custom modules with auto-registration** - `create_registry([YourModule])`
3. **Manual registration** - Direct `ModuleDescriptor` creation (advanced)

---

## Additional Resources

- **Design Docs:** `thoughts/designs/generalized_teax_type_system_design.md`
- **Field Referencing:** `thoughts/specs/field_referencing_spec.md`
- **Project Instructions:** `CLAUDE.md` (developer-focused)
- **Example Pipeline:** `packages/battery-tea-demo/battery_tea/tests/fixtures/pipeline_configs/demo_linear_alt.yaml`
- **Module Examples:** `packages/battery-tea-demo/battery_tea/modules/` (rate_data, cost_calc, etc.)

---

## Migration Guide

This section documents the changes made when separating the codebase into `teax-simkit` (core framework) and `battery-tea-demo` (example implementation).

### Import Changes

| Old Import | New Import |
|------------|------------|
| `from simkit.config.schema import BatteryConfig` | `from battery_tea.schemas import BatteryConfig` |
| `from simkit.config.schema import BatteryState` | `from battery_tea.schemas import BatteryState` |
| `from simkit.config.schema import Geography` | `from battery_tea.schemas import Geography` |
| `from simkit.config.schema import LoadProfile8760` | `from battery_tea.schemas import LoadProfile8760` |
| `from simkit.config.schema import RateInfo` | `from battery_tea.schemas import RateInfo` |
| `from simkit.config.battery_schema import *` | `from battery_tea.schemas import *` |
| `from simkit.core.battery_config import ConfigureBatteryModule` | `from battery_tea.modules import ConfigureBatteryModule` |
| `from simkit.core.rate_data import RateDataModule` | `from battery_tea.modules import RateDataModule` |
| `from simkit.core import ConfigureBatteryModule` | `from battery_tea.modules import ConfigureBatteryModule` |
| `from simkit.io.readers import read_parquet_load_profile` | `from battery_tea.io import read_parquet_load_profile` |
| `from simkit.io.writers import write_parquet_telemetry` | `from battery_tea.io import write_parquet_telemetry` |

### Registry Changes

| Old Pattern | New Pattern |
|-------------|-------------|
| `PipelineModuleRegistry.from_static_modules()` | `from battery_tea import create_battery_registry; create_battery_registry()` |
| `create_registry([...], include_builtins=True)` | `create_registry([...])` (no builtins exist) |

### Pipeline YAML Changes

Pipeline YAML files that use battery modules need to pass the battery registry:

```python
from battery_tea import create_battery_registry
from battery_tea.schemas import Geography, RateInfo, LoadProfile8760
from simkit.core.pipeline import execute_pipeline

result = execute_pipeline(
    "my_pipeline.yaml",
    output_dir="outputs/",
    registry=create_battery_registry(),
    custom_schema_types=[Geography, RateInfo, LoadProfile8760],
)
```

### Directory Structure Changes

| Old Location | New Location |
|--------------|--------------|
| `simkit/` | `packages/teax-simkit/simkit/` |
| `simkit/core/rate_data/` | `packages/battery-tea-demo/battery_tea/modules/rate_data/` |
| `simkit/core/battery_config/` | `packages/battery-tea-demo/battery_tea/modules/battery_config/` |
| `simkit/config/battery_schema.py` | `packages/battery-tea-demo/battery_tea/schemas.py` |
| `simkit/config/defaults.py` (battery parts) | `packages/battery-tea-demo/battery_tea/defaults.py` |
| `simkit/tests/fixtures/` (battery fixtures) | `packages/battery-tea-demo/battery_tea/tests/fixtures/` |
| `notebooks/` | `packages/battery-tea-demo/notebooks/` |

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/anthropics/claude-code/issues
- Source Code: `packages/teax-simkit/` (core), `packages/battery-tea-demo/` (example)

---

**Last Updated:** 2026-01-04
**TEAx Version:** 0.1.0
**Python Requirement:** 3.10+
