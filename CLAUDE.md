# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

TEAx Simulation Environment (simkit) is a **generic simulation pipeline framework** for building techno-economic analysis (TEA) systems. The framework provides:

- **teax-simkit** (`packages/teax-simkit/`): Core framework with typed modules, pipeline execution, and YAML configuration
- **battery-tea-demo** (`packages/battery-tea-demo/`): Example implementation demonstrating battery storage TEA

The system follows a functional module pattern where each module has typed inputs/outputs, validation, and can be composed into pipelines via YAML configuration.

## Build & Development Commands

```bash
# Create virtual environment and install packages
python -m venv .venv && source .venv/bin/activate

# Install both packages for development
pip install -e packages/teax-simkit[dev]
pip install -e packages/battery-tea-demo[dev]

# Or install from root (workspace mode)
pip install -e .[dev]

# Run all tests (from root)
pytest

# Run framework tests only
pytest packages/teax-simkit/

# Run battery demo tests only
pytest packages/battery-tea-demo/

# Run specific test file
pytest packages/teax-simkit/simkit/tests/core/test_pipeline_executor.py
```

## Core Architecture

### Module Pattern

All pipeline modules inherit from `ModuleBase[InputModel, OutputModel]` (in `simkit/core/base.py`) and implement:

1. **`validate_and_fill_default(*args, **kwargs) -> InputModel`**
   - Validates all inputs before execution
   - Fills missing optional parameters from `simkit/config/defaults.py`
   - Returns validated, complete input model
   - Must use Pydantic models from `simkit/config/schema.py`

2. **`run(*args, **kwargs) -> ModuleResult[OutputModel]`**
   - Pure function: inputs → outputs (no I/O inside)
   - Returns `ModuleResult` wrapping output data + optional notes
   - Must validate inputs defensively even if caller used `validate_and_fill_default`

Each module declares `name` (str) and `version` (str) class attributes for provenance tracking.

#### Single-Output vs. Multi-Output Modules

**Single-Output Modules** (most common):
```python
class SimpleModule(ModuleBase[MyInput, MyOutput]):
    name = "simple"
    version = "v1.0"

    def run(self, **kwargs) -> ModuleResult[MyOutput]:
        # Process inputs...
        return ModuleResult(data=MyOutput(...))
```

The entire `MyOutput` object is assigned to the channel specified in YAML.

**Multi-Output Modules** (when routing different types to different downstream modules):
```python
from simkit.config.schema import MultiOutput

# Define output container
class MyMultiOutput(MultiOutput):
    """Container for multiple typed outputs."""
    field_a: TypeA
    field_b: TypeB

class MultiModule(ModuleBase[MyInput, MyMultiOutput]):
    name = "multi"
    version = "v1.0"

    def run(self, **kwargs) -> ModuleResult[MyMultiOutput]:
        # Process inputs...
        return ModuleResult(
            data=MyMultiOutput(
                field_a=TypeA(...),
                field_b=TypeB(...),
            )
        )
```

In YAML, declare each field as a separate output:
```yaml
multi_module:
  module_type: MultiModule
  outputs:
    field_a: TypeA channel_a
    field_b: TypeB channel_b
```

The executor automatically extracts each field from `MyMultiOutput` and routes them to separate channels.

**Why use MultiOutput?**
- Type-safe (no `# type: ignore` needed)
- Introspectable by `create_registry()` (auto-registration works)
- Self-documenting (signals multi-output intent)
- Better than legacy `Dict[str, BaseModel]` pattern (which violates TypeVar constraints)

### Data Models

All data models in `simkit/config/schema.py` extend `StrictBaseModel`:
- Frozen (immutable)
- Extra fields forbidden
- Strict validation with units explicit (e.g., `"kWh"`, `"USD"`)
- Arrays are length-validated (e.g., 8760 for hourly profiles)

**Primitive types** (built-in, no registration required):
- **float, int, str, bool**: Supported as first-class types in EntryPoint/ExitPoint and pipeline channels. Serialized as raw JSON (e.g., `42.0`, `"hello"`, `true`). Commonly produced by MultiOutput modules with bare primitive fields.

**Framework types** (in `simkit/config/schema.py`):
- **StrictBaseModel, MultiOutput**: Base types for custom schemas
- **TimeSpan, SyncTimeGrid, PriceTrajectory**: Time-series and simulation inputs
- **FinancialParams, FinancialResults**: Economic analysis
- **Provenance, PipelineRunMetadata, RunManifest**: Pipeline execution metadata

