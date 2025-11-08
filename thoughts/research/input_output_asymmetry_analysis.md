# Input/Output Asymmetry Analysis

## Executive Summary

**You are absolutely correct.** There IS a fundamental asymmetry between how inputs and outputs are handled in the pipeline system. This is not a bug—it's an intentional design pattern that enables two distinct output modes:

1. **Single-output modules**: The entire `OutputModel` object becomes the channel value
2. **Multi-output modules**: The `OutputModel` must be a `Dict[str, StrictBaseModel]`, and each key becomes a separate channel

## The Asymmetry Explained

### Input Pattern (Field-Based)

For inputs, the YAML fields **always** map to fields in the InputModel dataclass:

```yaml
simple_performance_sim:
  inputs:
    battery: BatteryConfig battery_config
    load_profile: LoadProfile8760 load_profile
    pv_profile: None -> pv_profile_default
    rate_info: RateInfo rate_info
```

Maps to:

```python
@dataclass(frozen=True)
class PerformanceInputs:
    battery: schema.BatteryConfig
    load_profile: schema.LoadProfile8760
    pv_profile: schema.PVProfile8760 | None
    rate_info: schema.RateInfo
```

The module receives these as individual kwargs in `validate_and_fill_default()` and `run()`.

**Reference**: `/home/reid/teax/simkit/core/perf_sim_simple/module.py:13-18`, `49-54`

### Output Pattern (Mode-Dependent)

For outputs, the behavior depends on **how many outputs** are declared in the YAML:

#### Single Output Mode

```yaml
simple_performance_sim:
  outputs:
    telemetry: BatteryTelemetry8760 telemetry
```

Here, `telemetry` is just a **label**. The entire `BatteryTelemetry8760` object returned by the module becomes the channel value. The YAML field name (`telemetry`) doesn't need to match any field in `BatteryTelemetry8760`—it's purely the channel name.

```python
class SimplePerformanceSimModule(
    ModuleBase[PerformanceInputs, schema.BatteryTelemetry8760]
):
    def run(...) -> ModuleResult[schema.BatteryTelemetry8760]:
        # ... simulation logic ...
        return ModuleResult(telemetry, notes="...")
```

**Reference**: `/home/reid/teax/simkit/core/perf_sim_simple/module.py:21-23`, `138-147`

#### Multiple Output Mode

```yaml
synchronous_sim:
  outputs:
    synchronous_sim: SyncSimOutputs synchronous_sim
    forecasts: MockForecastSeries forecasts
    guidances: SyncGuidanceSeries guidances
    telemetry: SyncTelemetrySeries telemetry
```

Here, the YAML field names (`synchronous_sim`, `forecasts`, `guidances`, `telemetry`) **DO** map to keys in the dictionary returned by the module. Each becomes a separate channel.

```python
class SynchronousSimModule(
    ModuleBase[SynchronousSimInputs, Dict[str, schema.StrictBaseModel]]
):
    def run(...) -> ModuleResult[Dict[str, schema.StrictBaseModel]]:
        # ... simulation logic ...
        bundle = schema.SyncSimOutputs(
            forecasts=schema.MockForecastSeries(series=tuple(forecasts)),
            guidances=schema.SyncGuidanceSeries(series=tuple(guidances)),
            telemetry=schema.SyncTelemetrySeries(frames=tuple(telemetry_frames)),
        )
        result_payload: Dict[str, schema.StrictBaseModel] = {
            "synchronous_sim": bundle,
            "forecasts": bundle.forecasts,
            "guidances": bundle.guidances,
            "telemetry": bundle.telemetry,
        }
        return ModuleResult(result_payload, notes="...")
```

**Reference**: `/home/reid/teax/simkit/core/synchronous_sim/module.py:26-28`, `154-165`

## The Critical Code Path

The executor determines which mode to use based on `len(outputs)`:

**File**: `/home/reid/teax/simkit/core/pipeline_executor.py:164-176`

```python
outputs = module_spec.outputs
result = module.run(**kwargs)
data = result.data

if len(outputs) == 1:
    # Single-output mode: entire data object → channel
    binding = next(iter(outputs.values()))
    context.set_channel(binding.channel_name, data)
else:
    # Multi-output mode: data must be dict, keys → channels
    if not isinstance(data, Mapping):
        raise RuntimeError(
            f"Module '{module_key}' produced multiple outputs but returned non-mapping data"
        )
    for field, binding in outputs.items():
        context.set_channel(binding.channel_name, data[field])
```

## Why This Asymmetry Exists

### Input Side: Always Field-Based

Inputs need field-based mapping because:
1. Modules receive inputs as `**kwargs` in Python
2. Type validation requires named parameters
3. The InputModel dataclass provides clear documentation of what the module needs

### Output Side: Mode-Dependent

Outputs use conditional logic because:
1. **Common case** (single output): No need to force modules to return a dict wrapper
2. **Advanced case** (multiple outputs): Dict keys provide natural routing to multiple channels
3. This avoids boilerplate for simple modules while enabling complex ones

## Comparison Table

| Aspect | Input Behavior | Single Output | Multiple Outputs |
|--------|---------------|---------------|------------------|
| YAML field names | Map to InputModel fields | Label only (channel name) | Map to dict keys |
| Type generic | `InputModel` (dataclass) | `OutputModel` (any Pydantic model) | `Dict[str, StrictBaseModel]` |
| Module signature | `run(**kwargs)` | `ModuleResult[OutputModel]` | `ModuleResult[Dict[str, ...]]` |
| Executor behavior | Unpacks to kwargs | Assigns entire object to channel | Indexes dict by field name |

