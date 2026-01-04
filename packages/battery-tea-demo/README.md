# Battery TEA Demo

**Version:** 0.1.0
**Status:** Example implementation

An example implementation of a battery storage techno-economic analysis (TEA) system built on the [teax-simkit](../teax-simkit/) framework.

## Overview

This package demonstrates how to build domain-specific simulation modules using the teax-simkit framework. It includes:

- **6 Pipeline Modules**: RateData, ConfigureBattery, SimplePerformanceSim, CostCalculator, ProjectAnalyzer, SynchronousSim
- **Domain Schemas**: Battery-specific Pydantic models (BatteryConfig, BatteryTelemetry8760, etc.)
- **I/O Utilities**: Parquet readers/writers for time-series data
- **Example Pipelines**: YAML specifications for battery TEA workflows

## Installation

```bash
# Install with dependencies
pip install -e packages/battery-tea-demo

# For development (includes pytest)
pip install -e packages/battery-tea-demo[dev]
```

## Quick Start

### Using the Battery Registry

```python
from battery_tea import create_battery_registry
from battery_tea.schemas import Geography, RateInfo, LoadProfile8760
from simkit.core.pipeline import execute_pipeline

# Create registry with all battery modules
registry = create_battery_registry()

# Execute a battery TEA pipeline
result = execute_pipeline(
    "battery_tea/tests/fixtures/pipeline_configs/demo_linear_alt.yaml",
    output_dir="outputs/",
    registry=registry,
    custom_schema_types=[Geography, RateInfo, LoadProfile8760],
)

print(result.outputs.keys())
```

### Using Individual Modules

```python
from battery_tea.modules import RateDataModule, ConfigureBatteryModule
from battery_tea.schemas import Geography

# Create and run a module
module = RateDataModule()
result = module.run(
    geography=Geography(
        country="US",
        region="CA",
        utility="PGE",
    )
)
rate_info = result.data
```

## Package Structure

```
battery_tea/
├── __init__.py          # Package exports (create_battery_registry, schemas)
├── schemas.py           # Battery-specific Pydantic models
├── defaults.py          # Battery-specific default values
├── registry.py          # create_battery_registry() function
├── io.py                # Parquet readers/writers for battery data
├── modules/             # Pipeline modules
│   ├── rate_data/       # Geography -> RateInfo
│   ├── battery_config/  # LoadProfile + RateInfo -> BatteryConfig
│   ├── perf_sim_simple/ # BatteryConfig + LoadProfile -> BatteryTelemetry
│   ├── cost_calc/       # BatteryConfig + Geography -> CostBreakdown
│   ├── project_analyzer/# RateInfo + Telemetry -> FinancialResults
│   └── synchronous_sim/ # Time-stepped physics simulation
├── tests/
│   ├── conftest.py      # Pytest fixtures
│   ├── fixtures/        # Test data (JSON, Parquet)
│   └── modules/         # Module unit tests
└── notebooks/           # Jupyter demos
```

## Available Modules

| Module | Inputs | Outputs |
|--------|--------|---------|
| `RateData` | Geography | RateInfo |
| `ConfigureBattery` | LoadProfile8760, RateInfo, DesignPrefs | BatteryConfig |
| `SimplePerformanceSim` | BatteryConfig, LoadProfile8760 | BatteryTelemetry8760 |
| `CostCalculator` | BatteryConfig, Geography | CostBreakdown |
| `ProjectAnalyzer` | RateInfo, BatteryTelemetry8760, FinancialParams | FinancialResults |
| `SynchronousSim` | SyncTimeGrid, BatteryState, etc. | SyncSimOutputs |

## Key Schemas

```python
from battery_tea.schemas import (
    # Input data
    Geography,
    LoadProfile8760,
    PVProfile8760,
    RateInfo,
    DesignPrefs,

    # Battery configuration
    BatteryConfig,
    BatteryState,

    # Simulation outputs
    BatteryTelemetry8760,
    SyncTelemetrySeries,
    SyncSimOutputs,

    # Financial
    CostBreakdown,
    CostLineItem,
)
```

## Running Tests

```bash
# Run all battery-tea-demo tests
pytest packages/battery-tea-demo/

# Run specific module tests
pytest packages/battery-tea-demo/battery_tea/tests/modules/test_rate_data.py

# Run integration tests
pytest packages/battery-tea-demo/battery_tea/tests/test_integration.py
```

## Example Pipelines

See `battery_tea/tests/fixtures/pipeline_configs/` for example YAML specifications:

- `demo_linear_alt.yaml` - Linear pipeline: Geography -> RateInfo -> BatteryConfig -> Telemetry -> FinancialResults

## Creating Your Own Domain Package

This package serves as a template for building your own domain-specific simulation system. Key patterns to follow:

1. **Define schemas** in `schemas.py` using `StrictBaseModel`
2. **Create modules** inheriting from `ModuleBase[InputModel, OutputModel]`
3. **Provide a registry function** via `create_registry([...modules...])`
4. **Add custom I/O** for domain-specific file formats

See the [teax-simkit documentation](../teax-simkit/) for framework details.

## License

MIT License - See LICENSE file for details.