**Battery demo types** (in `battery_tea/schemas.py` - example implementation):
- **Geography, LoadProfile8760, RateInfo**: Input data
- **BatteryConfig, BatteryTelemetry8760, BatteryState**: Battery specifications and simulation
- **CostBreakdown**: Cost analysis outputs

### Pipeline Execution Modes

**1. Pipeline Mode (YAML-driven)**

YAML spec defines a DAG of modules with typed channel bindings:
```yaml
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
```

Execute via:
```python
from simkit.core.pipeline import execute_pipeline

result = execute_pipeline("spec.yaml", output_dir="outputs/")
# result.outputs: Dict[str, Any] with all produced channels
# result.provenance: config hash, module versions
```

Pipeline spec references in `inputs` support:
- Literal file paths (absolute or relative to spec file)
- Environment variable prefix: `PYRONDO_INPUT_DIR` (defaults to `<repo>/run_data/inputs`)
- Path resolution attempts literal first, then prefixed with `PYRONDO_INPUT_DIR`

**2. Manual Mode (Notebook)**

Call modules step-by-step, optionally substituting manual artifacts:
```python
# Example using battery-tea-demo modules
from battery_tea.modules import RateDataModule
module = RateDataModule()

# Validate and run
inputs = module.validate_and_fill_default(geography=geo)
result = module.run(inputs)
rate_info = result.data
```

See `packages/battery-tea-demo/notebooks/manual_mode_demo.ipynb` for example.

### Module Registry & Custom Modules

The core framework provides no built-in modules. Domain-specific modules are provided by external packages like `battery-tea-demo`.

**Battery demo modules** (in `battery_tea.modules`):
- `RateData`: Geography → RateInfo
- `ConfigureBattery`: LoadProfile + RateInfo → BatteryConfig
- `SimplePerformanceSim`: BatteryConfig + LoadProfile → BatteryTelemetry (rule-based)
- `SynchronousSim`: Time-stepped simulation with forecasting/guidance/dynamics
- `CostCalculator`: BatteryConfig + Geography → CostBreakdown
- `ProjectAnalyzer`: RateInfo + Telemetry → FinancialResults

**Custom modules** are registered via `simkit/core/registry_builder.py`:
```python
from simkit.core.registry_builder import create_registry
from simkit.core.pipeline import execute_pipeline

# Define module class inheriting ModuleBase[InputModel, OutputModel]
registry = create_registry([MyCustomModule])

# Pass registry to pipeline
result = execute_pipeline("spec.yaml", "outputs/", registry=registry)
```

**Using battery-tea-demo modules:**
```python
from battery_tea import create_battery_registry
from simkit.core.pipeline import execute_pipeline

registry = create_battery_registry()
result = execute_pipeline("battery_pipeline.yaml", "outputs/", registry=registry)
```

Module introspection (`simkit/core/module_introspector.py`) automatically extracts input/output schemas from type hints.

### I/O System

- **Readers** (`simkit/io/readers.py`): Load JSON, Parquet, YAML fixtures
- **Writers** (`simkit/io/writers.py`): Persist outputs as JSON/Parquet
- **OutputRouter** (`simkit/io/output_router.py`): Routes module outputs to timestamped directories with typed serialization

Entry/Exit points:
- `EntryPoint`: Validates all input artifacts exist before pipeline starts (fail-fast)
- `ExitPoint`: Aggregates outputs into structured bundle with provenance

## Directory Structure

