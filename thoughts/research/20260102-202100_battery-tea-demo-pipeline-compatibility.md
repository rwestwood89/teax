---
date: 2026-01-02T20:21:00+00:00
researcher: Reid Westwood
git_commit: e0e90c9c
branch: refactor
repository: teax
topic: "Battery-tea-demo pipeline compatibility with teax-simkit"
tags: [research, codebase, module-introspection, pipeline-validation, battery-tea]
status: complete
last_updated: 2026-01-02
last_updated_by: Reid Westwood
---

# Research: Battery-tea-demo Pipeline Compatibility with teax-simkit

**Date**: 2026-01-02T20:21:00+00:00
**Researcher**: Reid Westwood
**Git Commit**: e0e90c9c
**Branch**: refactor
**Repository**: teax

## Research Question

During Phase 6 of the simkit-battery separation refactor, why are battery-tea-demo pipeline tests not working? The commit message notes "battery demo tests not fully passing yet" even though unit tests pass. What is the root cause and how should it be fixed?

## Summary

**All 171 unit tests pass**, but **YAML-based pipeline execution fails** for battery-tea-demo modules due to a **fundamental architectural mismatch** between:

1. **How the module introspector extracts output types**: It extracts individual field types from the OutputModel (e.g., `BatteryConfig.capacity_kwh`, `BatteryConfig.power_kw`, etc.)

2. **How the YAML declares outputs**: A single output with the model type (e.g., `battery_config: BatteryConfig battery_config`)

3. **How the executor stores outputs**: For single-output modules, it stores the entire OutputModel object in one channel (correct behavior), but the validator rejects this because the YAML bindings don't match the introspected field-level outputs.

The fix requires either:
- **Option A**: Change battery module output types to use wrapper patterns (RootModel or custom single-field wrapper)
- **Option B**: Update the introspector to detect single-output modules and preserve the OutputModel type instead of extracting fields
- **Option C**: Update YAML files to declare individual field outputs (breaking change, verbose)

## Detailed Findings

### 1. Module Introspection Extracts Fields

The `introspect_module()` function at `packages/teax-simkit/simkit/core/module_introspector.py:124-185` extracts OutputModel fields:

```python
# Line 155: Extract field types from output model
outputs_raw, _ = extract_field_types(output_model)
```

For `ConfigureBatteryModule(ModuleBase[BatteryConfigInputs, BatteryConfig])`:
- OutputModel = `BatteryConfig`
- Extracted outputs: `{'capacity_kwh': float, 'power_kw': float, 'charge_kw_max': float, ...}`

### 2. RootModel Special Case Exists But Doesn't Help

The introspector has a special case for `RootModel` (lines 162-167):

```python
if is_rootmodel(output_model) and len(outputs_raw) == 1:
    field_name = next(iter(outputs_raw.keys()))  # 'root'
    outputs = {field_name: output_model}  # Use RootModel[T], not T
```

This preserves the wrapper type for `RootModel[float]` → `{'root': RootModel[float]}`.

But `BatteryConfig` is not a `RootModel`, so this doesn't apply.

### 3. Validator Rejects Mismatched Outputs

The `_validate_outputs()` method at `packages/teax-simkit/simkit/core/pipeline_validator.py:330-341`:

```python
def _validate_outputs(self, module: PipelineModuleSpec, descriptor: ModuleDescriptor) -> None:
    expected = set(descriptor.outputs.keys())  # {'capacity_kwh', 'power_kw', ...}
    actual = set(module.outputs.keys())        # {'battery_config'}
    if expected != actual:
        raise PipelineValidationError("Output bindings do not match registry metadata")
```

### 4. Executor Would Handle It Correctly

Ironically, the executor at `packages/teax-simkit/simkit/core/pipeline_executor.py:220-223` handles single outputs correctly:

```python
# Single-output mode - assign entire data to one channel
if len(outputs) == 1:
    binding = next(iter(outputs.values()))
    context.set_channel(binding.channel_name, data)  # Stores whole object
```

But the validator blocks execution before this code runs.

### 5. Example Error

```python
from battery_tea import create_battery_registry
from simkit.core.pipeline import execute_pipeline

registry = create_battery_registry()
result = execute_pipeline('demo_linear_alt.yaml', output_dir='tmp/', registry=registry, ...)
# Error: PipelineValidationError: Output bindings do not match registry metadata
```

### 6. Registry vs YAML Mismatch Evidence

