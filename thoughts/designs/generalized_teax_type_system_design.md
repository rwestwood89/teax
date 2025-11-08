# Generalized TEAx Type System Design

**Date:** 2025-11-08
**Status:** Specification
**Context:** Making TEAx a generalizable framework for external users with custom modules

---

## Executive Summary

This design addresses four critical limitations identified by TEAx users developing custom simulation modules. The current type system is too rigid, assuming all modules use TEAx's internal `StrictBaseModel` schema and enforcing patterns that make multi-output modules difficult to implement and introspect.

**Goals:**
1. Support any Pydantic `BaseModel` subclass as channel data (not just `StrictBaseModel`)
2. Make multi-output pattern explicit and introspectable
3. Remove TypeVar constraint violations for multi-output modules
4. Provide optional support for primitive types in channels

**Non-Goals:**
- Breaking backward compatibility with existing TEAx modules
- Runtime behavior changes (only type system and introspection)
- Supporting non-Pydantic data types

---

## Problem Statement

### Current Architecture Assumptions

TEAx was designed with these implicit assumptions:

1. **All schemas inherit from `simkit.config.schema.StrictBaseModel`**
   - Enforced in `ModuleDescriptor` type hints
   - Not enforced at runtime (works fine with plain `BaseModel`)

2. **Single-output is the default, multi-output is an undocumented exception**
   - Single-output: Return `OutputModel` directly
   - Multi-output: Return `Dict[str, BaseModel]` (breaks type constraint!)

3. **Module introspection assumes single BaseModel output**
   - `extract_io_models()` requires `OutputModel` to be a `BaseModel` subclass
   - Fails for `Dict[str, BaseModel]` pattern

4. **All channel data must be Pydantic models**
   - Cannot pass primitives like `float`, `str`, `int`
   - Forces wrapper boilerplate: `PowerValue(value=123.4)`

### Impact on External Users

**Scenario:** Fusion modeling team building custom TEAx modules

**Pain Points:**
- 50+ Pyright type errors from `StrictBaseModel` constraint
- Cannot use `create_registry()` for multi-output modules
- Must manually register all modules (defeats automation)
- Must create wrapper classes for simple numeric outputs
- No documentation on single vs. multi-output patterns

---

## Design Principles

### 1. **Accept Any BaseModel** (Principle of Least Surprise)

TEAx should work with **any Pydantic BaseModel subclass**, not just its internal schemas.

**Rationale:**
- Pydantic provides the interface contract (`model_dump()`, `model_fields`, validation)
- `StrictBaseModel` is an implementation detail, not a public API requirement
- External users shouldn't need to depend on TEAx schema internals

### 2. **Explicit is Better Than Implicit** (Multi-Output)

The distinction between single-output and multi-output should be **declared in Python**, not inferred from YAML.

**Rationale:**
- Current pattern: Mode determined by YAML `len(outputs)` check at runtime
- Problems: Type system can't express it, introspection can't detect it, confusing DX
- Solution: Explicit output model pattern distinguishes the two modes

### 3. **Type Safety Without Type Violations** (No type: ignore)

The type system should accurately reflect runtime behavior without requiring `# type: ignore`.

**Rationale:**
- `Dict[str, BaseModel]` violates `OutputModel = TypeVar("OutputModel", bound=BaseModel)`
- External users shouldn't need to add ignore comments for valid patterns
- Type checker should help, not hinder

### 4. **Progressive Enhancement** (Backward Compatible)

All changes must maintain backward compatibility with existing TEAx modules.

**Rationale:**
- Cannot break `RateDataModule`, `SimplePerformanceSimModule`, etc.
- Existing YAML pipelines must continue working
- New features opt-in, not breaking changes

---

## Solution Architecture

### Component 1: Relax Type Constraints

**File:** `simkit/core/pipeline_registry.py`

**Change:** Accept any `BaseModel` subclass in `ModuleDescriptor`

**Before:**
```python
@dataclass(frozen=True)
class ModuleDescriptor:
    module_type: str
    factory: Callable[[], ModuleBase]
    required_inputs: Mapping[str, type[schema.StrictBaseModel]]  # ← Too restrictive
    optional_inputs: Mapping[str, type[schema.StrictBaseModel]]  # ← Too restrictive
    outputs: Mapping[str, type[schema.StrictBaseModel]]          # ← Too restrictive
    version: str
```

