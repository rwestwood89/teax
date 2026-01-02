# Simkit/Battery Demo Separation - Implementation Plan

**Document Type:** Implementation Plan
**Version:** v1.0
**Status:** Draft
**Owner:** Reid Westwood
**Last Updated:** 2026-01-01
**Related Docs:**
- Research: `thoughts/research/20260101-163700_simkit-battery-separation.md`

## Overview

Separate the TEAx codebase into two packages:
1. **`teax-simkit`** - Generic simulation framework (pip-installable)
2. **`battery-tea-demo`** - Battery TEA example implementation (not built by default)

**Approach:** Clean break with no backwards compatibility. Single consumer will follow migration guide.

## Target Directory Structure

```
teax/
├── packages/
│   ├── teax-simkit/
│   │   ├── simkit/
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── pipeline.py
│   │   │   │   ├── pipeline_executor.py
│   │   │   │   ├── pipeline_graph.py
│   │   │   │   ├── pipeline_registry.py
│   │   │   │   ├── pipeline_validator.py
│   │   │   │   ├── registry_builder.py
│   │   │   │   └── module_introspector.py
│   │   │   ├── config/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── schema.py
│   │   │   │   ├── pipeline_schema.py
│   │   │   │   ├── environment.py
│   │   │   │   ├── flags.py
│   │   │   │   └── time_utils.py
│   │   │   ├── io/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── readers.py
│   │   │   │   ├── writers.py
│   │   │   │   └── output_router.py
│   │   │   └── tests/
│   │   │       ├── __init__.py
│   │   │       ├── conftest.py
│   │   │       ├── core/
│   │   │       ├── io/
│   │   │       ├── pipeline/
│   │   │       └── fixtures/
│   │   └── pyproject.toml
│   │
│   └── battery-tea-demo/
│       ├── battery_tea/
│       │   ├── __init__.py
│       │   ├── schemas.py
│       │   ├── defaults.py
│       │   ├── registry.py
│       │   └── modules/
│       │       ├── __init__.py
│       │       ├── rate_data/
│       │       ├── battery_config/
│       │       ├── perf_sim_simple/
│       │       ├── cost_calc/
│       │       ├── project_analyzer/
│       │       └── synchronous_sim/
│       ├── tests/
│       │   ├── __init__.py
│       │   ├── conftest.py
│       │   ├── fixtures/
│       │   └── modules/
│       ├── notebooks/
│       ├── README.md
│       └── pyproject.toml
│
├── README.md
├── pyproject.toml
├── CLAUDE.md
└── thoughts/
```

---

## Phase 1: Create Generic Framework Test Foundation

### Overview
Establish battery-free test infrastructure so core framework can be tested independently. This ensures we can verify framework functionality after removing battery code.

### Test Stencil
```python
# Test stencil for generic framework tests
# File: packages/teax-simkit/simkit/tests/test_toy_pipeline.py

def test_toy_pipeline_executes_two_modules():
    """E2E test: ToyModule pipeline without any battery dependencies."""
    from simkit.core.registry_builder import create_registry
    from simkit.core.pipeline import execute_pipeline

    # Uses toy_linear.yaml which references ToyDoubler and ToyAdder modules
    registry = create_registry([ToyDoublerModule, ToyAdderModule])
    result = execute_pipeline(
        "fixtures/pipeline_configs/toy_linear.yaml",
        output_dir=tmp_path,
        registry=registry,
    )

    assert result.success
    assert "doubled" in result.outputs
    assert "added" in result.outputs
    assert result.outputs["added"].value == 42.0  # (10 * 2) + 22
```

### Changes Required

#### 1. Create ToyModule Definitions
**File:** `simkit/tests/core/toy_modules.py` (NEW)

- [ ] Create `ToyInput` schema (value: float)
- [ ] Create `ToyOutput` schema (value: float)
- [ ] Create `ToyDoublerModule` - doubles input value
- [ ] Create `ToyAdderModule` - adds constant to input
- [ ] Create `ToyMultiOutputModule` - produces two outputs (for multi-output testing)

```python
from pydantic import BaseModel
from simkit.core.base import ModuleBase, ModuleResult
from simkit.config.schema import MultiOutput


class ToyInput(BaseModel):
    value: float


class ToyOutput(BaseModel):
    value: float


class ToyDoublerModule(ModuleBase[ToyInput, ToyOutput]):
    """Doubles input value. For framework testing."""
    name = "ToyDoubler"
    version = "v1.0"

    def validate_and_fill_default(self, value: float) -> ToyInput:
        return ToyInput(value=value)

    def run(self, value: float) -> ModuleResult[ToyOutput]:
        validated = self.validate_and_fill_default(value)
        return ModuleResult(data=ToyOutput(value=validated.value * 2.0))


class ToyAdderModule(ModuleBase[ToyInput, ToyOutput]):
    """Adds 22 to input value. For framework testing."""
    name = "ToyAdder"
    version = "v1.0"

    def validate_and_fill_default(self, value: float) -> ToyInput:
        return ToyInput(value=value)

    def run(self, value: float) -> ModuleResult[ToyOutput]:
        validated = self.validate_and_fill_default(value)
        return ModuleResult(data=ToyOutput(value=validated.value + 22.0))
```

