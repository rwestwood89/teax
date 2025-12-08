# Using Primitive Types in TEAx Modules

## Quick Start: Two Ways to Register Modules

### Pattern 1: Auto-Introspection (Recommended)

```python
from pydantic import RootModel
from simkit.core.base import ModuleBase, ModuleResult
from simkit.core.registry_builder import create_registry

# 1. Define your module
class PowerDoubler(ModuleBase[RootModel[float], RootModel[float]]):
    name = "power_doubler"
    version = "v1.0"

    def run(self, root: float) -> ModuleResult[RootModel[float]]:
        return ModuleResult(data=RootModel[float](root * 2))

# 2. Register automatically - that's it!
registry = create_registry([PowerDoubler])
```

**Use this pattern.** TEAx automatically figures out the correct types.

### Pattern 2: Manual Registration

```python
from pydantic import RootModel
from simkit.core.pipeline_registry import ModuleDescriptor, PipelineModuleRegistry

# 1. Define your module (same as above)
class PowerDoubler(ModuleBase[RootModel[float], RootModel[float]]):
    name = "power_doubler"
    version = "v1.0"

    def run(self, root: float) -> ModuleResult[RootModel[float]]:
        return ModuleResult(data=RootModel[float](root * 2))

# 2. Register manually
registry = PipelineModuleRegistry()
registry.register("PowerDoubler", ModuleDescriptor(
    module_type="PowerDoubler",
    factory=lambda: PowerDoubler(),
    required_inputs={"root": float},     # Use float, not RootModel[float]
    outputs={"root": float},             # Use float, not RootModel[float]
    version="v1.0"
))
```

**Key rule**: Register the **unwrapped field type** (`float`), not the wrapper (`RootModel[float]`), for both inputs and outputs. This matches what auto-introspection extracts.

## Type Declaration Reference

| What You're Declaring | Type to Use |
|----------------------|-------------|
| Module's InputModel/OutputModel | `RootModel[float]` |
| Module's `run()` parameter | `float` |
| Module's `run()` return | `RootModel[float]` |
| **Registry `required_inputs`** | **`float`** |
| **Registry `outputs`** | **`float`** |

## Complete Examples

### Example 1: Simple Primitive Module

```python
from pydantic import RootModel
from simkit.core.base import ModuleBase, ModuleResult

class TemperatureConverter(ModuleBase[RootModel[float], RootModel[float]]):
    name = "temp_converter"
    version = "v1.0"

    def run(self, root: float) -> ModuleResult[RootModel[float]]:
        # Input: Fahrenheit (unwrapped float)
        celsius = (root - 32) * 5/9
        # Output: Celsius (wrapped in RootModel)
        return ModuleResult(data=RootModel[float](celsius))
```

**YAML usage:**
```yaml
converter:
  module_type: TemperatureConverter
  inputs:
    root: float temp_f.root          # Extract from RootModel channel
  outputs:
    root: float temp_c                # Store as RootModel in channel
```

### Example 2: Complex Input, Primitive Output

```python
from pydantic import BaseModel

class PowerConfig(BaseModel):
    voltage: float
    current: float

class PowerCalculator(ModuleBase[PowerConfig, RootModel[float]]):
    name = "power_calc"
    version = "v1.0"

    def run(self, voltage: float, current: float) -> ModuleResult[RootModel[float]]:
        power = voltage * current
        return ModuleResult(data=RootModel[float](power))
```

**YAML usage:**
```yaml
calculator:
  module_type: PowerCalculator
  inputs:
    voltage: float config.voltage    # Extract fields from BaseModel
    current: float config.current
  outputs:
    root: float total_power          # Store as RootModel
```

### Example 3: Multiple Modules with Primitives

```python
# Module 1: Outputs primitive
class AlphaCalculator(ModuleBase[FusionParams, RootModel[float]]):
    name = "alpha_calc"
    version = "v1.0"

    def run(self, p_fusion: float) -> ModuleResult[RootModel[float]]:
        alpha_power = p_fusion * 0.2
        return ModuleResult(data=RootModel[float](alpha_power))

# Module 2: Consumes primitive
class PowerAnalyzer(ModuleBase[RootModel[float], AnalysisResult]):
    name = "power_analyzer"
    version = "v1.0"

    def run(self, root: float) -> ModuleResult[AnalysisResult]:
        analysis = AnalysisResult(power=root, status="ok")
        return ModuleResult(data=analysis)
```