**After:**
```python
from pydantic import BaseModel

@dataclass(frozen=True)
class ModuleDescriptor:
    module_type: str
    factory: Callable[[], ModuleBase]
    required_inputs: Mapping[str, type[BaseModel]]  # ✓ Any BaseModel
    optional_inputs: Mapping[str, type[BaseModel]]  # ✓ Any BaseModel
    outputs: Mapping[str, type[BaseModel]]          # ✓ Any BaseModel
    version: str
```

**Impact:**
- ✅ Eliminates 50+ Pyright errors for external users
- ✅ No runtime behavior change (already worked)
- ✅ Backward compatible (StrictBaseModel IS-A BaseModel)
- ✅ Self-documents that any BaseModel is acceptable

**Risk:** Very low - purely a type hint change

---

### Component 2: Explicit Multi-Output Pattern

**File:** `simkit/config/schema.py`

**Change:** Introduce `MultiOutput` container model

**New Schema:**
```python
class MultiOutput(StrictBaseModel):
    """Container for modules that produce multiple typed outputs.

    Use this as the OutputModel for modules that need to route different
    data types to different downstream modules.

    Example:
        class AlphaNeutronSplitOutput(MultiOutput):
            p_alpha: PowerValue
            p_neutron: PowerValue

        class AlphaNeutronSplitModule(
            ModuleBase[FusionInput, AlphaNeutronSplitOutput]
        ):
            def run(self, ...) -> ModuleResult[AlphaNeutronSplitOutput]:
                return ModuleResult(
                    data=AlphaNeutronSplitOutput(
                        p_alpha=PowerValue(value=520.5),
                        p_neutron=PowerValue(value=2079.4),
                    )
                )
    """
    # No additional fields - just a marker base class
    # Subclasses define their own output fields

    def to_channel_dict(self) -> Dict[str, BaseModel]:
        """Convert multi-output fields to channel routing dict.

        Returns dict with field names as keys, field values as values.
        Used by executor to route outputs to separate channels.
        """
        return {
            field_name: getattr(self, field_name)
            for field_name in self.model_fields.keys()
        }
```

**Benefit:**
- ✓ `MultiOutput` IS-A `BaseModel` (satisfies TypeVar constraint!)
- ✓ Introspection can detect it: `issubclass(OutputModel, MultiOutput)`
- ✓ Self-documenting: seeing `MultiOutput` signals multi-output mode
- ✓ Type-safe: `AlphaNeutronSplitOutput.p_alpha` is statically typed

**Comparison to Current Dict Pattern:**

**Current (type violation):**
```python
class AlphaNeutronSplitModule(
    ModuleBase[Input, Dict[str, BaseModel]]  # ❌ Dict not a BaseModel!
):
    def run(self, ...) -> ModuleResult[Dict[str, BaseModel]]:
        return ModuleResult(data={
            "p_alpha": PowerValue(value=520.5),
            "p_neutron": PowerValue(value=2079.4),
        })
```

**Proposed (type-safe):**
```python
class AlphaNeutronSplitOutput(MultiOutput):
    p_alpha: PowerValue
    p_neutron: PowerValue

class AlphaNeutronSplitModule(
    ModuleBase[Input, AlphaNeutronSplitOutput]  # ✓ MultiOutput IS-A BaseModel!
):
    def run(self, ...) -> ModuleResult[AlphaNeutronSplitOutput]:
        return ModuleResult(
            data=AlphaNeutronSplitOutput(
                p_alpha=PowerValue(value=520.5),
                p_neutron=PowerValue(value=2079.4),
            )
        )
```

---

### Component 3: Update Pipeline Executor

**File:** `simkit/core/pipeline_executor.py:164-176`

**Change:** Detect `MultiOutput` and extract fields

**Before:**
```python
outputs = module_spec.outputs
result = module.run(**kwargs)
data = result.data

if len(outputs) == 1:
    # Single-output mode
    binding = next(iter(outputs.values()))
    context.set_channel(binding.channel_name, data)
else:
    # Multi-output mode - expects dict
    if not isinstance(data, Mapping):
        raise RuntimeError(
            f"Module '{module_key}' produced multiple outputs but returned non-mapping data"
        )
    for field, binding in outputs.items():
        context.set_channel(binding.channel_name, data[field])
```