#### 2. Create Generic Test Pipeline YAML
**File:** `simkit/tests/fixtures/pipeline_configs/toy_linear.yaml` (NEW)

- [ ] Define EntryPoint loading `toy_input.json`
- [ ] Define ToyDoubler module
- [ ] Define ToyAdder module
- [ ] Define ExitPoint writing outputs

```yaml
modules:
  entry:
    module_type: EntryPoint
    inputs:
      input_value: ToyInput toy_input.json
    outputs:
      input_value: ToyInput input_value

  doubler:
    module_type: ToyDoubler
    inputs:
      value: RootModel[float] input_value.value
    outputs:
      doubled: ToyOutput doubled

  adder:
    module_type: ToyAdder
    inputs:
      value: RootModel[float] doubled.value
    outputs:
      added: ToyOutput added

  exit:
    module_type: ExitPoint
    outputs:
      doubled: ToyOutput doubled.json
      added: ToyOutput added.json
```

#### 3. Create Test Input Fixture
**File:** `simkit/tests/fixtures/toy_input.json` (NEW)

- [ ] Create minimal JSON input for ToyInput schema

```json
{"value": 10.0}
```

#### 4. Create Generic Pipeline E2E Test
**File:** `simkit/tests/test_toy_pipeline.py` (NEW)

- [ ] Test `execute_pipeline()` with ToyModule registry
- [ ] Test in-memory mode (no file output)
- [ ] Test with file output to tmp_path
- [ ] Verify channel values are correct

#### 5. Update Existing Framework Tests to Not Require Battery
**File:** `simkit/tests/core/test_pipeline_executor_entry.py`

- [ ] Review tests - if they use `Geography` fixture, create equivalent with `ToyInput`
- [ ] Add parallel test using ToyInput for path resolution testing

**File:** `simkit/tests/core/test_pipeline_executor_field_reference.py`

- [ ] Review and add ToyModule-based field reference test

### Success Criteria

#### Automated Verification:
- [ ] `pytest simkit/tests/test_toy_pipeline.py` passes
- [ ] `pytest simkit/tests/core/toy_modules.py` passes (if any unit tests)
- [ ] All existing tests still pass (no regressions)

#### Manual Verification:
- [ ] ToyModule tests exercise same code paths as battery tests (registry, executor, validator)
- [ ] No imports from battery modules in new test files

---

## Phase 2: Split Schema File

### Overview
Separate generic framework types from battery-specific types. Generic types stay in `simkit/config/schema.py`. Battery types move to a new file that will later move to `battery_tea/schemas.py`.

### Test Stencil
```python
# Test stencil for schema split verification
# File: simkit/tests/config/test_schema_split.py

def test_generic_schemas_importable():
    """Verify generic schemas are still in simkit.config.schema."""
    from simkit.config.schema import (
        StrictBaseModel,
        MultiOutput,
        Provenance,
        PipelineRunMetadata,
        TimeSpan,
        SyncTimeGrid,
        PriceTrajectory,
        FinancialParams,
    )
    assert StrictBaseModel is not None


def test_battery_schemas_in_separate_file():
    """Verify battery schemas moved to battery_schema.py."""
    from simkit.config.battery_schema import (
        BatteryConfig,
        BatteryTelemetry8760,
        BatteryState,
        CostBreakdown,
    )
    assert BatteryConfig is not None
```

### Changes Required

#### 1. Create Battery Schema File
**File:** `simkit/config/battery_schema.py` (NEW)

- [ ] Add file header and imports
- [ ] Move `Geography` (lines 105-111)
- [ ] Move `LoadProfile8760` (lines 113-132) with validators
- [ ] Move `PVProfile8760` (lines 134-153) with validators
- [ ] Move `RateInfo` (lines 155-180) with validators
- [ ] Move `DesignPrefs` (lines 182-195) with validator
- [ ] Move `BatteryConfig` (lines 197-210)
- [ ] Move `CostLineItem` (lines 212-219)
- [ ] Move `CostBreakdown` (lines 221-229)
- [ ] Move `BatteryTelemetry8760` (lines 231-245) with validator
- [ ] Move `BatteryState` (lines 542-565) with validator
- [ ] Move `GuidanceConfig` (lines 622-642) with validator
- [ ] Move `DynamicsInitInput` (lines 680-684)
- [ ] Move `SyncTelemetryFrame` (lines 692-715) with validator
- [ ] Move `SyncTelemetrySeries` (lines 717-723)
- [ ] Move `SyncSimOutputs` (lines 737-746) with validator
- [ ] Import generic types from `schema.py` as needed (StrictBaseModel, MultiOutput, TimeSpan, etc.)

#### 2. Clean Up Generic Schema File
**File:** `simkit/config/schema.py`

