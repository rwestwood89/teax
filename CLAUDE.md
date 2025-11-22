# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

TEAx Simulation Environment (simkit) is a modular battery techno-economic analysis (TEA) framework. The system follows a functional module pattern where each module has typed inputs/outputs, validation, and can be composed into pipelines via YAML configuration.

## Build & Development Commands

```bash
# Create virtual environment and install package
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]

# Run all tests
pytest

# Run specific test or test pattern
pytest simkit/tests/test_pipeline.py -k happy_path
pytest simkit/tests/pipeline_modules/test_rate_data.py

# Run single test file
pytest simkit/tests/core/test_pipeline_executor.py
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

Key model families:
- **Geography, LoadProfile8760, PVProfile8760, RateInfo**: Input data
- **BatteryConfig, BatteryTelemetry8760**: Battery system specifications and simulation results
- **CostBreakdown, FinancialResults**: Economic analysis outputs
- **SyncTimeGrid, BatteryState, PriceTrajectory**: Synchronous simulation inputs
- **Provenance, PipelineRunMetadata, RunManifest**: Pipeline execution metadata
- **MultiOutput**: Base class for modules with multiple typed outputs (see Multi-Output Modules above)

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
# Load module and fixtures
from simkit.core.rate_data import RateDataModule
module = RateDataModule()

# Validate and run
inputs = module.validate_and_fill_default(geography=geo)
result = module.run(inputs)
rate_info = result.data
```

See `notebooks/manual_mode_demo.ipynb` for example.

### Module Registry & Custom Modules

**Built-in modules** (registered in `PipelineModuleRegistry.from_static_modules()`):
- `RateData`: Geography → RateInfo
- `ConfigureBattery`: LoadProfile + RateInfo → BatteryConfig
- `SimplePerformanceSim`: BatteryConfig + LoadProfile → BatteryTelemetry (rule-based, no physics)
- `SynchronousSim`: Time-stepped simulation with forecasting/guidance/dynamics components
- `CostCalculator`: BatteryConfig + Geography → CostBreakdown
- `ProjectAnalyzer`: RateInfo + Telemetry → FinancialResults

**Custom modules** can be registered via `simkit/core/registry_builder.py`:
```python
from simkit.core.registry_builder import create_registry
from simkit.core.pipeline import execute_pipeline

# Define module class inheriting ModuleBase[InputModel, OutputModel]
registry = create_registry([MyCustomModule], include_builtins=True)

# Pass registry to pipeline
result = execute_pipeline("spec.yaml", "outputs/", registry=registry)
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
simkit/
  core/              # Module implementations and pipeline orchestration
    rate_data/       # RateData module
    battery_config/  # ConfigureBattery module
    cost_calc/       # CostCalculator module
    perf_sim_simple/ # SimplePerformanceSim module (rule-based)
    synchronous_sim/ # SynchronousSim module (time-stepped physics)
    project_analyzer/# ProjectAnalyzer module
    base.py          # ModuleBase interface
    pipeline.py      # execute_pipeline entrypoint
    pipeline_executor.py     # SerialPipelineExecutor
    pipeline_registry.py     # PipelineModuleRegistry
    registry_builder.py      # create_registry for custom modules
    module_introspector.py   # Auto-extract module metadata
  config/
    schema.py        # Pydantic data models (Geography, RateInfo, BatteryConfig, etc.)
    defaults.py      # Default values and unit constants
    flags.py         # Feature flags (minimal)
    pipeline_schema.py # YAML spec structure
    environment.py   # Environment variable handling (PYRONDO_INPUT_DIR)
  io/
    readers.py       # Load JSON/Parquet/YAML fixtures
    writers.py       # Persist outputs
    output_router.py # Route outputs to directories
    adapters/        # External data source stubs
  tests/
    pipeline_modules/  # Module unit tests (test_rate_data.py, etc.)
    core/              # Pipeline/executor tests
    fixtures/          # Small JSON/Parquet test inputs
      pipeline_configs/  # Example YAML pipeline specs
    conftest.py        # Pytest fixtures (geography, load profiles, rate info)
notebooks/           # Jupyter demos (manual_mode_demo.ipynb)
thoughts/            # Design docs, plans, notes
  designs/
  plans/
```

## Testing Guidelines

- Tests mirror package structure: `simkit/tests/pipeline_modules/test_*.py` for each module
- Fixtures in `simkit/tests/fixtures/`: `geography_us_ca_pge.json`, `load_profile_toy_8760.parquet`, etc.
- Reusable pytest fixtures in `conftest.py`

For each module, test:
1. **`validate_and_fill_default`**:
   - Invalid input raises validation error
   - Complete valid input unchanged
   - Incomplete input filled with defaults

2. **`run`**:
   - Invalid/incomplete input raises error (defensive check)
   - Valid input produces correct types and invariants (e.g., telemetry SOC within bounds, no energy creation)

Run tests before PRs: `pytest`

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

When adding new modules:
1. Define input/output Pydantic models in `simkit/config/schema.py`
2. Create module class in `simkit/core/<module_name>/module.py`
3. Implement `ModuleBase[InputModel, OutputModel]` with `validate_and_fill_default` + `run`
4. Add tests in `simkit/tests/pipeline_modules/test_<module_name>.py`
5. Register in `PipelineModuleRegistry.from_static_modules()` or use `create_registry([YourModule])`

External packages (e.g., `fusion_simkit`) should provide a `create_<package>_registry()` function that calls `create_registry([...module_classes])`.

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