**After:**
```python
from ..config.schema import MultiOutput

outputs = module_spec.outputs
result = module.run(**kwargs)
data = result.data

# Check if module returned MultiOutput container
if isinstance(data, MultiOutput):
    # Multi-output mode - extract fields from container
    channel_dict = data.to_channel_dict()
    for field, binding in outputs.items():
        if field not in channel_dict:
            raise RuntimeError(
                f"Module '{module_key}' MultiOutput missing field '{field}' "
                f"declared in YAML. Available fields: {list(channel_dict.keys())}"
            )
        context.set_channel(binding.channel_name, channel_dict[field])
    context.module_versions[module_key] = descriptor.version
    return

# Legacy multi-output mode - dict pattern (backward compatibility)
if len(outputs) > 1 and isinstance(data, Mapping):
    for field, binding in outputs.items():
        context.set_channel(binding.channel_name, data[field])
    context.module_versions[module_key] = descriptor.version
    return

# Single-output mode - assign entire data to one channel
if len(outputs) == 1:
    binding = next(iter(outputs.values()))
    context.set_channel(binding.channel_name, data)
else:
    # Error: multiple outputs declared but data is neither MultiOutput nor dict
    raise RuntimeError(
        f"Module '{module_key}' declared {len(outputs)} outputs in YAML "
        f"but returned {type(data).__name__} instead of MultiOutput or dict"
    )

context.module_versions[module_key] = descriptor.version
```

**Behavior:**
1. **First**: Check if `data` is `MultiOutput` instance → extract fields
2. **Second**: Backward compatibility check for dict pattern (supports old `SynchronousSimModule`)
3. **Third**: Single-output mode (current default behavior)
4. **Error**: Multiple outputs declared but wrong return type

**Impact:**
- ✅ New `MultiOutput` pattern works
- ✅ Backward compatible with existing dict pattern
- ✅ Backward compatible with single-output pattern
- ✅ Better error messages

---

### Component 4: Update Module Introspector

**File:** `simkit/core/module_introspector.py`

**Change:** Support `MultiOutput` introspection

**Add to `extract_io_models()`:**

```python
def extract_io_models(module_cls: Type[ModuleBase]) -> tuple[Type[BaseModel], Type[BaseModel] | Type[MultiOutput]]:
    """Extract InputModel and OutputModel from ModuleBase generic type hints.

    Returns:
        Tuple of (InputModel, OutputModel) where OutputModel may be:
        - BaseModel subclass (single-output)
        - MultiOutput subclass (multi-output)
        - Dict[str, BaseModel] (legacy multi-output, deprecated)
    """
    # ... existing validation code ...

    input_model, output_model = type_args

    # Validate input is BaseModel
    if not (isinstance(input_model, type) and issubclass(input_model, BaseModel)):
        raise ModuleIntrospectionError(
            f"Input type parameter must be a Pydantic BaseModel subclass. "
            f"Got: {input_model}"
        )

    # Validate output is BaseModel OR MultiOutput
    if isinstance(output_model, type) and issubclass(output_model, BaseModel):
        # Valid: single-output or MultiOutput subclass
        return input_model, output_model

    # Check for legacy Dict[str, BaseModel] pattern (backward compatibility)
    origin = get_origin(output_model)
    if origin is dict:
        args = get_args(output_model)
        if len(args) == 2 and args[0] is str:
            # Legacy multi-output pattern - issue deprecation warning
            import warnings
            warnings.warn(
                f"Module {module_cls.__name__} uses Dict[str, BaseModel] output pattern. "
                f"This pattern is deprecated. Please use MultiOutput instead. "
                f"See: simkit/config/schema.py::MultiOutput",
                DeprecationWarning,
                stacklevel=2
            )
            # Return as-is for backward compatibility, but introspection will handle specially
            return input_model, output_model

    # Invalid output type
    raise ModuleIntrospectionError(
        f"Output type parameter must be a Pydantic BaseModel subclass or MultiOutput. "
        f"Got: {output_model}"
    )
```

**Add to `introspect_module()`:**