- [ ] Remove all battery-specific types listed above
- [ ] Keep: `StrictBaseModel`, `MultiOutput`
- [ ] Keep: `TimeSpan`, `SyncOuterStep`, `InnerLoopConfig`, `SyncTimeGrid`
- [ ] Keep: `PriceTrajectory`, `PriceTrajectoryWindow`
- [ ] Keep: `FinancialParams`, `CashflowEntry`, `LedgerEntry`, `FinancialResults`
- [ ] Keep: `Provenance`, `PipelineRunMetadata`, `RunArtifactRecord`, `RunManifest`
- [ ] Keep: `MockForecastMetadata`, `MockForecastConfig`, `MockForecastPoint`, `MockForecastSeries`
- [ ] Keep: `GuidanceMetadata`, `SyncGuidance`, `SyncGuidanceSeries`
- [ ] Keep: `DynamicSimConfig`, `DynamicsStepInput`
- [ ] Keep: `ensure_outer_indices_match()` function
- [ ] Verify no circular imports

#### 3. Update Battery Module Imports
**Files:** All files in `simkit/core/battery_config/`, `simkit/core/cost_calc/`, `simkit/core/perf_sim_simple/`, `simkit/core/project_analyzer/`, `simkit/core/synchronous_sim/`, `simkit/core/rate_data/`

- [ ] Update `from ..config import schema` → `from ..config import battery_schema`
- [ ] Or update individual imports to use `battery_schema.BatteryConfig` etc.

#### 4. Update Pipeline Executor
**File:** `simkit/core/pipeline_executor.py`

- [ ] Update `_build_schema_type_registry()` to import battery schemas from `battery_schema`
- [ ] Update `_DEFAULT_ENTRY_LOADERS` to import from `battery_schema`

#### 5. Update Output Router
**File:** `simkit/io/output_router.py`

- [ ] Update `create_default_router()` to import battery schemas from `battery_schema`

#### 6. Update Test Imports
**Files:** All test files that import battery schemas

- [ ] `simkit/tests/conftest.py` - update schema imports
- [ ] `simkit/tests/fixtures/__init__.py` - update schema imports
- [ ] `simkit/tests/pipeline_modules/*.py` - update schema imports
- [ ] `simkit/tests/core/test_custom_schema_registration.py` - update imports
- [ ] `simkit/tests/io/test_output_router.py` - update imports

### Success Criteria

#### Automated Verification:
- [ ] `pytest simkit/tests/` passes (all tests)
- [ ] `python -c "from simkit.config.schema import StrictBaseModel, MultiOutput"` works
- [ ] `python -c "from simkit.config.battery_schema import BatteryConfig, BatteryState"` works

#### Manual Verification:
- [ ] `schema.py` contains only generic types (~300 lines)
- [ ] `battery_schema.py` contains all battery types (~450 lines)
- [ ] No circular import errors

---

## Phase 3: Create Package Directory Structure

### Overview
Create the `packages/` directory structure and move simkit to `packages/teax-simkit/`. This phase only restructures directories without changing code.

### Test Stencil
```python
# Test stencil: verify package structure
# Run from repo root after restructure

def test_package_structure_exists():
    """Verify directory structure is correct."""
    import os

    assert os.path.isdir("packages/teax-simkit/simkit")
    assert os.path.isdir("packages/teax-simkit/simkit/core")
    assert os.path.isdir("packages/teax-simkit/simkit/config")
    assert os.path.isdir("packages/teax-simkit/simkit/io")
    assert os.path.isfile("packages/teax-simkit/pyproject.toml")

    assert os.path.isdir("packages/battery-tea-demo/battery_tea")
    assert os.path.isfile("packages/battery-tea-demo/pyproject.toml")
```

### Changes Required

#### 1. Create Package Directories
- [ ] `mkdir -p packages/teax-simkit`
- [ ] `mkdir -p packages/battery-tea-demo/battery_tea/modules`
- [ ] `mkdir -p packages/battery-tea-demo/battery_tea/tests/fixtures`
- [ ] `mkdir -p packages/battery-tea-demo/battery_tea/tests/modules`

#### 2. Move Core Framework
- [ ] `mv simkit/ packages/teax-simkit/simkit/`

#### 3. Create teax-simkit pyproject.toml
**File:** `packages/teax-simkit/pyproject.toml` (NEW)

- [ ] Set name = "teax-simkit"
- [ ] Set version = "0.1.0"
- [ ] Set description = "Generic simulation pipeline framework"
- [ ] Copy dependencies from root pyproject.toml
- [ ] Configure pytest paths

```toml
[project]
name = "teax-simkit"
version = "0.1.0"
description = "Generic simulation pipeline framework for techno-economic analysis"
requires-python = ">=3.10"
dependencies = [
  "pydantic>=2.5",
  "numpy>=1.23",
  "pandas>=1.5",
  "pyarrow>=12",
  "PyYAML>=6.0",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=7.3",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["simkit/tests"]
addopts = "-q"
```

#### 4. Create battery-tea-demo pyproject.toml
**File:** `packages/battery-tea-demo/pyproject.toml` (NEW)

- [ ] Set name = "battery-tea-demo"
- [ ] Set version = "0.1.0"
- [ ] Add dependency on teax-simkit (path reference for local dev)

```toml
[project]
name = "battery-tea-demo"
version = "0.1.0"
description = "Battery TEA example implementation using teax-simkit"
requires-python = ">=3.10"
dependencies = [
  "teax-simkit",  # Will resolve via path in dev
]

[project.optional-dependencies]
dev = [
  "pytest>=7.3",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]

[tool.pytest.ini_options]
pythonpath = [".", "../teax-simkit"]
testpaths = ["battery_tea/tests", "tests"]
addopts = "-q"
```