```
teax/
├── packages/
│   ├── teax-simkit/                 # Core framework (pip-installable)
│   │   ├── simkit/
│   │   │   ├── core/                # Pipeline orchestration
│   │   │   │   ├── base.py          # ModuleBase interface
│   │   │   │   ├── pipeline.py      # execute_pipeline entrypoint
│   │   │   │   ├── pipeline_executor.py
│   │   │   │   ├── pipeline_registry.py
│   │   │   │   ├── registry_builder.py
│   │   │   │   └── module_introspector.py
│   │   │   ├── config/
│   │   │   │   ├── schema.py        # Generic Pydantic models
│   │   │   │   ├── defaults.py      # Default values
│   │   │   │   ├── pipeline_schema.py
│   │   │   │   └── environment.py
│   │   │   ├── io/
│   │   │   │   ├── readers.py       # Load JSON/YAML
│   │   │   │   ├── writers.py       # Persist outputs
│   │   │   │   └── output_router.py
│   │   │   └── tests/               # Framework tests
│   │   └── pyproject.toml
│   │
│   └── battery-tea-demo/            # Example implementation
│       ├── battery_tea/
│       │   ├── schemas.py           # Battery-specific models
│       │   ├── defaults.py          # Battery defaults
│       │   ├── registry.py          # create_battery_registry()
│       │   ├── io.py                # Battery I/O (Parquet readers/writers)
│       │   ├── modules/             # Battery modules
│       │   │   ├── rate_data/
│       │   │   ├── battery_config/
│       │   │   ├── cost_calc/
│       │   │   ├── perf_sim_simple/
│       │   │   ├── project_analyzer/
│       │   │   └── synchronous_sim/
│       │   └── tests/               # Battery module tests
│       │       └── fixtures/        # Test data
│       ├── notebooks/               # Jupyter demos
│       └── pyproject.toml
│
├── thoughts/                        # Design docs, plans, notes
├── CLAUDE.md
├── README.md
└── pyproject.toml                   # Workspace root
```

## Testing Guidelines

**Framework tests** (`packages/teax-simkit/simkit/tests/`):
- Core pipeline, executor, validator, registry tests
- Generic fixtures for framework testing
- No battery dependencies

**Battery demo tests** (`packages/battery-tea-demo/battery_tea/tests/`):
- Module tests in `tests/modules/test_*.py`
- Fixtures in `tests/fixtures/`: `geography_us_ca_pge.json`, `load_profile_toy_8760.parquet`, etc.
- Integration tests in `tests/test_integration.py`

For each module, test:
1. **`validate_and_fill_default`**:
   - Invalid input raises validation error
   - Complete valid input unchanged
   - Incomplete input filled with defaults

2. **`run`**:
   - Invalid/incomplete input raises error (defensive check)
   - Valid input produces correct types and invariants

Run tests before PRs: `pytest` (runs both packages from root)

## Coding Conventions

- Python 3.10+, 4-space indentation
- Type hints required
- Pydantic models for all data payloads (mimic patterns in `schema.py`)
- Module names lowercase_with_underscores
- Classes PascalCase (e.g., `ProjectAnalyzerModule`)
- Test functions `test_*`
- No inline magic constants: use `config/defaults.py`

## Key Design Principles

1. **Modularity**: Functional modules with pure inputs → outputs
2. **Explicit schemas**: Pydantic models validated early, version-controlled
3. **Progressive automation**: Manual notebook mode → automated pipeline mode
4. **Provenance**: Config hashes, module versions, run metadata persisted with outputs
5. **Environment integration**: `.env` loaded before pipeline execution; `PYRONDO_INPUT_DIR` for input resolution

## Important Files for Context

- `tea_simulation_design_doc.md`: Overall design philosophy and patterns
- `sim_demo_plan.md`: Async pipeline demo plan (module contracts, acceptance criteria)
- `AGENTS.md`: Existing repository guidelines (superset of this file)

## Custom Module Development Pattern

When adding new modules to your own package:
1. Define input/output Pydantic models in your package's `schemas.py`
2. Create module class inheriting from `ModuleBase[InputModel, OutputModel]`
3. Implement `validate_and_fill_default` + `run` methods
4. Add tests for your module
5. Create a registry function using `create_registry([YourModule])`

**Example package structure** (see `battery-tea-demo` for reference):
```
my_domain_package/
├── schemas.py           # Domain-specific Pydantic models
├── defaults.py          # Domain-specific defaults
├── registry.py          # create_my_domain_registry() function
├── modules/
│   └── my_module/
│       └── module.py
└── tests/
```

External packages should provide a `create_<package>_registry()` function:
```python
# In my_package/registry.py
from simkit.core.registry_builder import create_registry
from .modules import MyModule1, MyModule2

def create_my_package_registry():
    return create_registry([MyModule1, MyModule2])
```

## Custom Schema Development Pattern

TEAx supports custom Pydantic schema types for EntryPoint loading, field reference validation, and ExitPoint output. This enables external packages to define domain-specific data models while integrating seamlessly with the pipeline system.

### Quick Start: Using Custom Schemas

