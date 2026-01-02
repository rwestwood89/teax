# Battery-tea-demo RootModel Wrapping Design

## Overview

Wrap all single-output battery-tea-demo module OutputModels in `RootModel[T]` to align with teax-simkit's module introspector expectations, enabling YAML pipeline execution.

### Ticket and Research References
- Research: `thoughts/research/20260102-202100_battery-tea-demo-pipeline-compatibility.md`

## Current Design

### Problem Statement

The teax-simkit module introspector extracts individual field types from OutputModels. For example, `ConfigureBatteryModule` with `OutputModel = BatteryConfig` produces:

```python
# Introspector extracts:
outputs = {'capacity_kwh': float, 'power_kw': float, 'charge_kw_max': float, ...}
```

But YAML pipelines declare single-output bindings:

```yaml
configure_battery:
  outputs:
    battery_config: BatteryConfig battery_config
```

The pipeline validator (`pipeline_validator.py:330-341`) rejects this mismatch before the executor can run.

### RootModel Special Case

The introspector has special handling for `RootModel` at `module_introspector.py:162-167`:

```python
if is_rootmodel(output_model) and len(outputs_raw) == 1:
    field_name = next(iter(outputs_raw.keys()))  # 'root'
    outputs = {field_name: output_model}  # Preserves wrapper type
```

This preserves the wrapper type, enabling single-output semantics.

## Proposed Design

Wrap each single-output module's OutputModel in `RootModel[T]` with type aliases defined in `schemas.py`.

### Block 1: Type Aliases in schemas.py

Add type aliases at the end of `schemas.py`:

```python
from pydantic import RootModel

# Output wrapper types for pipeline compatibility
# These enable single-output semantics via the introspector's RootModel special case
RateInfoOutput = RootModel[RateInfo]
BatteryConfigOutput = RootModel[BatteryConfig]
BatteryTelemetry8760Output = RootModel[BatteryTelemetry8760]
CostBreakdownOutput = RootModel[CostBreakdown]
```

Note: `FinancialResults` is from `simkit.config.schema`, so `ProjectAnalyzerModule` will use `RootModel[schema.FinancialResults]` directly (inline, not aliased).

### Block 2: Module Changes

Each affected module changes its type signature and wraps return values.

**RateDataModule** (`modules/rate_data/module.py:13,85,89`):
```python
# Before
class RateDataModule(ModuleBase[schemas.Geography, schemas.RateInfo]):
    def run(...) -> ModuleResult[schemas.RateInfo]:
        return ModuleResult(rate_info, notes=...)

# After
class RateDataModule(ModuleBase[schemas.Geography, schemas.RateInfoOutput]):
    def run(...) -> ModuleResult[schemas.RateInfoOutput]:
        return ModuleResult(schemas.RateInfoOutput(rate_info), notes=...)
```

**ConfigureBatteryModule** (`modules/battery_config/module.py:20,93-101`):
```python
# Before
class ConfigureBatteryModule(ModuleBase[BatteryConfigInputs, schemas.BatteryConfig]):
    def run(...) -> ModuleResult[schemas.BatteryConfig]:
        return ModuleResult(config, notes=...)

# After
class ConfigureBatteryModule(ModuleBase[BatteryConfigInputs, schemas.BatteryConfigOutput]):
    def run(...) -> ModuleResult[schemas.BatteryConfigOutput]:
        return ModuleResult(schemas.BatteryConfigOutput(config), notes=...)
```

**SimplePerformanceSimModule** (`modules/perf_sim_simple/module.py:21-23,138-147`):
```python
# Before
class SimplePerformanceSimModule(ModuleBase[PerformanceInputs, schemas.BatteryTelemetry8760]):
    def run(...) -> ModuleResult[schemas.BatteryTelemetry8760]:
        return ModuleResult(telemetry, notes=...)

# After
class SimplePerformanceSimModule(ModuleBase[PerformanceInputs, schemas.BatteryTelemetry8760Output]):
    def run(...) -> ModuleResult[schemas.BatteryTelemetry8760Output]:
        return ModuleResult(schemas.BatteryTelemetry8760Output(telemetry), notes=...)
```