#### 5. Update Root pyproject.toml
**File:** `pyproject.toml`

- [ ] Convert to workspace configuration
- [ ] Update pytest to run both packages

```toml
[project]
name = "teax"
version = "0.1.0"
description = "TEAx Simulation Environment - Workspace Root"
requires-python = ">=3.10"

[tool.pytest.ini_options]
pythonpath = ["packages/teax-simkit", "packages/battery-tea-demo"]
testpaths = [
  "packages/teax-simkit/simkit/tests",
  "packages/battery-tea-demo/battery_tea/tests",
]
addopts = "-q"
```

#### 6. Create battery_tea Package Init
**File:** `packages/battery-tea-demo/battery_tea/__init__.py` (NEW)

- [ ] Add package docstring
- [ ] Placeholder for future exports

```python
"""Battery TEA example implementation using teax-simkit framework."""

__version__ = "0.1.0"
```

### Success Criteria

#### Automated Verification:
- [ ] `pytest` from root runs tests from both packages
- [ ] `cd packages/teax-simkit && pip install -e . && python -c "from simkit.core import ModuleBase"`
- [ ] Directory structure matches target layout

#### Manual Verification:
- [ ] `packages/teax-simkit/simkit/` contains all framework code
- [ ] `packages/battery-tea-demo/battery_tea/` exists with `__init__.py`
- [ ] Root `simkit/` directory no longer exists

---

## Phase 4: Extract Battery Modules to Demo Package

### Overview
Move all 6 battery modules from `packages/teax-simkit/simkit/core/` to `packages/battery-tea-demo/battery_tea/modules/`. Update all imports.

### Test Stencil
```python
# Test stencil for battery module migration
# File: packages/battery-tea-demo/battery_tea/tests/test_battery_registry.py

def test_create_battery_registry():
    """Verify battery registry can be created from demo package."""
    from battery_tea.registry import create_battery_registry

    registry = create_battery_registry()

    assert registry.has("RateData")
    assert registry.has("ConfigureBattery")
    assert registry.has("SimplePerformanceSim")
    assert registry.has("CostCalculator")
    assert registry.has("ProjectAnalyzer")
    assert registry.has("SynchronousSim")


def test_battery_pipeline_executes():
    """E2E test: battery pipeline runs with battery registry."""
    from battery_tea.registry import create_battery_registry
    from simkit.core.pipeline import execute_pipeline

    registry = create_battery_registry()
    result = execute_pipeline(
        "fixtures/pipeline_configs/demo_linear_alt.yaml",
        output_dir=tmp_path,
        registry=registry,
    )

    assert result.success
    assert "financial_results" in result.outputs
```

### Changes Required

#### 1. Move Battery Schemas
**From:** `packages/teax-simkit/simkit/config/battery_schema.py`
**To:** `packages/battery-tea-demo/battery_tea/schemas.py`

- [ ] Move entire file
- [ ] Update imports to reference `simkit.config.schema` for base types

```python
"""Battery TEA schema types."""
from simkit.config.schema import (
    StrictBaseModel,
    MultiOutput,
    TimeSpan,
    SyncOuterStep,
    # ... other generic types needed
)

# All battery types here...
```

#### 2. Move Battery Defaults
**From:** `packages/teax-simkit/simkit/config/defaults.py` (battery parts)
**To:** `packages/battery-tea-demo/battery_tea/defaults.py` (NEW)

- [ ] Create new file with battery-specific defaults
- [ ] Move: `DEFAULT_ROUNDTRIP_EFFICIENCY`, `DEFAULT_SOC_MIN`, `DEFAULT_SOC_MAX`, `DEFAULT_BATTERY_NOTES`
- [ ] Move: `default_design_prefs()` function
- [ ] Keep generic defaults in original file: `DEFAULT_DISCOUNT_RATE`, `DEFAULT_ANALYSIS_YEARS`, etc.

#### 3. Move Rate Data Module
**From:** `packages/teax-simkit/simkit/core/rate_data/`
**To:** `packages/battery-tea-demo/battery_tea/modules/rate_data/`

- [ ] Move `module.py` and `__init__.py`
- [ ] Update imports: `from battery_tea.schemas import Geography, RateInfo`
- [ ] Update imports: `from simkit.core.base import ModuleBase, ModuleResult`

#### 4. Move Battery Config Module
**From:** `packages/teax-simkit/simkit/core/battery_config/`
**To:** `packages/battery-tea-demo/battery_tea/modules/battery_config/`

- [ ] Move `module.py` and `__init__.py`
- [ ] Update imports to use `battery_tea.schemas`
- [ ] Update imports to use `battery_tea.defaults`

#### 5. Move Performance Sim Module
**From:** `packages/teax-simkit/simkit/core/perf_sim_simple/`
**To:** `packages/battery-tea-demo/battery_tea/modules/perf_sim_simple/`

- [ ] Move `module.py` and `__init__.py`
- [ ] Update imports

#### 6. Move Cost Calculator Module
**From:** `packages/teax-simkit/simkit/core/cost_calc/`
**To:** `packages/battery-tea-demo/battery_tea/modules/cost_calc/`

- [ ] Move `module.py` and `__init__.py`
- [ ] Update imports

