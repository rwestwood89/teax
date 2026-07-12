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

# 2. Register manually (single-output RootModel)
registry = PipelineModuleRegistry()
registry.register("PowerDoubler", ModuleDescriptor(
    module_type="PowerDoubler",
    factory=lambda: PowerDoubler(),
    required_inputs={"root": float},           # Unwrapped: from field extraction
    outputs={"root": RootModel[float]},        # Wrapped: channel stores whole object
    version="v1.0"
))
```

**Key rule for single-output RootModel modules**:
- **Inputs**: Use unwrapped type (`float`) - matches field extraction behavior
- **Outputs**: Use wrapped type (`RootModel[float]`) - matches what's stored in channels

Auto-introspection handles this automatically. Manual registration must match this pattern.

## Type Declaration Reference

| What You're Declaring | Type to Use |
|----------------------|-------------|
| Module's InputModel/OutputModel | `RootModel[float]` |
| Module's `run()` parameter | `float` |
| Module's `run()` return | `RootModel[float]` |
| **Registry `required_inputs`** | **`float`** (unwrapped) |
| **Registry `outputs` (single-output)** | **`RootModel[float]`** (wrapped) |
| **Registry `outputs` (multi-output)** | **`float`** (unwrapped) |

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
    root: float temp_f.root                # Extract from RootModel channel
  outputs:
    root: RootModel[float] temp_c          # Stores RootModel[float] in channel
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
    voltage: float config.voltage       # Extract fields from BaseModel
    current: float config.current
  outputs:
    root: RootModel[float] total_power  # Stores RootModel[float] in channel
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
      root: RootModel[float] alpha_power    # Channel stores RootModel[float]

  analyzer:
    module_type: PowerAnalyzer
    inputs:
      root: float alpha_power.root          # Extract .root field → gets float
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
# Single-output: Channel stores WHOLE RootModel[float] object
module_a:
  outputs:
    root: RootModel[float] power_channel

# Field extraction gets unwrapped float
module_b:
  inputs:
    root: float power_channel.root  # .root extracts 500.0 from RootModel
```

**Flow:**
1. Module A returns `RootModel[float](500.0)` object
2. Executor stores **WHOLE object** in channel (single-output mode)
3. Channel `power_channel` contains `RootModel[float](500.0)`
4. Field extraction `.root` calls `getattr(rootmodel, 'root')` → returns `500.0`
5. Module B receives unwrapped `float` parameter `root=500.0`

### Why Inputs Use `float` But Outputs Use `RootModel[float]`

This asymmetry exists because of how TEAx handles single-output modules:

**Inputs** come from field extraction:
```python
# When YAML says: root: float channel.some_field
# Runtime: getattr(channel_value, 'some_field') → returns unwrapped value
# Descriptor must declare: float (what module receives)
```

**Outputs** for single-output go directly to channels:
```python
# Module returns: RootModel[float](42.0)
# Executor stores WHOLE object in channel (pipeline_executor.py:217-220)
# Descriptor must declare: RootModel[float] (what channel contains)
```

Auto-introspection detects this automatically (as of v0.1.0+):
```python
# TEAx introspects RootModel[float] with single output
if is_rootmodel(output_model) and len(outputs) == 1:
    outputs = {"root": RootModel[float]}  # Use wrapper type
else:
    outputs = {"root": float}             # Use field type
```

Manual registration must match this pattern.

## Common Mistake: Wrong Output Type for Single-Output RootModel

```python
# ❌ WRONG - Using float for single-output RootModel outputs
Float = RootModel[float]
registry.register("MyModule", ModuleDescriptor(
    required_inputs={"root": float},    # ✅ Correct - inputs use unwrapped
    outputs={"root": float},            # ❌ WRONG! Should be RootModel[float]
    ...
))
```

**Error you'll see when downstream modules try field extraction:**
```
AttributeError: type object 'float' has no attribute 'model_computed_fields'
```

**Why this happens:**
1. Single-output modules store the **whole OutputModel** in the channel
2. Validator thinks channel contains `float` (from wrong descriptor)
3. Downstream module tries field extraction: `channel.root`
4. Validator tries to check if `float` has a `root` field
5. Fails because `float` is not a Pydantic model

**Fix:**
```python
# ✅ CORRECT - Use RootModel[float] for single-output
registry.register("MyModule", ModuleDescriptor(
    required_inputs={"root": float},           # ✅ Unwrapped for inputs
    outputs={"root": RootModel[float]},        # ✅ Wrapped for single-output
    ...
))

# Or better yet, just use auto-introspection!
registry = create_registry([MyModule])  # Handles this automatically
```

## Persisting and Loading Scalars at the Boundary

The default output router writes these channel types to JSON without consumer registration:

- Bare `float`, `int`, `str`, and `bool` values from multi-output modules.
- `RootModel[float]`, `RootModel[int]`, `RootModel[str]`, and `RootModel[bool]` values from single-output modules.

Both forms use the natural JSON representation. A bare `float` and a `RootModel[float]`
containing `1.25` produce a byte-identical file containing `1.25`.

Declare the shape that is actually stored on the channel:

```yaml
exit:
  module_type: ExitPoint
  outputs:
    efficiency: float efficiency.json
    total_power: RootModel[float] total_power.json
```

ExitPoint validation compares each declared type with the producer's resolvable channel
type. A bare/wrapped mismatch, or a declaration such as `bool` for a `float` channel,
fails before any module runs.

**EntryPoint also loads bare scalars.** An EntryPoint input declared `float`/`int`/`str`/`bool`
reads a raw JSON scalar from its artifact file. Type checking is exact, not coercive: a
JSON integer does not satisfy a `float` input, and JSON `true` does not satisfy an `int`
input (because `bool` is a subclass of `int`, the loader compares exact type identity to
keep them distinct). This makes the boundary symmetric — a scalar the framework can write,
it can also read.

Named domain models still need `custom_schema_types` so TEAx can register their JSON
writer. Other payloads and formats need an explicit `OutputRouter` handler.

The boundary has these limits:

- Passing an explicit `output_router` replaces the default router. That router owns its
  complete handler set.
- `create_output_router_with_json_schemas(..., include_builtins=False)` does not add the
  scalar handlers automatically. `register_handler()` is the deliberate override API, and a
  custom name that collides with a default handler does not replace it.
- `None` means the channel was not produced. The manifest records `produced: false`, and
  TEAx does not write JSON `null`. Other falsy scalar values are written normally.
- `list`, `dict`, `bytes`, `Decimal`, and other unregistered values are not default
  outputs.

## Best Practices

1. **Prefer auto-introspection** - Use `create_registry([YourModule])`
2. **RootModel only for type parameters** - `ModuleBase[RootModel[float], ...]`
3. **Never `RootModel` as BaseModel field** - Use `field: float`, not `field: RootModel[float]`
4. **Field name is always `root`** - When using `RootModel[T]`
5. **Extract with `.root` in YAML** - `channel.root` to get the primitive value

## Summary

- **Module definition**: `ModuleBase[RootModel[float], RootModel[float]]`
- **Module `run()`**: `def run(self, root: float) -> ModuleResult[RootModel[float]]`
- **Registry (manual, single-output)**:
  - `required_inputs={"root": float}`
  - `outputs={"root": RootModel[float]}`
- **Registry (auto)**: Just call `create_registry([YourModule])` ✨
  - Automatically detects single-output RootModel and uses correct types
  - Always prefer this over manual registration!