```python
def introspect_module(module_cls: Type[ModuleBase]) -> Dict[str, Any]:
    """Introspect module to extract all metadata needed for ModuleDescriptor."""
    # ... existing code ...

    input_model, output_model = extract_io_models(module_cls)

    # Extract field types from input model
    required_inputs, optional_inputs = extract_field_types(input_model)

    # Extract outputs based on output model type
    if isinstance(output_model, type) and issubclass(output_model, MultiOutput):
        # Multi-output: extract all fields from MultiOutput container
        outputs, _ = extract_field_types(output_model)
    elif isinstance(output_model, type) and issubclass(output_model, BaseModel):
        # Single-output: output model itself is the only output
        # Use module name or "output" as default field name
        output_field_name = module_cls.name.lower() + "_output"
        outputs = {output_field_name: output_model}
    else:
        # Legacy Dict[str, BaseModel] - cannot introspect field types
        # User must manually register
        raise ModuleIntrospectionError(
            f"Cannot auto-introspect Dict[str, BaseModel] output pattern for {module_cls.__name__}. "
            f"Please use MultiOutput or manually register this module."
        )

    metadata = {
        "module_type": module_cls.__name__,
        "input_model": input_model,
        "output_model": output_model,
        "required_inputs": required_inputs,
        "optional_inputs": optional_inputs,
        "outputs": outputs,
        "version": module_cls.version,
        "name": module_cls.name,
    }

    return metadata
```

**Impact:**
- ✅ `create_registry()` now works with `MultiOutput` modules
- ✅ Automatic field extraction from `MultiOutput` subclasses
- ✅ Deprecation warning for old dict pattern (soft migration path)
- ✅ Clear error for unsupported patterns

---

### Component 5: Remove OutputModel TypeVar Constraint (Optional)

**File:** `simkit/core/base.py`

**Status:** Optional - only needed if we want to support legacy dict pattern without deprecation

**Change:**
```python
# Before:
OutputModel = TypeVar("OutputModel", bound=BaseModel)

# After (Option A - Remove bound):
OutputModel = TypeVar("OutputModel")

# After (Option B - Union bound - DOESN'T WORK):
OutputModel = TypeVar("OutputModel", bound=Union[BaseModel, Dict[str, BaseModel]])  # ❌ Not valid syntax
```

**Recommendation:**
- **Don't remove the bound** if we're introducing `MultiOutput`
- `MultiOutput` IS-A `BaseModel`, so it satisfies the constraint
- Keep the bound for better self-documentation
- Only remove if we need to support dict pattern indefinitely

---

### Component 6: Primitive Type Support (Future Enhancement)

**Status:** Phase 2 - Not included in initial implementation

**Goal:** Allow `float`, `str`, `int` in channels without wrapper models

**Approach:** Auto-wrapping at channel boundaries

**Example:**
```python
# YAML (future):
outputs:
  temperature: float temperature
  pressure: float pressure

# TEAx generates internal wrapper:
class _FloatChannelValue(BaseModel):
    value: float

# Module returns unwrapped:
def run(self, ...) -> ModuleResult[float]:
    return ModuleResult(data=123.4)

# Executor auto-wraps:
context.set_channel("temperature", _FloatChannelValue(value=123.4))

# Downstream module receives unwrapped:
def run(self, temperature: float, ...):  # Receives 123.4, not wrapper
    ...
```

**Implementation Plan:**
1. Define generic wrappers in `simkit/config/schema.py`:
   ```python
   class FloatValue(StrictBaseModel):
       value: float

   class StrValue(StrictBaseModel):
       value: str

   class IntValue(StrictBaseModel):
       value: int
   ```

2. Update YAML parser to recognize primitive type names

3. Update executor to auto-wrap/unwrap at channel boundaries

4. Update introspector to handle primitive annotations

**Defer Rationale:**
- Medium complexity, medium benefit
- Users can use wrapper pattern for now (documented workaround)
- Priority 1-3 fixes are more impactful
- Can add later without breaking changes

---

## Implementation Plan

### Phase 1: Type System Fixes (High Priority)

**Issue 1: Relax StrictBaseModel constraint**
- [ ] Update `ModuleDescriptor` type hints to accept `BaseModel`
- [ ] Update all type hints in `pipeline_registry.py`
- [ ] Run Pyright on fusion_modeling project - should eliminate 50+ errors
- [ ] Run existing tests - should pass unchanged