#### 7. Move Project Analyzer Module
**From:** `packages/teax-simkit/simkit/core/project_analyzer/`
**To:** `packages/battery-tea-demo/battery_tea/modules/project_analyzer/`

- [ ] Move `module.py` and `__init__.py`
- [ ] Update imports

#### 8. Move Synchronous Sim Module
**From:** `packages/teax-simkit/simkit/core/synchronous_sim/`
**To:** `packages/battery-tea-demo/battery_tea/modules/synchronous_sim/`

- [ ] Move `module.py`, `guidance.py`, `dynamics.py`, `forecast.py`, `__init__.py`
- [ ] Update imports in all files

#### 9. Create Battery Modules Init
**File:** `packages/battery-tea-demo/battery_tea/modules/__init__.py` (NEW)

- [ ] Export all module classes

```python
"""Battery TEA modules."""
from .rate_data import RateDataModule
from .battery_config import ConfigureBatteryModule
from .perf_sim_simple import SimplePerformanceSimModule
from .cost_calc import CostCalculatorModule
from .project_analyzer import ProjectAnalyzerModule
from .synchronous_sim import SynchronousSimModule

__all__ = [
    "RateDataModule",
    "ConfigureBatteryModule",
    "SimplePerformanceSimModule",
    "CostCalculatorModule",
    "ProjectAnalyzerModule",
    "SynchronousSimModule",
]
```

#### 10. Create Battery Registry
**File:** `packages/battery-tea-demo/battery_tea/registry.py` (NEW)

- [ ] Create `create_battery_registry()` function using `simkit.core.registry_builder.create_registry()`

```python
"""Battery TEA module registry."""
from simkit.core.registry_builder import create_registry

from .modules import (
    RateDataModule,
    ConfigureBatteryModule,
    SimplePerformanceSimModule,
    CostCalculatorModule,
    ProjectAnalyzerModule,
    SynchronousSimModule,
)


def create_battery_registry():
    """Create registry with all battery TEA modules."""
    return create_registry([
        RateDataModule,
        ConfigureBatteryModule,
        SimplePerformanceSimModule,
        CostCalculatorModule,
        ProjectAnalyzerModule,
        SynchronousSimModule,
    ])
```

#### 11. Update battery_tea Package Init
**File:** `packages/battery-tea-demo/battery_tea/__init__.py`

- [ ] Export registry function and key schemas

```python
"""Battery TEA example implementation using teax-simkit framework."""
from .registry import create_battery_registry
from .schemas import (
    BatteryConfig,
    BatteryState,
    BatteryTelemetry8760,
    CostBreakdown,
    Geography,
    LoadProfile8760,
    RateInfo,
)

__version__ = "0.1.0"
__all__ = [
    "create_battery_registry",
    "BatteryConfig",
    "BatteryState",
    "BatteryTelemetry8760",
    "CostBreakdown",
    "Geography",
    "LoadProfile8760",
    "RateInfo",
]
```

### Success Criteria

#### Automated Verification:
- [ ] `cd packages/battery-tea-demo && pip install -e . && python -c "from battery_tea import create_battery_registry"`
- [ ] `python -c "from battery_tea.modules import ConfigureBatteryModule"`
- [ ] `python -c "from battery_tea.schemas import BatteryConfig"`

#### Manual Verification:
- [ ] No battery module directories in `packages/teax-simkit/simkit/core/`
- [ ] All 6 modules exist in `packages/battery-tea-demo/battery_tea/modules/`
- [ ] `battery_schema.py` no longer exists in teax-simkit

---

## Phase 5: Clean Core Framework

### Overview
Remove all battery coupling from teax-simkit. Delete `from_static_modules()`, remove battery schemas from hardcoded registries, clean up exports.

### Test Stencil
```python
# Test stencil: verify core is battery-free
# File: packages/teax-simkit/simkit/tests/test_no_battery_deps.py

def test_core_init_has_no_battery_exports():
    """Verify simkit.core doesn't export battery modules."""
    from simkit import core

    assert not hasattr(core, "ConfigureBatteryModule")
    assert not hasattr(core, "CostCalculatorModule")
    assert not hasattr(core, "BatteryConfig")

    # Framework exports should exist
    assert hasattr(core, "ModuleBase")
    assert hasattr(core, "ModuleResult")
    assert hasattr(core, "PipelineModuleRegistry")


def test_schema_has_no_battery_types():
    """Verify simkit.config.schema has no battery types."""
    from simkit.config import schema

    assert not hasattr(schema, "BatteryConfig")
    assert not hasattr(schema, "BatteryState")
    assert not hasattr(schema, "BatteryTelemetry8760")

    # Generic types should exist
    assert hasattr(schema, "StrictBaseModel")
    assert hasattr(schema, "MultiOutput")
    assert hasattr(schema, "PriceTrajectory")


def test_registry_has_no_from_static_modules():
    """Verify from_static_modules() is removed."""
    from simkit.core.pipeline_registry import PipelineModuleRegistry

    assert not hasattr(PipelineModuleRegistry, "from_static_modules")
```

### Changes Required

#### 1. Clean Core __init__.py
**File:** `packages/teax-simkit/simkit/core/__init__.py`

