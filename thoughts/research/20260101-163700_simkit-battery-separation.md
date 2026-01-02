---
date: 2026-01-01T16:37:00+00:00
researcher: Reid Westwood
git_commit: 35f9cf2
branch: main
repository: teax
topic: "Separating Battery Demo from Core Simkit Framework"
tags: [research, codebase, refactoring, package-separation]
status: complete
last_updated: 2026-01-01
last_updated_by: Reid Westwood
---

# Research: Separating Battery Demo from Core Simkit Framework

**Date**: 2026-01-01T16:37:00+00:00
**Researcher**: Reid Westwood
**Git Commit**: 35f9cf2
**Branch**: main
**Repository**: teax

## Research Question

Identify all battery/TEA-specific code in the simkit codebase versus the generic simulation framework, then propose a strategy for:
1. Cleaning up the actual simkit (to be built as `teax-simkit` package)
2. Moving the specific battery demo to a separate folder that should NOT get built by default

## Summary

The codebase has **clear but entangled** separation between generic framework code and battery-specific simulation code. Analysis reveals:

- **~61% of schema types are battery-specific** (28 of 46 Pydantic models)
- **All 6 domain modules are battery-specific** (RateData, ConfigureBattery, SimplePerformanceSim, CostCalculator, ProjectAnalyzer, SynchronousSim)
- **Generic framework infrastructure is well-isolated** in `core/` (base.py, pipeline_*.py, registry_builder.py, module_introspector.py) and `io/` (readers.py, writers.py, output_router.py)
- **Static module registration (`from_static_modules()`) couples battery modules to framework**

Recommended approach: Create a **monorepo with two packages** structure.

---

## Detailed Findings

### 1. Generic Framework Components (Should Remain in teax-simkit)

#### Core Module Infrastructure
| File | Description |
|------|-------------|
| `simkit/core/base.py:1-31` | `ModuleBase[InputModel, OutputModel]` interface, `ModuleResult` wrapper |
| `simkit/core/pipeline.py:1-206` | `execute_pipeline()` entrypoint |
| `simkit/core/pipeline_executor.py:1-688` | `SerialPipelineExecutor`, `RunResult`, `PipelineExecutionContext` |
| `simkit/core/pipeline_registry.py:17-67` | `PipelineModuleRegistry`, `ModuleDescriptor` (generic parts) |
| `simkit/core/pipeline_validator.py:1-500` | `PipelineValidator`, `PipelineValidationError` |
| `simkit/core/pipeline_graph.py:1-85` | `PipelineGraph`, `PipelineDagBuilder` |
| `simkit/core/registry_builder.py:1-184` | `create_registry()` for custom module registration |
| `simkit/core/module_introspector.py:1-205` | Auto-extract input/output schemas from type hints |

#### I/O Infrastructure
| File | Description |
|------|-------------|
| `simkit/io/readers.py` | Generic loaders (`read_json_model`, `read_yaml_config`, `read_parquet_*`) |
| `simkit/io/writers.py` | Generic writers (`write_json_model`, `write_provenance`) |
| `simkit/io/output_router.py` | `OutputRouter`, `WriteHandler`, `create_default_router`, `create_output_router_with_json_schemas` |

#### Generic Schema Types (simkit/config/schema.py)
| Type | Lines | Purpose |
|------|-------|---------|
| `StrictBaseModel` | 50-54 | Immutable, strict validation base class |
| `MultiOutput` | 56-103 | Base for multi-output modules |
| `Provenance` | 285-290 | Config hash, module versions |
| `PipelineRunMetadata` | 292-296 | Pipeline execution metadata |
| `RunArtifactRecord` | 298-303 | Artifact tracking |
| `RunManifest` | 305-312 | Output bundle structure |
| `TimeSpan` | 318-339 | Duration representation |
| `SyncOuterStep` | 341-362 | Single outer loop step |
| `InnerLoopConfig` | 364-378 | Inner loop configuration |
| `SyncTimeGrid` | 380-425 | Hierarchical time-stepping |
| `PriceTrajectory` | 427-501 | Time-indexed price series (domain-agnostic) |
| `PriceTrajectoryWindow` | 503-540 | Sliced price view |
| `FinancialParams` | 247-256 | Generic financial parameters |
| `CashflowEntry` | 258-262 | Single year cashflow |
| `LedgerEntry` | 264-269 | Financial ledger item |
| `FinancialResults` | 271-283 | Financial metrics (partially generic) |