**Issue 2: Multi-Output pattern**
- [ ] Add `MultiOutput` base class to `simkit/config/schema.py`
- [ ] Update `pipeline_executor.py` to detect and handle `MultiOutput`
- [ ] Maintain backward compatibility with dict pattern
- [ ] Add tests for both patterns

**Issue 3: Introspection support**
- [ ] Update `extract_io_models()` to accept `MultiOutput`
- [ ] Update `introspect_module()` to extract fields from `MultiOutput`
- [ ] Add deprecation warning for dict pattern
- [ ] Add tests for `create_registry()` with multi-output modules

**Issue 4: Documentation**
- [ ] Document single-output pattern in `CLAUDE.md`
- [ ] Document `MultiOutput` pattern in `CLAUDE.md`
- [ ] Add migration guide for dict → `MultiOutput`
- [ ] Update `thoughts/research/input_output_asymmetry_analysis.md` with new pattern

### Phase 2: Primitive Type Support (Future)

- [ ] Define generic value wrappers (`FloatValue`, `StrValue`, `IntValue`)
- [ ] Update YAML parser to recognize primitive types
- [ ] Implement auto-wrapping in executor
- [ ] Update introspector for primitive handling
- [ ] Add tests and documentation

---

## Migration Guide

### For Existing TEAx Modules (No Changes Required)

All existing modules continue working:

```python
# Single-output modules - unchanged
class SimplePerformanceSimModule(
    ModuleBase[PerformanceInputs, schema.BatteryTelemetry8760]
):
    def run(self, ...) -> ModuleResult[schema.BatteryTelemetry8760]:
        return ModuleResult(telemetry)  # ✓ Still works
```

```python
# Multi-output modules using dict - still works, but deprecated
class SynchronousSimModule(
    ModuleBase[SynchronousSimInputs, Dict[str, schema.StrictBaseModel]]
):
    def run(self, ...) -> ModuleResult[Dict[str, schema.StrictBaseModel]]:
        return ModuleResult({
            "forecasts": ...,
            "guidances": ...,
        })  # ✓ Still works (deprecation warning)
```

### For New Custom Modules (Use MultiOutput)

**Single-output (no changes):**
```python
class BlanketThermalPowerModule(ModuleBase[BlanketInput, PowerValue]):
    def run(self, ...) -> ModuleResult[PowerValue]:
        return ModuleResult(data=PowerValue(value=p_thermal))
```

**Multi-output (use MultiOutput):**
```python
from simkit.config.schema import MultiOutput

class AlphaNeutronSplitOutput(MultiOutput):
    """Typed container for fusion power split outputs."""
    p_alpha: PowerValue
    p_neutron: PowerValue

class AlphaNeutronSplitModule(
    ModuleBase[FusionInput, AlphaNeutronSplitOutput]
):
    name = "AlphaNeutronSplit"
    version = "v0.1"

    def run(self, fusion_params: FusionParams) -> ModuleResult[AlphaNeutronSplitOutput]:
        p_alpha, p_neutron = calculate_split(fusion_params)

        return ModuleResult(
            data=AlphaNeutronSplitOutput(
                p_alpha=PowerValue(value=p_alpha),
                p_neutron=PowerValue(value=p_neutron),
            )
        )
```

**YAML (unchanged):**
```yaml
alphaneutronsplit:
  module_type: AlphaNeutronSplit
  inputs:
    fusion_params: FusionParams fusion_params
  outputs:
    p_alpha: PowerValue p_alpha
    p_neutron: PowerValue p_neutron
```

**Registry (now auto-introspection works!):**
```python
from simkit.core.registry_builder import create_registry

# Before: Had to manually register multi-output modules
# After: Auto-introspection works!
registry = create_registry([
    AlphaNeutronSplitModule,      # ✓ Now works! (was broken before)
    BlanketThermalPowerModule,
    GrossElectricPowerModule,
])
```

### Migrating Dict Pattern to MultiOutput

**Step 1:** Define output container

```python
# Before:
class MyModule(ModuleBase[Input, Dict[str, BaseModel]]):
    ...

# After:
class MyModuleOutput(MultiOutput):
    field1: Type1
    field2: Type2

class MyModule(ModuleBase[Input, MyModuleOutput]):
    ...
```