```python
from pydantic import BaseModel
from simkit.config.schema import StrictBaseModel
from simkit.core.pipeline import execute_pipeline

# Define your custom schema (use StrictBaseModel for immutability)
class FusionParams(StrictBaseModel):
    plasma_temperature: float  # keV
    confinement_time: float    # seconds
    beta_n: float              # normalized beta

# Use in pipeline - auto-registers JSON loader and OutputRouter handler
result = execute_pipeline(
    "fusion_pipeline.yaml",
    "outputs/",
    custom_schema_types=[FusionParams],
)
```

### Pipeline YAML with Custom Schemas

```yaml
modules:
  entry:
    module_type: EntryPoint
    inputs:
      params: FusionParams fusion_params.json  # Loads custom type
    outputs:
      params: FusionParams params

  analyzer:
    module_type: PlasmaAnalyzer
    inputs:
      temperature: RootModel[float] params.plasma_temperature  # Field extraction
    outputs:
      analysis: AnalysisResult result

  exit:
    module_type: ExitPoint
    outputs:
      analysis: AnalysisResult result.json  # Writes custom type
```

### Custom Schema Requirements

**All custom schema types must:**
1. Be Pydantic `BaseModel` subclasses (preferably `StrictBaseModel`)
2. Have unique `__name__` (no conflicts with built-in TEAx types or other custom types)
3. Be JSON-serializable (default Pydantic behavior)

**Automatic features provided:**
- **EntryPoint loading**: JSON deserialization via `readers.read_json_model()`
- **Field reference validation**: Type resolution in `PipelineValidator`
- **ExitPoint writing**: JSON serialization via auto-created `OutputRouter`

### Advanced: Custom Loaders (Future Enhancement)

For schemas requiring non-JSON formats (Parquet, HDF5, custom binary), future versions will support:

```python
# Future API (not yet implemented)
custom_loaders = {
    FusionProfile: lambda path: load_hdf5_fusion_profile(path),
    PlasmaState: lambda path: load_parquet_plasma_state(path),
}

result = execute_pipeline(
    "pipeline.yaml",
    custom_schema_types=[FusionProfile, PlasmaState],
    custom_entry_loaders=custom_loaders,  # Future parameter
)
```

Currently, all custom schemas default to JSON. For specialized formats, preprocess data to JSON or use custom OutputRouter.

### Testing Custom Schemas

```python
from simkit.core.pipeline_executor import _build_schema_type_registry, _build_entry_loaders

# Unit test schema registration
def test_fusion_schema_registration():
    registry = _build_schema_type_registry([FusionParams])
    assert "FusionParams" in registry
    assert registry["FusionParams"] is FusionParams

# Unit test entry loader
def test_fusion_entry_loader(tmp_path):
    loaders = _build_entry_loaders([FusionParams])

    # Create test file
    test_file = tmp_path / "params.json"
    test_file.write_text(json.dumps({
        "plasma_temperature": 10.0,
        "confinement_time": 0.5,
        "beta_n": 2.5
    }))

    # Load using generated loader
    obj = loaders[FusionParams](test_file)
    assert isinstance(obj, FusionParams)
    assert obj.plasma_temperature == 10.0
```

### Error Handling

**Common errors and solutions:**

1. **`TypeError: Custom schema type must be a Pydantic BaseModel subclass`**
   - Solution: Ensure type inherits from `BaseModel` or `StrictBaseModel`

2. **`ValueError: Duplicate schema type name 'Geography'`**
   - Solution: Rename custom type to avoid conflict with built-in

3. **`ValueError: Unknown schema type 'FusionParams'`**
   - Solution: Add type to `custom_schema_types` parameter

4. **`PipelineValidationError: ExitPoint output type has no registered write handler`**
   - Solution: Include type in `custom_schema_types` (auto-creates handler) or provide explicit `output_router`

### Package Integration Example

External packages should expose a registry function:

```python
# In fusion_simkit/registry.py
from simkit.core.registry_builder import create_registry
from .schemas import FusionParams, PlasmaProfile, AnalysisResult
from .modules import PlasmaAnalyzer, FusionOptimizer

def create_fusion_registry():
    """Create TEAx registry with Fusion modules."""
    return create_registry([PlasmaAnalyzer, FusionOptimizer])

# Usage
from fusion_simkit import create_fusion_registry
from fusion_simkit.schemas import FusionParams, PlasmaProfile

result = execute_pipeline(
    "fusion_pipeline.yaml",
    registry=create_fusion_registry(),
    custom_schema_types=[FusionParams, PlasmaProfile],
)
```