#### Configuration & Environment
| File | Description |
|------|-------------|
| `simkit/config/environment.py` | `resolve_input_dir`, `resolve_output_dir`, `loadenv` |
| `simkit/config/flags.py` | Feature flags (minimal) |
| `simkit/config/time_utils.py` | Time/timezone utilities |
| `simkit/config/pipeline_schema.py` | YAML pipeline spec structure |

---

### 2. Battery-Specific Components (Should Move to Demo Package)

#### Domain Modules (simkit/core/*)
| Directory | Module Class | Purpose |
|-----------|--------------|---------|
| `rate_data/` | `RateDataModule` | Geography → RateInfo (utility tariff lookup) |
| `battery_config/` | `ConfigureBatteryModule` | LoadProfile + RateInfo → BatteryConfig (battery sizing) |
| `perf_sim_simple/` | `SimplePerformanceSimModule` | BatteryConfig + LoadProfile → BatteryTelemetry8760 (rule-based) |
| `cost_calc/` | `CostCalculatorModule` | BatteryConfig + Geography → CostBreakdown (CapEx/OpEx) |
| `project_analyzer/` | `ProjectAnalyzerModule` | RateInfo + Telemetry → FinancialResults (NPV/IRR) |
| `synchronous_sim/` | `SynchronousSimModule` | Time-stepped physics simulation with forecasting/guidance/dynamics |

#### Battery-Specific Schema Types (simkit/config/schema.py)
| Type | Lines | Purpose |
|------|-------|---------|
| `Geography` | 105-111 | Location for tariff lookup |
| `LoadProfile8760` | 113-132 | 8760 hourly load in kWh |
| `PVProfile8760` | 134-153 | 8760 hourly solar production |
| `RateInfo` | 155-180 | Electricity tariff structure |
| `DesignPrefs` | 182-195 | Battery design preferences |
| `BatteryConfig` | 197-210 | Battery system parameters |
| `CostLineItem` | 212-219 | Cost breakdown line item |
| `CostBreakdown` | 221-229 | Battery system costs |
| `BatteryTelemetry8760` | 231-245 | Hourly charge/discharge telemetry |
| `BatteryState` | 542-565 | Instantaneous battery state |
| `MockForecastMetadata` | 567-571 | Forecast metadata |
| `MockForecastConfig` | 573-589 | Forecast configuration |
| `MockForecastPoint` | 591-608 | Single forecast |
| `MockForecastSeries` | 610-616 | Forecast history |
| `GuidanceMetadata` | 618-620 | Guidance metadata |
| `GuidanceConfig` | 622-642 | Battery dispatch config |
| `SyncGuidance` | 644-655 | Power setpoint command |
| `SyncGuidanceSeries` | 657-663 | Guidance history |
| `DynamicSimConfig` | 665-678 | Dynamics configuration |
| `DynamicsInitInput` | 680-684 | Dynamics init input |
| `DynamicsStepInput` | 686-690 | Dynamics step input |
| `SyncTelemetryFrame` | 692-715 | Per-timestep telemetry |
| `SyncTelemetrySeries` | 717-723 | Telemetry history |
| `SyncSimOutputs` | 737-746 | Synchronous sim outputs |

#### Battery-Specific Defaults (simkit/config/defaults.py)
```python
DEFAULT_ROUNDTRIP_EFFICIENCY = 0.92
DEFAULT_SOC_MIN = 0.1
DEFAULT_SOC_MAX = 0.9
DEFAULT_BATTERY_NOTES = "Heuristic sizing for demo"
default_design_prefs()  # Battery design defaults
```