**Step 2:** Update run() method

```python
# Before:
def run(self, ...) -> ModuleResult[Dict[str, BaseModel]]:
    return ModuleResult(data={
        "field1": Type1(...),
        "field2": Type2(...),
    })

# After:
def run(self, ...) -> ModuleResult[MyModuleOutput]:
    return ModuleResult(
        data=MyModuleOutput(
            field1=Type1(...),
            field2=Type2(...),
        )
    )
```

**Step 3:** Remove type: ignore comments

```python
# Before:
class MyModule(
    ModuleBase[Input, Dict[str, BaseModel]]  # type: ignore[type-arg]
):
    ...

# After:
class MyModule(ModuleBase[Input, MyModuleOutput]):  # ✓ No ignore needed!
    ...
```

---

## Testing Strategy

### Unit Tests

**`simkit/tests/core/test_pipeline_executor.py`:**
- [ ] Test single-output module (existing - should pass)
- [ ] Test `MultiOutput` module extraction
- [ ] Test backward compatibility with dict pattern
- [ ] Test error when multi-output YAML but single-output return
- [ ] Test error when MultiOutput missing declared field

**`simkit/tests/core/test_module_introspector.py`:**
- [ ] Test introspection of single-output module
- [ ] Test introspection of `MultiOutput` module
- [ ] Test deprecation warning for dict pattern
- [ ] Test error for unsupported output types

**`simkit/tests/core/test_registry_builder.py`:**
- [ ] Test `create_registry()` with single-output modules
- [ ] Test `create_registry()` with `MultiOutput` modules
- [ ] Test manual registration still works

### Integration Tests

**Fusion modeling test suite:**
- [ ] Migrate `AlphaNeutronSplitModule` to `MultiOutput` pattern
- [ ] Run all fusion pipeline tests - should pass
- [ ] Verify Pyright errors eliminated
- [ ] Verify `create_registry()` works

---

## Success Criteria

### Must Have (Phase 1)

1. ✅ **Zero Pyright errors** in fusion_modeling project
2. ✅ **`create_registry()` works** with multi-output modules
3. ✅ **Backward compatibility** - all existing TEAx tests pass
4. ✅ **No `# type: ignore` needed** for valid module patterns
5. ✅ **Documentation** of single vs. multi-output patterns

### Should Have (Phase 1)

6. ✅ **Migration guide** from dict to `MultiOutput`
7. ✅ **Deprecation warnings** for dict pattern
8. ✅ **Test coverage** for new `MultiOutput` path

### Nice to Have (Phase 2)

9. ⏸️ **Primitive type support** (defer to future)
10. ⏸️ **Auto-wrapper generation** (defer to future)

---

## Risks and Mitigations

### Risk 1: Breaking Existing Modules

**Risk:** Type hint changes break existing code

**Mitigation:**
- `StrictBaseModel` IS-A `BaseModel` (Liskov substitution)
- All type changes are **widening** constraints, not narrowing
- Comprehensive test suite runs on all existing modules
- Migration can be gradual (dict pattern deprecated, not removed)

**Likelihood:** Very Low
**Impact:** High
**Mitigation Effectiveness:** High

### Risk 2: MultiOutput Adoption Friction

**Risk:** Users don't understand new pattern

**Mitigation:**
- Clear documentation with examples
- Migration guide with before/after code
- Deprecation warnings point to docs
- Both patterns work during transition

**Likelihood:** Medium
**Impact:** Medium
**Mitigation Effectiveness:** High

### Risk 3: Introspection Edge Cases

**Risk:** Complex output types break introspection

**Mitigation:**
- Manual registration fallback always available
- Clear error messages for unsupported patterns
- Test complex scenarios (nested models, optional fields, unions)
- Document introspection limitations

**Likelihood:** Medium
**Impact:** Low (manual registration works)
**Mitigation Effectiveness:** High

---

## Alternative Approaches Considered

### Alternative 1: Keep Dict Pattern, Remove TypeVar Bound

**Approach:**
```python
OutputModel = TypeVar("OutputModel")  # No bound constraint
```

**Pros:**
- Minimal code change
- Dict pattern works without type errors