**CostCalculatorModule** (`modules/cost_calc/module.py:25,111-118`):
```python
# Before
class CostCalculatorModule(ModuleBase[CostInputs, schemas.CostBreakdown]):
    def run(...) -> ModuleResult[schemas.CostBreakdown]:
        return ModuleResult(breakdown, notes=...)

# After
class CostCalculatorModule(ModuleBase[CostInputs, schemas.CostBreakdownOutput]):
    def run(...) -> ModuleResult[schemas.CostBreakdownOutput]:
        return ModuleResult(schemas.CostBreakdownOutput(breakdown), notes=...)
```

**ProjectAnalyzerModule** (`modules/project_analyzer/module.py:23,168-204`):
```python
from pydantic import RootModel

# Before
class ProjectAnalyzerModule(ModuleBase[AnalyzerInputs, schema.FinancialResults]):
    def run(...) -> ModuleResult[schema.FinancialResults]:
        return ModuleResult(results, notes=...)

# After
class ProjectAnalyzerModule(ModuleBase[AnalyzerInputs, RootModel[schema.FinancialResults]]):
    def run(...) -> ModuleResult[RootModel[schema.FinancialResults]]:
        return ModuleResult(RootModel[schema.FinancialResults](results), notes=...)
```

### Block 3: YAML Pipeline Changes

Update `demo_linear_alt.yaml` to use `.root` accessor and `RootModel[T]` output declarations:

```yaml
modules:
  rate_data:
    module_type: RateData
    inputs:
      geography: Geography geo
    outputs:
      root: RootModel[RateInfo] rate_info  # Changed

  configure_battery:
    module_type: ConfigureBattery
    inputs:
      load_profile: LoadProfile8760 load_profile
      rate_info: RateInfo rate_info.root  # Changed: .root accessor
      design_prefs: None -> design_pref_default
    outputs:
      root: RootModel[BatteryConfig] battery_config  # Changed

  simple_performance_sim:
    module_type: SimplePerformanceSim
    inputs:
      battery: BatteryConfig battery_config.root  # Changed
      load_profile: LoadProfile8760 load_profile
      pv_profile: None -> pv_profile_default
      rate_info: RateInfo rate_info.root  # Changed
    outputs:
      root: RootModel[BatteryTelemetry8760] telemetry  # Changed

  cost_calculator:
    module_type: CostCalculator
    inputs:
      config: BatteryConfig battery_config.root  # Changed
      geography: Geography geo
    outputs:
      root: RootModel[CostBreakdown] cost_breakdown  # Changed

  project_analyzer:
    module_type: ProjectAnalyzer
    inputs:
      rate_info: RateInfo rate_info.root  # Changed
      telemetry: BatteryTelemetry8760 telemetry.root  # Changed
      financial_params: FinancialParams financial_params
      cost_breakdown: CostBreakdown cost_breakdown.root  # Changed
    outputs:
      root: RootModel[FinancialResults] financial_results  # Changed

  exit_point:
    module_type: ExitPoint
    outputs:
      rate_info: RateInfo rate_info.root.json  # Changed: .root in path
      battery_config: BatteryConfig battery_config.root.json
      cost_breakdown: CostBreakdown cost_breakdown.root.json
      telemetry: BatteryTelemetry8760 telemetry.root.parquet
      financial_results: FinancialResults financial_results.root.json
```

Note: ExitPoint outputs use `.root` in the artifact path to extract the wrapped value before serialization.

### Block 4: Unit Test Changes

Update all module tests to unwrap via `.root`:

**test_rate_data.py** - Example changes at lines 68-69, 78, 90, 98, 106-107:
```python
# Before
rate_info = result.data
assert isinstance(rate_info, schemas.RateInfo)

# After
rate_info = result.data.root
assert isinstance(rate_info, schemas.RateInfo)
```

**test_battery_config.py** - Example changes at lines 104-106, 117, 129, 141, 169:
```python
# Before
config = result.data
assert isinstance(config, schemas.BatteryConfig)

# After
config = result.data.root
assert isinstance(config, schemas.BatteryConfig)
```

**test_perf_sim_simple.py** - Example changes at lines 92-94, 106, 121, 140-141, 154, 174:
```python
# Before
telemetry = result.data
assert isinstance(telemetry, schemas.BatteryTelemetry8760)

# After
telemetry = result.data.root
assert isinstance(telemetry, schemas.BatteryTelemetry8760)
```