#### Test Fixtures (simkit/tests/fixtures/)
- `geography_us_ca_pge.json` - Geography data
- `load_profile_toy_8760.parquet` - 8760 hourly load
- `load_profile_flat_8760.parquet` - Alternative load
- `rateinfo_tou_synthetic.json` - Time-of-use rates
- `financial_params_demo.json` - Financial parameters
- `synchronous_sim/` - All synchronous sim fixtures
- `pipeline_configs/demo_linear_alt.yaml` - Battery pipeline
- `pipeline_configs/synchronous_sim_stubbed.yaml` - Sync sim pipeline

---

### 3. Coupling Points (Require Refactoring)

#### A. Static Module Registration
**File**: `simkit/core/pipeline_registry.py:46-148`

`PipelineModuleRegistry.from_static_modules()` hardcodes all 6 battery modules:
```python
registry.register("RateData", ModuleDescriptor(...))
registry.register("ConfigureBattery", ModuleDescriptor(...))
registry.register("SimplePerformanceSim", ModuleDescriptor(...))
registry.register("CostCalculator", ModuleDescriptor(...))
registry.register("ProjectAnalyzer", ModuleDescriptor(...))
registry.register("SynchronousSim", ModuleDescriptor(...))
```

**Solution**: Remove `from_static_modules()` from core package. Battery demo should call `create_registry([...battery_modules...])`.

#### B. Core Package Exports
**File**: `simkit/core/__init__.py:1-31`

Exports all battery module classes directly:
```python
from .battery_config import ConfigureBatteryModule
from .cost_calc import CostCalculatorModule
# ... etc
```

**Solution**: Core `__init__.py` should only export framework classes (`ModuleBase`, `ModuleResult`, `PipelineModuleRegistry`, etc.).

#### C. Schema File Mixing
**File**: `simkit/config/schema.py`

Single file contains both generic framework types and 28 battery-specific types.

**Solution**: Split into `schema_base.py` (generic) and move battery types to demo package.

#### D. Defaults File
**File**: `simkit/config/defaults.py`

Contains battery-specific defaults mixed with generic financial defaults.

**Solution**: Keep generic defaults in core, move battery defaults to demo package.

---

## Proposed Strategy

### Package Structure

```
teax/
├── packages/
│   ├── teax-simkit/           # Core framework package (pip install teax-simkit)
│   │   ├── simkit/
│   │   │   ├── core/
│   │   │   │   ├── __init__.py          # Only framework exports
│   │   │   │   ├── base.py
│   │   │   │   ├── pipeline.py
│   │   │   │   ├── pipeline_executor.py
│   │   │   │   ├── pipeline_graph.py
│   │   │   │   ├── pipeline_registry.py  # No from_static_modules()
│   │   │   │   ├── pipeline_validator.py
│   │   │   │   ├── registry_builder.py
│   │   │   │   └── module_introspector.py
│   │   │   ├── config/
│   │   │   │   ├── schema.py             # Only generic types
│   │   │   │   ├── pipeline_schema.py
│   │   │   │   ├── environment.py
│   │   │   │   ├── flags.py
│   │   │   │   └── time_utils.py
│   │   │   ├── io/
│   │   │   │   ├── readers.py
│   │   │   │   ├── writers.py
│   │   │   │   └── output_router.py
│   │   │   └── tests/                    # Generic framework tests only
│   │   │       ├── core/
│   │   │       │   ├── test_registry_builder.py
│   │   │       │   ├── test_module_introspector.py
│   │   │       │   └── test_custom_schema_registration.py
│   │   │       └── fixtures/
│   │   │           └── pipeline_configs/  # Generic test pipelines
│   │   └── pyproject.toml
│   │
│   └── battery-tea-demo/      # Example implementation (not installed by default)
│       ├── battery_tea/
│       │   ├── __init__.py
│       │   ├── schemas.py                # All battery-specific types
│       │   ├── defaults.py               # Battery-specific defaults
│       │   ├── registry.py               # create_battery_registry()
│       │   ├── modules/
│       │   │   ├── rate_data/
│       │   │   ├── battery_config/
│       │   │   ├── perf_sim_simple/
│       │   │   ├── cost_calc/
│       │   │   ├── project_analyzer/
│       │   │   └── synchronous_sim/
│       │   └── tests/
│       │       ├── fixtures/             # All battery fixtures
│       │       └── test_*.py
│       ├── notebooks/
│       └── pyproject.toml                # depends on teax-simkit
│
├── README.md                             # Points to examples in battery-tea-demo
└── pyproject.toml                        # Workspace config (if using workspace)
```

