# Bug Fix Spec: RootModel Single-Output Introspection

**Status**: Draft
**Priority**: High (Blocking fusion_simkit auto-introspection)
**Affected Component**: `simkit/core/module_introspector.py`
**Created**: 2025-12-08

---

## Problem Statement

Auto-introspection (`create_registry()`) produces incorrect type declarations for single-output modules that use `RootModel[T]` as their OutputModel. This causes field extraction validation to fail when downstream modules try to reference these channels.

### Current Behavior (Broken)

```python
from pydantic import RootModel
from simkit.core.registry_builder import create_registry

class PowerDoubler(ModuleBase[RootModel[float], RootModel[float]]):
    name = "power_doubler"
    version = "v1.0"

    def run(self, root: float) -> ModuleResult[RootModel[float]]:
        return ModuleResult(data=RootModel[float](root * 2))

registry = create_registry([PowerDoubler])
descriptor = registry.get("PowerDoubler")

# BUG: Introspector extracts field type, not OutputModel type
print(descriptor.outputs)  # {'root': <class 'float'>}
```

**Runtime Behavior:**
1. Module returns `RootModel[float](42.0)` object
2. Executor stores **entire RootModel[float] object** in channel (single-output mode)
3. Validator thinks channel contains `float` (from descriptor)
4. Downstream module tries field extraction: `channel.root`
5. Validator tries to check if `float` has field `root`
6. **CRASH**: `AttributeError: type object 'float' has no attribute 'model_computed_fields'`

### Expected Behavior (Fixed)

```python
registry = create_registry([PowerDoubler])
descriptor = registry.get("PowerDoubler")

# FIXED: Introspector detects RootModel and registers the wrapper type
print(descriptor.outputs)  # {'root': <class 'pydantic.RootModel[float]'>}
```

**Runtime Behavior:**
1. Module returns `RootModel[float](42.0)` object
2. Executor stores **entire RootModel[float] object** in channel (single-output mode)
3. Validator knows channel contains `RootModel[float]` (from descriptor)
4. Downstream module tries field extraction: `channel.root`
5. Validator checks if `RootModel[float]` has field `root` of type `float`
6. **SUCCESS**: Validation passes, field extraction works

---

## Root Cause Analysis

### The Introspection Pipeline

**File**: `simkit/core/module_introspector.py:99-144`

```python
def introspect_module(module_cls: Type[ModuleBase]) -> Dict[str, Any]:
    # Extract I/O models
    input_model, output_model = extract_io_models(module_cls)  # RootModel[float]

    # Extract field types from input model
    required_inputs, optional_inputs = extract_field_types(input_model)

    # Extract field types from output model
    outputs, _ = extract_field_types(output_model)  # ← BUG HERE
    # For RootModel[float]: returns {'root': float}
    # Should return: {'root': RootModel[float]} for single-output

    return {
        "module_type": module_cls.__name__,
        "input_model": input_model,     # RootModel[float] (correct)
        "output_model": output_model,   # RootModel[float] (correct)
        "outputs": outputs,             # {'root': float} (WRONG for single-output!)
        ...
    }
```

**File**: `simkit/core/module_introspector.py:74-96`

```python
def extract_field_types(model_cls: Type[BaseModel]) -> tuple[Dict[str, type], Dict[str, type]]:
    """Extract required and optional field types from Pydantic model."""
    required_fields: Dict[str, type] = {}
    optional_fields: Dict[str, type] = {}

    for field_name, field_info in model_cls.model_fields.items():
        field_type = field_info.annotation  # For RootModel[float]: 'root' → float

        if field_info.is_required():
            required_fields[field_name] = field_type
        else:
            optional_fields[field_name] = field_type

    return required_fields, optional_fields
```

**Problem**: For `RootModel[float]`, `model_fields` contains `{'root': FieldInfo(annotation=float)}`, so `extract_field_types()` returns `{'root': float}`. This is correct for **inputs** and **multi-output** modules, but **wrong for single-output** modules where the channel stores the entire `RootModel[float]` object.

### Why This Only Affects Single-Output

**File**: `simkit/core/pipeline_executor.py:217-220`

```python
# Single-output mode - assign entire data to one channel
if len(outputs) == 1:
    binding = next(iter(outputs.values()))
    context.set_channel(binding.channel_name, data)  # ← Stores WHOLE RootModel[float]
```

**File**: `simkit/core/pipeline_executor.py:197-206`

```python
# Multi-output mode - extract fields from MultiOutput container
if isinstance(data, MultiOutput):
    channel_dict = data.to_channel_dict()
    for field, binding in outputs.items():
        context.set_channel(binding.channel_name, channel_dict[field])  # ← Stores EXTRACTED field
```

For **single-output**, the entire OutputModel object is stored.
For **multi-output**, each field is extracted and stored separately.

### Impact on Inputs vs Outputs