**test_cost_calc.py** - Example changes at lines 69-71, 79, 88, 102, 135, 149:
```python
# Before
breakdown = result.data
assert isinstance(breakdown, schemas.CostBreakdown)

# After
breakdown = result.data.root
assert isinstance(breakdown, schemas.CostBreakdown)
```

**test_project_analyzer.py** - Example changes at lines 85-86, 101, 115, 133, 147, 175:
```python
# Before
assert isinstance(result.data, schema.FinancialResults)

# After
assert isinstance(result.data.root, schema.FinancialResults)
```

### Block 5: Integration Test for Pipeline Execution

Add a new integration test to verify end-to-end pipeline execution:

**test_integration.py** - Add new test class:
```python
class TestPipelineExecution:
    """Tests for YAML pipeline execution."""

    def test_demo_linear_pipeline_executes(self, tmp_path):
        """demo_linear_alt.yaml executes successfully."""
        from simkit.core.pipeline import execute_pipeline
        from battery_tea import create_battery_registry
        from battery_tea.schemas import (
            Geography, LoadProfile8760, RateInfo, BatteryConfig,
            BatteryTelemetry8760, CostBreakdown,
        )

        registry = create_battery_registry()
        config_path = Path(__file__).parent / "fixtures" / "pipeline_configs" / "demo_linear_alt.yaml"

        result = execute_pipeline(
            str(config_path),
            output_dir=str(tmp_path),
            registry=registry,
            custom_schema_types=[
                Geography, LoadProfile8760, RateInfo, BatteryConfig,
                BatteryTelemetry8760, CostBreakdown,
            ],
        )

        # Verify outputs exist
        assert result.outputs is not None
        assert "rate_info" in result.outputs
        assert "battery_config" in result.outputs
        assert "telemetry" in result.outputs
        assert "cost_breakdown" in result.outputs
        assert "financial_results" in result.outputs
```

## Files to Modify

| File | Changes |
|------|---------|
| `battery_tea/schemas.py` | Add 4 type aliases (RateInfoOutput, BatteryConfigOutput, etc.) |
| `battery_tea/modules/rate_data/module.py` | Change class signature and return type |
| `battery_tea/modules/battery_config/module.py` | Change class signature and return type |
| `battery_tea/modules/perf_sim_simple/module.py` | Change class signature and return type |
| `battery_tea/modules/cost_calc/module.py` | Change class signature and return type |
| `battery_tea/modules/project_analyzer/module.py` | Change class signature, import RootModel, return type |
| `battery_tea/tests/fixtures/pipeline_configs/demo_linear_alt.yaml` | Update all output bindings and input references |
| `battery_tea/tests/modules/test_rate_data.py` | Add `.root` to all `result.data` accesses |
| `battery_tea/tests/modules/test_battery_config.py` | Add `.root` to all `result.data` accesses |
| `battery_tea/tests/modules/test_perf_sim_simple.py` | Add `.root` to all `result.data` accesses |
| `battery_tea/tests/modules/test_cost_calc.py` | Add `.root` to all `result.data` accesses |
| `battery_tea/tests/modules/test_project_analyzer.py` | Add `.root` to all `result.data` accesses |
| `battery_tea/tests/test_integration.py` | Add TestPipelineExecution class |

## Implementation Benefits

- Aligns battery-tea-demo with teax-simkit's module introspection design
- Enables YAML pipeline execution with single-output modules
- Uses framework's existing RootModel special case (no teax-simkit changes)
- Type aliases keep module code readable
- Explicit `.root` accessor makes unwrapping visible in YAML

## Potential Risks

- **ExitPoint field extraction**: The ExitPoint may need special handling to extract `.root` before serialization. The YAML pattern `rate_info.root.json` should work, but verify during implementation.
- **Downstream consumers**: Any code calling `module.run()` directly will now receive `RootModel[T]` instead of `T`. All such call sites must add `.root` unwrapping.
- **test_integration.py registry tests**: The `TestRegistryIntegration` tests check descriptor outputs - verify they still pass with RootModel output types.