**Cons:**
- Loses type safety documentation
- Doesn't solve introspection problem
- Still confusing two-mode pattern
- Allows nonsensical types like `ModuleBase[Input, str]`

**Decision:** Rejected - doesn't solve root problems

### Alternative 2: Separate Base Classes for Single/Multi

**Approach:**
```python
class SingleOutputModule(ModuleBase[Input, Output]):
    ...

class MultiOutputModule(ModuleBase[Input, OutputContainer]):
    ...
```

**Pros:**
- Explicit mode distinction
- Type-safe

**Cons:**
- Code duplication
- Two base classes to maintain
- Breaking change for existing modules
- Complicates registry/executor

**Decision:** Rejected - too invasive

### Alternative 3: Decorator-Based Mode Declaration

**Approach:**
```python
@multi_output(fields=["field1", "field2"])
class MyModule(ModuleBase[Input, Output]):
    ...
```

**Pros:**
- Explicit mode declaration
- No new base classes

**Cons:**
- Decorator magic
- Introspection more complex
- Doesn't solve TypeVar bound issue
- Less "Pythonic" than inheritance

**Decision:** Rejected - doesn't solve core type issues

### Selected Approach: MultiOutput Marker Class

**Why:**
- ✅ IS-A relationship preserves type safety
- ✅ Introspectable via `isinstance()` / `issubclass()`
- ✅ Self-documenting pattern
- ✅ Minimal code change
- ✅ Backward compatible
- ✅ Solves all four reported issues

---

## Open Questions

### Q1: Should we remove dict pattern entirely?

**Options:**
A. Keep indefinitely (backward compat)
B. Deprecate now, remove in v2.0
C. Remove immediately

**Recommendation:** Option B
- Soft deprecation via warning
- Document migration path
- Remove in next major version
- SynchronousSimModule migrates as example

### Q2: Should MultiOutput be required or optional?

**Current Design:** Optional
- Single-output: plain BaseModel
- Multi-output: MultiOutput subclass

**Alternative:** Always require output container

**Recommendation:** Keep optional
- Single-output common case should be simple
- MultiOutput only when needed
- Reduces boilerplate for 80% case

### Q3: Should we support Dict[str, primitive] outputs?

**Example:**
```python
ModuleResult[Dict[str, float]]  # {"temp": 123.4, "pressure": 45.6}
```

**Recommendation:** No
- Primitives should use Phase 2 auto-wrapping
- Dict should be Dict[str, BaseModel] only
- Keeps channel type system consistent

---

## References

- **User Report:** `/home/reid/fusion_modeling/project/research/teax_integration_issues_and_limitations.md`
- **Current Analysis:** `/home/reid/teax/thoughts/research/input_output_asymmetry_analysis.md`
- **Type System Explanation:** `/home/reid/teax/thoughts/research/type_system_explanation.md`
- **Module Introspector:** `/home/reid/teax/simkit/core/module_introspector.py`
- **Pipeline Executor:** `/home/reid/teax/simkit/core/pipeline_executor.py:164-176`
- **Module Registry:** `/home/reid/teax/simkit/core/pipeline_registry.py:20-29`

---

## Appendix: Code Examples

### Example 1: Fusion Module Migration

**Before (current workaround):**
```python
class AlphaNeutronSplitModule(
    ModuleBase[AlphaNeutronSplitInput, Dict[str, BaseModel]]  # type: ignore[type-arg]
):
    name = "AlphaNeutronSplit"
    version = "v0.1"

    def validate_and_fill_default(
        self, fusion_params: FusionParams | dict[str, Any]
    ) -> AlphaNeutronSplitInput:
        return AlphaNeutronSplitInput(fusion_params=fusion_params)

    def run(
        self, fusion_params: FusionParams | dict[str, Any]
    ) -> ModuleResult[Dict[str, BaseModel]]:
        inputs = self.validate_and_fill_default(fusion_params=fusion_params)
        p_alpha, p_neutron = run_alphaneutronsplit(inputs.fusion_params)

        result_payload = {
            "p_alpha": PowerValue(value=p_alpha),
            "p_neutron": PowerValue(value=p_neutron),
        }
        return ModuleResult(data=result_payload)
```