| Scenario | Correct Type | Reason |
|----------|-------------|--------|
| **Input** from field extraction | `float` | Field extraction returns unwrapped value |
| **Input** from RootModel channel (via `.root` reference) | `float` | Extracted via `getattr(rootmodel, 'root')` |
| **Output** for single-output RootModel | `RootModel[float]` | Executor stores whole object |
| **Output** for multi-output with RootModel field | `float` | Executor extracts and stores field value |

---

## Proposed Solution

### Option 1: Fix Introspector (Recommended)

Detect `RootModel[T]` OutputModels and register the wrapper type for single-output modules.

**File**: `simkit/core/module_introspector.py`

**Changes:**

1. Add helper function to detect RootModel:

```python
from typing import get_origin
from pydantic import RootModel

def is_rootmodel(model_cls: Type[BaseModel]) -> bool:
    """Check if a Pydantic model is a RootModel."""
    return get_origin(model_cls) is RootModel or (
        hasattr(model_cls, '__orig_bases__') and
        any(get_origin(base) is RootModel for base in model_cls.__orig_bases__)
    )
```

2. Modify `introspect_module()` to handle RootModel outputs:

```python
def introspect_module(module_cls: Type[ModuleBase]) -> Dict[str, Any]:
    # ... existing code ...

    # Extract field types from output model
    outputs_raw, _ = extract_field_types(output_model)

    # SPECIAL CASE: RootModel single-output modules
    # For single-output, the channel stores the WHOLE OutputModel, not extracted fields
    # So the descriptor must declare the OutputModel type, not the field type
    if is_rootmodel(output_model) and len(outputs_raw) == 1:
        # Replace field type with OutputModel type
        field_name = next(iter(outputs_raw.keys()))  # Should be 'root'
        outputs = {field_name: output_model}  # Use RootModel[T], not T
    else:
        # Normal case: use extracted field types
        outputs = outputs_raw

    return {
        "module_type": module_cls.__name__,
        "input_model": input_model,
        "output_model": output_model,
        "required_inputs": required_inputs,
        "optional_inputs": optional_inputs,
        "outputs": outputs,  # Now correct for RootModel single-output
        "version": module_cls.version,
        "name": module_cls.name,
    }
```

**Rationale:**
- Minimal change to introspector
- Fixes the type mismatch at the source
- Preserves existing behavior for multi-output and non-RootModel modules
- Matches what the executor actually stores in channels

### Option 2: Fix Executor (Alternative)

Change single-output behavior for RootModel to extract the field instead of storing the whole object.

**Pros:**
- Makes all outputs consistent (always store field values)
- Descriptor types always match channel contents

**Cons:**
- **Breaking change**: Changes runtime behavior for existing RootModel modules
- Inconsistent with other single-output modules (which store whole object)
- Requires more complex change to executor logic

**Not recommended** due to breaking change.

### Option 3: Fix Validator (Alternative)

Make validator aware of RootModel single-output pattern and use OutputModel type for channel type.

**Pros:**
- No change to introspector or executor
- Keeps descriptor showing field types

**Cons:**
- Adds complexity to validator
- Channel type doesn't match what's actually stored
- Harder to understand/debug

**Not recommended** due to complexity.

---

## Implementation Plan

### Phase 1: Fix Introspector

**File**: `simkit/core/module_introspector.py`

**Changes:**
1. Add `is_rootmodel()` helper function (lines ~15-22)
2. Modify `introspect_module()` to detect RootModel single-output (lines ~129-145)

**Testing:**
1. Update `simkit/tests/core/test_registry_builder.py::test_create_registry_rootmodel_primitives`
2. Verify descriptor outputs contain `RootModel[float]`, not `float`

### Phase 2: Add Integration Test

**File**: `simkit/tests/core/test_registry_builder.py`

Add test for field extraction from RootModel channel:

```python
def test_rootmodel_single_output_field_extraction():
    """Test that field extraction works from RootModel single-output channels.

    This verifies the fix for the RootModel introspection bug where single-output
    modules with RootModel[T] OutputModel were registering T instead of RootModel[T],
    breaking field extraction validation.
    """
    from pydantic import RootModel

    # Producer: single-output RootModel[float]
    class Producer(ModuleBase[RootModel[float], RootModel[float]]):
        name = "producer"
        version = "v1.0"

        def run(self, root: float) -> ModuleResult[RootModel[float]]:
            return ModuleResult(data=RootModel[float](root * 2))

    # Consumer: extracts .root field from producer's channel
    class Consumer(ModuleBase[RootModel[float], RootModel[float]]):
        name = "consumer"
        version = "v1.0"

        def run(self, root: float) -> ModuleResult[RootModel[float]]:
            return ModuleResult(data=RootModel[float](root + 10))

    # Create test pipeline YAML that does field extraction
    # This would previously fail with: AttributeError: type object 'float' has no attribute 'model_computed_fields'

    # ... (full E2E test with execute_pipeline)
```