## Current Module Patterns in Codebase

### Single-Output Modules (Most Common)

1. **RateDataModule**: `Geography → RateInfo`
   - File: `/home/reid/teax/simkit/core/rate_data/module.py:12`

2. **ConfigureBatteryModule**: `BatteryConfigInputs → BatteryConfig`
   - File: `/home/reid/teax/simkit/core/battery_config/module.py:20`

3. **SimplePerformanceSimModule**: `PerformanceInputs → BatteryTelemetry8760`
   - File: `/home/reid/teax/simkit/core/perf_sim_simple/module.py:21-23`

4. **CostCalculatorModule**: `CostInputs → CostBreakdown`
   - File: `/home/reid/teax/simkit/core/cost_calc/module.py:25`

5. **ProjectAnalyzerModule**: `AnalyzerInputs → FinancialResults`
   - File: `/home/reid/teax/simkit/core/project_analyzer/module.py:21`

### Multi-Output Module (Rare)

1. **SynchronousSimModule**: `SynchronousSimInputs → Dict[str, StrictBaseModel]`
   - File: `/home/reid/teax/simkit/core/synchronous_sim/module.py:26-28`
   - Returns 4 separate channels: `synchronous_sim`, `forecasts`, `guidances`, `telemetry`
   - YAML spec: `/home/reid/teax/simkit/tests/fixtures/pipeline_configs/synchronous_sim_stubbed.yaml:23-27`

## How to Handle Multiple Outputs

If you need a module to output two different data types to different downstream modules, follow the `SynchronousSimModule` pattern:

### Step 1: Declare Output Type as Dict

```python
class MyMultiOutputModule(
    ModuleBase[MyInputs, Dict[str, schema.StrictBaseModel]]
):
```

### Step 2: Return Dict from run()

```python
def run(...) -> ModuleResult[Dict[str, schema.StrictBaseModel]]:
    # ... processing ...

    result_payload = {
        "output_a": schema.TypeA(...),
        "output_b": schema.TypeB(...),
    }
    return ModuleResult(result_payload, notes="...")
```

### Step 3: Declare Multiple Outputs in YAML

```yaml
my_module:
  module_type: MyMultiOutput
  inputs:
    # ... inputs ...
  outputs:
    output_a: TypeA channel_a
    output_b: TypeB channel_b
```

### Step 4: Route to Different Modules

```yaml
downstream_module_1:
  module_type: ProcessorA
  inputs:
    data: TypeA channel_a

downstream_module_2:
  module_type: ProcessorB
  inputs:
    data: TypeB channel_b
```

## Optional: Bundle Pattern

Notice that `SynchronousSimModule` uses both patterns:
- Returns a **bundle** (`SyncSimOutputs`) as one channel
- Also returns the **individual components** as separate channels

```python
bundle = schema.SyncSimOutputs(
    forecasts=schema.MockForecastSeries(series=tuple(forecasts)),
    guidances=schema.SyncGuidanceSeries(series=tuple(guidances)),
    telemetry=schema.SyncTelemetrySeries(frames=tuple(telemetry_frames)),
)

result_payload = {
    "synchronous_sim": bundle,      # Complete bundle
    "forecasts": bundle.forecasts,  # Individual component
    "guidances": bundle.guidances,  # Individual component
    "telemetry": bundle.telemetry,  # Individual component
}
```

This gives downstream modules flexibility:
- Want everything? Use the `synchronous_sim` channel
- Want just forecasts? Use the `forecasts` channel

**Reference**: `/home/reid/teax/simkit/core/synchronous_sim/module.py:154-164`

## Schema Definition for Bundles

When using the bundle pattern, define the bundle as a Pydantic model:

**File**: `/home/reid/teax/simkit/config/schema.py:660-668`

```python
class SyncSimOutputs(StrictBaseModel):
    forecasts: MockForecastSeries
    guidances: SyncGuidanceSeries
    telemetry: SyncTelemetrySeries

    @model_validator(mode="after")
    def validate_alignment(self) -> "SyncSimOutputs":
        ensure_outer_indices_match(self.forecasts, self.guidances, self.telemetry)
        return self
```

## Validation: YAML Output Fields Must Match Dict Keys

The executor will raise a `KeyError` if YAML declares an output field that doesn't exist in the returned dict:

```python
for field, binding in outputs.items():
    context.set_channel(binding.channel_name, data[field])  # KeyError if missing!
```

**Reference**: `/home/reid/teax/simkit/core/pipeline_executor.py:175-176`

## Conclusion

The asymmetry you identified is **real and intentional**:

- **Inputs**: Always field-based mapping (YAML fields → InputModel fields)
- **Single outputs**: Whole-object mapping (entire OutputModel → channel)
- **Multiple outputs**: Dict-key mapping (YAML fields → Dict keys → channels)

This design provides:
✅ Simplicity for common single-output modules (no dict wrapper required)
✅ Power for complex multi-output modules (dict routing)
✅ Type safety through Pydantic models
✅ Clear data flow in pipeline DAGs

The `SynchronousSimModule` serves as the canonical reference implementation for multi-output modules in the codebase.