- [ ] Remove imports of battery modules
- [ ] Remove battery modules from `__all__`
- [ ] Keep only framework exports

```python
"""Core functional modules for simulation pipelines."""
from .base import ModuleBase, ModuleResult
from .pipeline_executor import PipelineExecutionContext, SerialPipelineExecutor
from .pipeline_graph import PipelineDagBuilder, PipelineGraph
from .pipeline_registry import ModuleDescriptor, PipelineModuleRegistry
from .pipeline_validator import PipelineValidationError, PipelineValidator
from .registry_builder import create_registry
from .module_introspector import ModuleIntrospector

__all__ = [
    "ModuleBase",
    "ModuleResult",
    "PipelineDagBuilder",
    "PipelineGraph",
    "PipelineExecutionContext",
    "SerialPipelineExecutor",
    "PipelineModuleRegistry",
    "ModuleDescriptor",
    "PipelineValidator",
    "PipelineValidationError",
    "create_registry",
    "ModuleIntrospector",
]
```

#### 2. Remove from_static_modules()
**File:** `packages/teax-simkit/simkit/core/pipeline_registry.py`

- [ ] Delete `from_static_modules()` method (lines 46-148)
- [ ] Remove battery module imports (lines 11-16)
- [ ] Remove `from ..config import schema` if only used for battery types

#### 3. Clean Pipeline Executor
**File:** `packages/teax-simkit/simkit/core/pipeline_executor.py`

- [ ] Remove battery schema imports
- [ ] Update `_build_schema_type_registry()` to only include generic types
- [ ] Update `_DEFAULT_ENTRY_LOADERS` to only include generic loaders
- [ ] Remove hardcoded battery schema references

Before (lines 449-468):
```python
registry = {
    schema.Geography.__name__: schema.Geography,
    schema.BatteryConfig.__name__: schema.BatteryConfig,
    # ... more battery types
}
```

After:
```python
registry = {
    schema.FinancialParams.__name__: schema.FinancialParams,
    schema.PriceTrajectory.__name__: schema.PriceTrajectory,
    schema.SyncTimeGrid.__name__: schema.SyncTimeGrid,
    # ... only generic types
}
```

#### 4. Clean Output Router
**File:** `packages/teax-simkit/simkit/io/output_router.py`

- [ ] Remove battery schema imports
- [ ] Update `create_default_router()` to only include generic handlers
- [ ] Remove handlers for: `BatteryConfig`, `CostBreakdown`, `BatteryTelemetry8760`

#### 5. Clean Defaults File
**File:** `packages/teax-simkit/simkit/config/defaults.py`

- [ ] Remove battery-specific defaults (already moved in Phase 4)
- [ ] Remove `default_design_prefs()` function
- [ ] Keep generic financial defaults

#### 6. Clean Writers
**File:** `packages/teax-simkit/simkit/io/writers.py`

- [ ] Review `write_parquet_telemetry()` - keep if generic, update docstring
- [ ] Remove any battery-specific type hints

### Success Criteria

#### Automated Verification:
- [ ] `pytest packages/teax-simkit/simkit/tests/` passes
- [ ] `pytest packages/teax-simkit/simkit/tests/test_no_battery_deps.py` passes
- [ ] `grep -r "BatteryConfig" packages/teax-simkit/` returns nothing
- [ ] `grep -r "from_static_modules" packages/teax-simkit/` returns nothing

#### Manual Verification:
- [ ] `simkit/core/__init__.py` has no battery imports
- [ ] `simkit/config/schema.py` has no battery types
- [ ] `PipelineModuleRegistry` has no `from_static_modules()` method

---

## Phase 6: Migrate Tests and Fixtures

### Overview
Move battery test fixtures and module tests to battery-tea-demo. Update pytest configuration for workspace.

### Test Stencil
```python
# Test stencil: battery tests run from demo package
# File: packages/battery-tea-demo/battery_tea/tests/modules/test_battery_config.py

def test_configure_battery_module(load_profile_fixture, rate_info_fixture):
    """Test ConfigureBatteryModule produces valid BatteryConfig."""
    from battery_tea.modules import ConfigureBatteryModule
    from battery_tea.schemas import BatteryConfig

    module = ConfigureBatteryModule()
    result = module.run(
        load_profile=load_profile_fixture,
        rate_info=rate_info_fixture,
    )

    assert isinstance(result.data, BatteryConfig)
    assert result.data.capacity_kwh > 0
```

### Changes Required

#### 1. Move Battery Test Fixtures
**From:** `packages/teax-simkit/simkit/tests/fixtures/`
**To:** `packages/battery-tea-demo/battery_tea/tests/fixtures/`

- [ ] Move `geography_us_ca_pge.json`
- [ ] Move `load_profile_toy_8760.parquet`
- [ ] Move `load_profile_flat_8760.parquet`
- [ ] Move `rateinfo_tou_synthetic.json`
- [ ] Move `financial_params_demo.json`
- [ ] Move `synchronous_sim/` directory (all contents)
- [ ] Move `pipeline_configs/demo_linear_alt.yaml`
- [ ] Move `pipeline_configs/synchronous_sim_stubbed.yaml`

#### 2. Move Battery Module Tests
**From:** `packages/teax-simkit/simkit/tests/pipeline_modules/`
**To:** `packages/battery-tea-demo/battery_tea/tests/modules/`