### Phase 3: Update Documentation

**File**: `/home/reid/teax/docs/rootmodel-and-primitives.md`

**Changes:**
1. Correct the "Type Declaration Reference" table
2. Update manual registration example to show correct types
3. Add note about single-output vs multi-output difference
4. Remove incorrect test from `test_create_registry_rootmodel_primitives`

---

## Acceptance Criteria

### Must Pass

1. ✅ Auto-introspection registers `RootModel[float]` for single-output RootModel modules
2. ✅ Field extraction validation works for RootModel channels (`.root` syntax)
3. ✅ Existing tests continue to pass (no regressions)
4. ✅ fusion_simkit modules can use auto-introspection without errors

### Test Cases

```python
# Test 1: Introspection produces correct types
class SingleOutputModule(ModuleBase[RootModel[float], RootModel[float]]):
    ...

descriptor = introspect_module(SingleOutputModule)
assert descriptor["outputs"]["root"] == RootModel[float]  # NOT float!

# Test 2: Field extraction validation passes
pipeline_yaml = """
modules:
  producer:
    module_type: SingleOutputModule
    outputs:
      root: RootModel[float] channel_a

  consumer:
    module_type: AnotherModule
    inputs:
      value: float channel_a.root  # Must validate successfully
"""

# Test 3: Backward compatibility - non-RootModel modules unchanged
class NormalModule(ModuleBase[MyInput, MyOutput]):
    ...

descriptor = introspect_module(NormalModule)
assert descriptor["outputs"] == extract_field_types(MyOutput)[0]  # Unchanged
```

---

## Migration Guide (for fusion_simkit)

### If Already Using Auto-Introspection

**Before fix:**
```python
# Manual workaround (if you added this)
registry.register("MyModule", ModuleDescriptor(
    required_inputs={"root": float},
    outputs={"root": RootModel[float]},  # Manual override
    ...
))
```

**After fix:**
```python
# Just use auto-introspection - it's fixed!
registry = create_registry([MyModule])  # Works correctly now
```

### If Still Using Manual Registration

**Before fix:**
```python
# fusion_simkit/__init__.py
Float = RootModel[float]

registry.register("PowerModule", ModuleDescriptor(
    required_inputs={"value": Float},     # WRONG - should be float
    outputs={"result": Float},            # CORRECT (for single-output)
    ...
))
```

**After fix (manual registration):**
```python
Float = RootModel[float]

registry.register("PowerModule", ModuleDescriptor(
    required_inputs={"value": float},     # ✅ Use unwrapped for inputs
    outputs={"result": Float},            # ✅ Use wrapped for single-output
    ...
))
```

**After fix (auto-introspection - recommended):**
```python
# Just use create_registry - no manual registration needed!
from simkit.core.registry_builder import create_registry

registry = create_registry([PowerModule, OtherModule, ...])
```

---

## Open Questions

1. **Should we deprecate manual registration for RootModel modules?**
   - Auto-introspection now handles this correctly
   - Manual registration is error-prone

2. **Do we need to handle other RootModel types (int, str, bool)?**
   - Current fix handles all `RootModel[T]` generically
   - Should add tests for `RootModel[int]`, etc.

3. **What about nested RootModels?**
   - E.g., `RootModel[List[RootModel[float]]]`
   - Likely not a real use case, but should verify behavior

---

## Risks & Mitigation

### Risk 1: Breaking Existing Code

**Risk**: Changing descriptor types might break code that depends on current behavior.

**Mitigation**:
- Only affects single-output RootModel modules
- Most code uses multi-output or complex models (unaffected)
- fusion_simkit is the primary user (we control it)
- Add deprecation warning for incorrect manual registrations?

### Risk 2: Incomplete Fix

**Risk**: Fix might not cover all edge cases.

**Mitigation**:
- Add comprehensive test suite
- Test with fusion_simkit modules
- Verify field extraction works in real pipelines

### Risk 3: Documentation Confusion

**Risk**: Users confused about when to use `float` vs `RootModel[float]`.

**Mitigation**:
- Clear documentation with decision tree
- Recommend always using auto-introspection
- Deprecate manual registration for RootModel modules

---

## Timeline

1. **Implement fix**: 1-2 hours (introspector change + tests)
2. **Test with fusion_simkit**: 1 hour (verify all modules work)
3. **Update documentation**: 1 hour
4. **Review & merge**: 1 hour

**Total**: ~4-6 hours

---

## References

- **Executor single-output logic**: `simkit/core/pipeline_executor.py:217-220`
- **Introspector field extraction**: `simkit/core/module_introspector.py:74-96`
- **Validator channel type map**: `simkit/core/pipeline_validator.py:149-153`
- **Field extraction validation**: `simkit/core/pipeline_validator.py:230-274`
- **Test demonstrating bug**: In-memory test created during debugging (2025-12-08)