**Registry expects (from introspector)**:
```
ConfigureBattery:
  Outputs: {'capacity_kwh': float, 'power_kw': float, 'charge_kw_max': float, ...}
```

**YAML declares**:
```yaml
configure_battery:
  outputs:
    battery_config: BatteryConfig battery_config
```

## Code References

- `packages/teax-simkit/simkit/core/module_introspector.py:155` - Field extraction from OutputModel
- `packages/teax-simkit/simkit/core/module_introspector.py:162-167` - RootModel special case
- `packages/teax-simkit/simkit/core/pipeline_validator.py:330-338` - Output validation that fails
- `packages/teax-simkit/simkit/core/pipeline_executor.py:220-223` - Correct single-output handling
- `packages/battery-tea-demo/battery_tea/modules/battery_config/module.py:20` - Module definition
- `packages/battery-tea-demo/battery_tea/tests/fixtures/pipeline_configs/demo_linear_alt.yaml:18-25` - YAML output binding

## Architecture Insights

### Current teax-simkit Design Philosophy

The framework was designed with these patterns in mind:

1. **Toy modules use `RootModel[float]`**: Simple single-value outputs wrap the value, enabling field extraction (`.root`).

2. **Multi-output modules use `MultiOutput`**: Container class with named fields, each routed to a separate channel.

3. **The introspector extracts fields**: For complex OutputModels, each field becomes a separate output channel. This enables downstream modules to consume individual fields via field references.

### Battery Module Pattern Conflict

Battery modules were written with a different pattern:
- Return a single complex Pydantic model (`BatteryConfig`, `RateInfo`, etc.)
- Expect YAML to declare a single output channel for the whole model
- Downstream modules consume the whole model, not individual fields

### Resolution Options

**Option A: Wrap Battery Outputs (Recommended)**

Change battery modules to use `RootModel` wrapper:

```python
# Before
class ConfigureBatteryModule(ModuleBase[BatteryConfigInputs, BatteryConfig]):
    ...

# After
class ConfigureBatteryModule(ModuleBase[BatteryConfigInputs, RootModel[BatteryConfig]]):
    def run(self, ...) -> ModuleResult[RootModel[BatteryConfig]]:
        config = BatteryConfig(...)
        return ModuleResult(data=RootModel[BatteryConfig](config))
```

YAML would use `.root` for downstream:
```yaml
outputs:
  battery_config: RootModel[BatteryConfig] battery_config

downstream_module:
  inputs:
    config: BatteryConfig battery_config.root
```

**Option B: Update Introspector**

Add logic to detect when a module has a single-output pattern (OutputModel with multiple fields but only one "logical" output):

```python
# In introspect_module(), after line 171:
# If YAML typically declares 1 output and module returns BaseModel (not MultiOutput),
# treat the whole OutputModel as a single output named after the model class
if not is_rootmodel(output_model) and not issubclass(output_model, MultiOutput):
    # Single complex output mode - use class name as output key
    outputs = {output_model.__name__.lower(): output_model}
```

This is more invasive and changes framework semantics.

**Option C: Update YAML Files (Not Recommended)**

Declare all field outputs in YAML:
```yaml
configure_battery:
  outputs:
    capacity_kwh: RootModel[float] capacity_kwh
    power_kw: RootModel[float] power_kw
    ...
```

This is verbose and doesn't match user expectations.

## Open Questions

1. **Is RootModel wrapping acceptable?** - Does wrapping outputs in `RootModel` break any existing patterns or expectations in `battery_tea` or downstream consumers?

2. **Should introspector be changed?** - Would changing introspector to handle "single complex output" pattern be cleaner than requiring wrapping?

3. **What about SynchronousSim?** - It already uses `MultiOutput` (`SyncSimOutputs`). This pattern is correct and should continue to work.

4. **Field reference implications** - With wrapping, downstream YAML needs `channel.root.field` instead of `channel.field`. Is this acceptable complexity?

## Recommendations

1. **Short-term**: Wrap battery module outputs in `RootModel` pattern to match framework expectations. Update YAML to use `.root` for field access.

2. **Long-term**: Consider adding a "single complex output" mode to the introspector that detects when OutputModel is a regular BaseModel (not MultiOutput/RootModel) and treats it as a single output.

3. **Documentation**: Update CLAUDE.md to clarify the output patterns:
   - `RootModel[T]` for single-value outputs
   - `MultiOutput` subclass for multiple named outputs
   - Regular `BaseModel` outputs are extracted as individual field channels (current behavior)