- [ ] Move `test_rate_data.py`
- [ ] Move `test_battery_config.py`
- [ ] Move `test_cost_calc.py`
- [ ] Move `test_perf_sim_simple.py`
- [ ] Move `test_project_analyzer.py`
- [ ] Move `test_synchronous_sim.py`
- [ ] Update all imports in moved files

#### 3. Move Battery Integration Tests
**From:** `packages/teax-simkit/simkit/tests/`
**To:** `packages/battery-tea-demo/battery_tea/tests/`

- [ ] Move `test_pipeline.py` → `test_battery_pipeline.py`
- [ ] Move `test_pipeline_synchronous_sim.py`
- [ ] Update imports to use `battery_tea` package

#### 4. Create Battery Test Conftest
**File:** `packages/battery-tea-demo/battery_tea/tests/conftest.py` (NEW)

- [ ] Move battery fixtures from `simkit/tests/conftest.py`
- [ ] Update imports to use `battery_tea.schemas`

```python
"""Pytest fixtures for battery TEA tests."""
import pytest
from pathlib import Path

from battery_tea.schemas import (
    Geography,
    LoadProfile8760,
    RateInfo,
    FinancialParams,
)
from battery_tea.defaults import default_design_prefs

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def geography_us_ca():
    from simkit.io.readers import read_json_model
    return read_json_model(FIXTURES_DIR / "geography_us_ca_pge.json", Geography)


@pytest.fixture
def rate_info_synth():
    from simkit.io.readers import read_json_model
    return read_json_model(FIXTURES_DIR / "rateinfo_tou_synthetic.json", RateInfo)


@pytest.fixture
def load_profile_flat():
    from simkit.io.readers import read_parquet_load_profile
    return read_parquet_load_profile(FIXTURES_DIR / "load_profile_flat_8760.parquet")


@pytest.fixture
def load_profile_toy():
    from simkit.io.readers import read_parquet_load_profile
    return read_parquet_load_profile(FIXTURES_DIR / "load_profile_toy_8760.parquet")


@pytest.fixture
def design_prefs_default():
    return default_design_prefs()


@pytest.fixture
def financial_params_demo():
    from simkit.io.readers import read_json_model
    return read_json_model(FIXTURES_DIR / "financial_params_demo.json", FinancialParams)
```

#### 5. Clean Framework Test Conftest
**File:** `packages/teax-simkit/simkit/tests/conftest.py`

- [ ] Remove battery fixtures (moved to battery-tea-demo)
- [ ] Keep any generic fixtures needed for framework tests
- [ ] Add ToyModule fixtures if needed

#### 6. Update Framework Tests That Used Battery Fixtures
**Files:** Various in `packages/teax-simkit/simkit/tests/core/`

- [ ] `test_custom_schema_registration.py` - use custom schemas instead of battery
- [ ] `test_pipeline_executor_entry.py` - use ToyInput instead of Geography
- [ ] Any other tests - update to use generic fixtures

#### 7. Move Fixtures Init
**File:** `packages/battery-tea-demo/battery_tea/tests/fixtures/__init__.py` (NEW)

- [ ] Move sample data generators from `simkit/tests/fixtures/__init__.py`
- [ ] Update imports

#### 8. Move Notebooks
**From:** `notebooks/`
**To:** `packages/battery-tea-demo/notebooks/`

- [ ] Move `manual_mode_demo.ipynb`
- [ ] Update imports in notebook to use `battery_tea` package

#### 9. Update Root pytest.ini
**File:** `pyproject.toml`

- [ ] Ensure pytest discovers both package test directories

### Success Criteria

#### Automated Verification:
- [ ] `pytest packages/teax-simkit/` passes (framework tests only)
- [ ] `pytest packages/battery-tea-demo/` passes (battery tests only)
- [ ] `pytest` from root passes (both)
- [ ] No test files remain in `packages/teax-simkit/simkit/tests/pipeline_modules/`

#### Manual Verification:
- [ ] All battery fixtures in `packages/battery-tea-demo/battery_tea/tests/fixtures/`
- [ ] Framework tests don't import from `battery_tea`
- [ ] Battery tests import from both `battery_tea` and `simkit`

---

## Phase 7: Documentation and Cleanup

### Overview
Update all documentation to reflect new package structure. Create migration guide. Clean up any remaining references.

### Changes Required

#### 1. Update CLAUDE.md
**File:** `CLAUDE.md`

- [ ] Update "Build & Development Commands" for workspace
- [ ] Update "Directory Structure" to show packages/
- [ ] Update module import examples to use `battery_tea`
- [ ] Update "Custom Module Development Pattern" examples
- [ ] Add note about battery-tea-demo being an example

#### 2. Update README.md
**File:** `README.md`

- [ ] Update project description
- [ ] Update installation instructions for both packages
- [ ] Update usage examples
- [ ] Link to battery-tea-demo as example implementation

#### 3. Create Battery Demo README
**File:** `packages/battery-tea-demo/README.md` (NEW)

- [ ] Describe purpose (example implementation)
- [ ] Installation instructions
- [ ] Usage examples
- [ ] Link to teax-simkit for framework docs