### Migration Steps

#### Phase 1: Create Minimal Generic Tests
1. Create `ToyModule` that doesn't use battery concepts
2. Add generic pipeline tests using `ToyModule`
3. Ensure framework can be tested without battery schemas

#### Phase 2: Split Schema File
1. Move 18 generic types to `simkit/config/schema.py`
2. Create `battery_tea/schemas.py` with 28 battery types
3. Update imports in all battery modules

#### Phase 3: Extract Battery Modules
1. Move 6 module directories to `battery_tea/modules/`
2. Update imports to use `battery_tea.schemas`
3. Create `battery_tea.registry.create_battery_registry()`

#### Phase 4: Clean Core Package
1. Remove `from_static_modules()` from `PipelineModuleRegistry`
2. Update `simkit/core/__init__.py` to only export framework
3. Move battery defaults to `battery_tea/defaults.py`

#### Phase 5: Test Fixtures Migration
1. Move battery fixtures to `battery-tea-demo/`
2. Create generic `ToyModule` fixtures for core tests
3. Update pytest configuration

#### Phase 6: Documentation
1. Update CLAUDE.md to reflect new structure
2. Create battery-tea-demo README with setup instructions
3. Add "Custom Module Development" guide to core package

### Breaking Changes

1. **Users importing battery modules from `simkit.core`** will need to change to `battery_tea.modules`
2. **Users calling `PipelineModuleRegistry.from_static_modules()`** will need to use `create_battery_registry()`
3. **Pipeline YAML files** may need registry parameter if not using battery-tea-demo

### Alternative: Single Package with Optional Install

Instead of separate packages, keep everything in one package but use optional dependencies:

```toml
[project.optional-dependencies]
battery = [
  # any battery-specific deps if needed
]
```

And use lazy imports in `simkit/core/__init__.py` that only expose battery modules if `battery_tea/` subpackage exists. This is simpler but less clean separation.

---

## Code References

- `simkit/core/pipeline_registry.py:46-148` - Static module registration (coupling point)
- `simkit/core/__init__.py:1-31` - Battery module exports (coupling point)
- `simkit/config/schema.py:105-746` - Battery-specific schemas
- `simkit/config/defaults.py:26-74` - Battery-specific defaults
- `simkit/core/battery_config/module.py` - Example battery module
- `simkit/core/registry_builder.py` - `create_registry()` for custom modules

## Architecture Insights

1. **Framework is well-designed for extension**: `create_registry()` and `custom_schema_types` parameter already support external modules
2. **CLAUDE.md documents the extension pattern**: Custom Module Development and Custom Schema Development patterns are documented
3. **Test infrastructure supports separation**: pytest fixtures pattern allows battery fixtures to move cleanly
4. **MultiOutput pattern is generic**: Can be used by any domain, not just battery

## Open Questions

1. **Package naming**: `teax-simkit` vs `simkit` vs something else?
2. **Versioning strategy**: Should battery-tea-demo version track core, or be independent?
3. **GitHub organization**: Monorepo with workspaces vs separate repos?
4. **PyPI publishing**: Publish core to PyPI? Battery demo is example-only?
5. **FinancialResults schema**: Keep `lcob` field (battery-specific) or make metric names configurable?