**YAML usage:**
```yaml
modules:
  alpha:
    module_type: AlphaCalculator
    inputs:
      p_fusion: float params.p_fusion
    outputs:
      root: float alpha_power          # RootModel[float] stored here

  analyzer:
    module_type: PowerAnalyzer
    inputs:
      root: float alpha_power.root     # Extract .root field
    outputs:
      result: AnalysisResult analysis
```

## What's Happening Under the Hood

### Why RootModel?

Pydantic requires all data to be structured as `BaseModel`. For single primitive values, `RootModel[T]` wraps them:

```python
from pydantic import RootModel

Float = RootModel[float]

# Creating and accessing
value = Float(42.0)
print(value.root)  # 42.0

# Has one field named 'root'
print(Float.model_fields)  # {'root': FieldInfo(annotation=float, ...)}
```

### Data Flow in Pipeline

```yaml
# Channel stores RootModel[float](500.0)
module_a:
  outputs:
    root: float power_channel

# Field extraction gets float
module_b:
  inputs:
    root: float power_channel.root  # .root extracts the 500.0 float
```

**Flow:**
1. Module A returns `RootModel[float](500.0)`
2. Channel `power_channel` stores `RootModel[float](500.0)`
3. Field extraction `.root` returns `500.0` as `float`
4. Module B receives `float` parameter `root=500.0`

### Why Registry Uses `float` Not `RootModel[float]`

The registry declares **what modules receive/produce at the field level**:

- **Inputs**: After field extraction, modules receive unwrapped `float`
- **Outputs**: The OutputModel has a field `root` of type `float`

Auto-introspection does this automatically:
```python
# TEAx introspects RootModel[float]
RootModel[float].model_fields  # {'root': float}

# Extracts field types
required_inputs = {"root": float}  # Not RootModel[float]!
outputs = {"root": float}
```

Manual registration must match this: use `float`, not `RootModel[float]`.

## Common Mistake: Wrong Registry Types

```python
# ❌ WRONG - Using RootModel[float] in registry
Float = RootModel[float]
registry.register("MyModule", ModuleDescriptor(
    required_inputs={"value": Float},  # WRONG! Causes validation errors
    outputs={"result": Float},         # WRONG! Also incorrect
    ...
))

# ✅ CORRECT - Use unwrapped float
registry.register("MyModule", ModuleDescriptor(
    required_inputs={"value": float},  # ✅ Matches what field extraction returns
    outputs={"result": float},         # ✅ Matches what introspection extracts
    ...
))
```

**Error you'll see:**
```
Type mismatch for field 'params.value'.
Expected type 'RootModel[float]', but field has type 'float'
```

**Why this happens:** Field extraction from schemas returns the raw field type (`float`), not a wrapped `RootModel[float]`. The descriptor must declare what modules actually receive, which is the unwrapped type.

**Fix:** Use `float` for both inputs and outputs in manual registrations, matching auto-introspection behavior.

## Best Practices

1. **Prefer auto-introspection** - Use `create_registry([YourModule])`
2. **RootModel only for type parameters** - `ModuleBase[RootModel[float], ...]`
3. **Never `RootModel` as BaseModel field** - Use `field: float`, not `field: RootModel[float]`
4. **Field name is always `root`** - When using `RootModel[T]`
5. **Extract with `.root` in YAML** - `channel.root` to get the primitive value

## Summary

- **Module definition**: `ModuleBase[RootModel[float], RootModel[float]]`
- **Module `run()`**: `def run(self, root: float) -> ModuleResult[RootModel[float]]`
- **Registry (manual)**: `required_inputs={"root": float}`, `outputs={"root": float}`
- **Registry (auto)**: Just call `create_registry([YourModule])` ✨