#### 4. Create Migration Guide
**File:** `docs/migration-guide.md` (NEW) or in README

- [ ] Document import changes
- [ ] Document registry changes
- [ ] Provide find/replace table

```markdown
## Migration Guide

### Import Changes

| Old Import | New Import |
|------------|------------|
| `from simkit.config.schema import BatteryConfig` | `from battery_tea.schemas import BatteryConfig` |
| `from simkit.config.schema import BatteryState` | `from battery_tea.schemas import BatteryState` |
| `from simkit.config.schema import Geography` | `from battery_tea.schemas import Geography` |
| `from simkit.core.battery_config import ConfigureBatteryModule` | `from battery_tea.modules import ConfigureBatteryModule` |
| `from simkit.core import ConfigureBatteryModule` | `from battery_tea.modules import ConfigureBatteryModule` |
| `PipelineModuleRegistry.from_static_modules()` | `from battery_tea import create_battery_registry; create_battery_registry()` |

### Pipeline YAML Changes

Pipeline YAML files that use battery modules need to pass the battery registry:

```python
from battery_tea import create_battery_registry
from simkit.core.pipeline import execute_pipeline

result = execute_pipeline(
    "my_pipeline.yaml",
    output_dir="outputs/",
    registry=create_battery_registry(),
    custom_schema_types=[...battery schemas if using custom entry/exit...],
)
```
```

#### 5. Update AGENTS.md
**File:** `AGENTS.md`

- [ ] Update any references to battery modules
- [ ] Update directory structure references

#### 6. Delete Empty Directories
- [ ] Remove empty `simkit/core/battery_config/` etc. if any remain
- [ ] Remove empty `simkit/tests/pipeline_modules/` if empty
- [ ] Remove `simkit/config/battery_schema.py` (moved to battery_tea)

#### 7. Verify No Stale References
- [ ] `grep -r "from_static_modules" .` returns nothing
- [ ] `grep -r "simkit.core.battery_config" .` returns nothing (except migration guide)
- [ ] `grep -r "simkit.config.battery_schema" .` returns nothing

### Success Criteria

#### Automated Verification:
- [ ] `pytest` passes from root
- [ ] Both packages can be installed: `pip install -e packages/teax-simkit && pip install -e packages/battery-tea-demo`
- [ ] Example from README works

#### Manual Verification:
- [ ] CLAUDE.md accurately describes new structure
- [ ] README provides clear installation/usage
- [ ] Migration guide covers all import changes
- [ ] No stale file references in docs

---

## Testing Strategy

### Unit Tests
- **Framework tests** in `packages/teax-simkit/simkit/tests/` - test ModuleBase, pipeline executor, registry, validators
- **Battery module tests** in `packages/battery-tea-demo/battery_tea/tests/modules/` - test each module's validate_and_fill_default and run methods

### Integration Tests
- **Framework E2E** - `test_toy_pipeline.py` uses ToyModules to test full pipeline without battery
- **Battery E2E** - `test_battery_pipeline.py` uses battery modules with `create_battery_registry()`

### Manual Testing Steps
1. [ ] Fresh clone, install both packages, run pytest
2. [ ] Import framework types: `from simkit.core import ModuleBase`
3. [ ] Import battery types: `from battery_tea import create_battery_registry, BatteryConfig`
4. [ ] Run notebook `manual_mode_demo.ipynb`
5. [ ] Execute battery pipeline YAML with registry parameter

---

## Risk Management

### Identified Risks

1. **Circular imports between packages**
   - *Mitigation*: battery_tea depends on simkit, never reverse. Verify with import tests.
   - *Rollback*: Revert to single package if intractable.

2. **Pytest discovery breaks with workspace**
   - *Mitigation*: Test pytest config after Phase 3 before proceeding.
   - *Rollback*: Use explicit test paths in CI.

3. **Missing imports after move**
   - *Mitigation*: Run full test suite after each phase. Use IDE refactoring tools.
   - *Rollback*: Git revert to previous phase.

4. **Parquet reader functions tied to battery schemas**
   - *Mitigation*: Keep readers generic (they already are). Battery-specific readers can be in battery_tea.
   - *Rollback*: Accept some generic readers know about 8760-length arrays.

### Dependencies
- Each phase depends on previous phase completing successfully
- Phase 1 (generic tests) is critical - blocks all other phases
- Phase 4 (module extraction) is the largest change

---

## Estimated Checklist Summary

| Phase | Checkboxes | Critical Path |
|-------|------------|---------------|
| Phase 1: Generic Test Foundation | 15 | Yes - blocks all |
| Phase 2: Split Schema | 25 | Yes |
| Phase 3: Package Structure | 12 | Yes |
| Phase 4: Extract Modules | 30 | Yes - largest |
| Phase 5: Clean Core | 18 | Yes |
| Phase 6: Migrate Tests | 22 | Yes |
| Phase 7: Documentation | 15 | No - can parallelize |
| **Total** | **~137** | |

---

## References

- Research: `thoughts/research/20260101-163700_simkit-battery-separation.md`
- Existing custom module pattern: `simkit/tests/test_custom_module_pipeline.py`
- Registry builder: `simkit/core/registry_builder.py`
- Schema file: `simkit/config/schema.py`