**After (with MultiOutput):**
```python
from simkit.config.schema import MultiOutput

class AlphaNeutronSplitOutput(MultiOutput):
    """Fusion power split into alpha particles and neutrons."""
    p_alpha: PowerValue = Field(description="Alpha particle power [MW]")
    p_neutron: PowerValue = Field(description="Neutron power [MW]")

class AlphaNeutronSplitModule(
    ModuleBase[AlphaNeutronSplitInput, AlphaNeutronSplitOutput]  # ✓ Type-safe!
):
    name = "AlphaNeutronSplit"
    version = "v0.1"

    def validate_and_fill_default(
        self, fusion_params: FusionParams | dict[str, Any]
    ) -> AlphaNeutronSplitInput:
        return AlphaNeutronSplitInput(fusion_params=fusion_params)

    def run(
        self, fusion_params: FusionParams | dict[str, Any]
    ) -> ModuleResult[AlphaNeutronSplitOutput]:
        inputs = self.validate_and_fill_default(fusion_params=fusion_params)
        p_alpha, p_neutron = run_alphaneutronsplit(inputs.fusion_params)

        return ModuleResult(
            data=AlphaNeutronSplitOutput(
                p_alpha=PowerValue(value=p_alpha),
                p_neutron=PowerValue(value=p_neutron),
            )
        )
```

**Registry (auto-introspection now works):**
```python
# Before: Manual registration required
registry = PipelineModuleRegistry()
registry.register("AlphaNeutronSplitModule", ModuleDescriptor(
    module_type="AlphaNeutronSplitModule",
    factory=lambda: AlphaNeutronSplitModule(),
    required_inputs={"fusion_params": FusionParams},
    optional_inputs={},
    outputs={"p_alpha": PowerValue, "p_neutron": PowerValue},
    version="v0.1"
))

# After: Auto-introspection!
from simkit.core.registry_builder import create_registry

registry = create_registry([
    AlphaNeutronSplitModule,  # ✓ Introspection extracts fields from AlphaNeutronSplitOutput
])
```

### Example 2: SynchronousSimModule Migration

**Before:**
```python
class SynchronousSimModule(
    ModuleBase[SynchronousSimInputs, Dict[str, schema.StrictBaseModel]]
):
    def run(self, ...) -> ModuleResult[Dict[str, schema.StrictBaseModel]]:
        bundle = schema.SyncSimOutputs(...)
        result_payload: Dict[str, schema.StrictBaseModel] = {
            "synchronous_sim": bundle,
            "forecasts": bundle.forecasts,
            "guidances": bundle.guidances,
            "telemetry": bundle.telemetry,
        }
        return ModuleResult(result_payload, notes="...")
```

**After:**
```python
class SynchronousSimOutput(MultiOutput):
    """Synchronous simulation outputs."""
    synchronous_sim: schema.SyncSimOutputs
    forecasts: schema.MockForecastSeries
    guidances: schema.SyncGuidanceSeries
    telemetry: schema.SyncTelemetrySeries

class SynchronousSimModule(
    ModuleBase[SynchronousSimInputs, SynchronousSimOutput]  # ✓ Type-safe!
):
    def run(self, ...) -> ModuleResult[SynchronousSimOutput]:
        bundle = schema.SyncSimOutputs(...)

        return ModuleResult(
            data=SynchronousSimOutput(
                synchronous_sim=bundle,
                forecasts=bundle.forecasts,
                guidances=bundle.guidances,
                telemetry=bundle.telemetry,
            ),
            notes="Synchronous simulation completed"
        )
```

---

## Summary

This design addresses all four reported issues:

1. ✅ **StrictBaseModel constraint** → Accept any `BaseModel`
2. ✅ **Multi-output pattern** → Explicit `MultiOutput` marker class
3. ✅ **Introspection limitation** → Extract fields from `MultiOutput`
4. ⏸️ **Primitive wrapper boilerplate** → Phase 2 enhancement

**Key Innovation:** `MultiOutput` marker class
- IS-A `BaseModel` (satisfies TypeVar constraint)
- Introspectable (detect via `issubclass()`)
- Type-safe (static typing works)
- Self-documenting (signals multi-output intent)
- Backward compatible (dict pattern still works)

**Impact:**
- Zero Pyright errors for external users
- `create_registry()` works for all module types
- No `# type: ignore` needed
- Clear, documented patterns
- Generalizable framework ready for external adoption
