# Type System Issue with Multi-Output Pattern

## The Core Problem

The issue is a **type constraint violation** in Python's generic type system. Let me explain step by step.

## What TypeVar Bounds Mean

In `simkit/core/base.py:9-10`, we have:

```python
InputModel = TypeVar("InputModel", bound=BaseModel)
OutputModel = TypeVar("OutputModel", bound=BaseModel)
```

The `bound=BaseModel` constraint means:

> "Whatever type you substitute for `OutputModel` **MUST BE** a subclass of `BaseModel`"

This is similar to saying "OutputModel must inherit from BaseModel."

## The Inheritance Hierarchy

Here's what the type system sees:

```python
# ✅ Valid: BatteryTelemetry8760 IS-A BaseModel
class BatteryTelemetry8760(StrictBaseModel):  # StrictBaseModel inherits from BaseModel
    ...

# ✅ Valid substitution
class SimplePerformanceSimModule(
    ModuleBase[PerformanceInputs, BatteryTelemetry8760]  # BatteryTelemetry8760 is a BaseModel
):
    ...
```

But:

```python
# ❌ Invalid: Dict IS-NOT-A BaseModel
Dict[str, StrictBaseModel]  # Dict is from builtins, NOT a BaseModel subclass!

# ❌ Type violation
class SynchronousSimModule(
    ModuleBase[SynchronousSimInputs, Dict[str, schema.StrictBaseModel]]  # Dict doesn't inherit from BaseModel!
):
    ...
```

## Why This Matters to the Type Checker

The type checker reasons like this:

1. `ModuleBase` is declared as `Generic[InputModel, OutputModel]`
2. `OutputModel` has bound `BaseModel`, meaning it expects a class like:
   ```python
   class SomeOutput(BaseModel):
       field1: str
       field2: int
   ```

3. When you write `ModuleBase[Input, Dict[str, BaseModel]]`:
   - The type checker asks: "Is `Dict[str, BaseModel]` a subclass of `BaseModel`?"
   - Answer: **NO!** `Dict` is a built-in container type, not a Pydantic model
   - It's like trying to say "a dictionary IS-A person" - category error!

## The Runtime vs. Type-Time Disconnect

Here's the subtle point: **this pattern works perfectly at runtime** because:

1. Python doesn't enforce generic bounds at runtime
2. The executor code in `pipeline_executor.py:164-176` handles `Dict` just fine
3. The actual data flow is correct

**But the type system can't verify this** because:

1. Type checkers operate statically (without running the code)
2. They only see the declared constraint: `bound=BaseModel`
3. They see you passing `Dict`, which violates the constraint
4. They raise an error to protect you from potential bugs

## Concrete Example of What Type Checker Fears

Imagine if `ModuleBase` had a method like this:

```python
class ModuleBase(Generic[InputModel, OutputModel]):
    def get_output_fields(self) -> list[str]:
        # Type checker expects OutputModel to be a BaseModel with .model_fields
        return list(self.OutputModel.model_fields.keys())
```

If `OutputModel = Dict[str, StrictBaseModel]`:
- `Dict` doesn't have `.model_fields` attribute!
- This would crash at runtime
- Type checker prevents this by enforcing the bound

Of course, `ModuleBase` doesn't actually have such a method, so it's safe. But the type checker **doesn't know that** - it only knows the constraint.

## Why Dict[str, BaseModel] Violates the Bound

```python
# This is the type hierarchy:
object
  ├─ dict                    # Built-in dictionary type
  │   └─ Dict[str, BaseModel]  # Generic dict with string keys and BaseModel values
  └─ BaseModel               # Pydantic's base class
      └─ StrictBaseModel     # Your strict base
          └─ BatteryTelemetry8760  # Specific model
```

Notice that:
- `BatteryTelemetry8760` inherits from `BaseModel` ✅
- `Dict[str, BaseModel]` does **NOT** inherit from `BaseModel` ❌
- `Dict` and `BaseModel` are siblings in the type tree, not parent-child!

## What Would Satisfy the Type Checker?

If you wanted to make multi-output type-safe, you'd need something like:

```python
class MultiOutputModel(BaseModel):  # Now it IS-A BaseModel!
    """Type-safe wrapper for multiple outputs."""
    channels: Dict[str, BaseModel]

    def __getitem__(self, key: str) -> BaseModel:
        return self.channels[key]

# ✅ This would be type-safe
class SynchronousSimModule(
    ModuleBase[SynchronousSimInputs, MultiOutputModel]
):
    def run(...) -> ModuleResult[MultiOutputModel]:
        return ModuleResult(
            MultiOutputModel(channels={
                "forecasts": ...,
                "guidances": ...,
            })
        )
```

**BUT** this would require changing the executor logic in `pipeline_executor.py` to unwrap `.channels`, which changes the runtime contract.

## Why `# type: ignore` is Pragmatic Here

Given that:

1. The runtime behavior is **correct and tested**
2. `SynchronousSimModule` already uses this pattern successfully
3. Changing the type system would require either:
   - Relaxing the `bound=BaseModel` constraint (affects all modules)
   - Creating wrapper classes (requires executor changes)
4. The violation is **intentional design**, not a bug

Using `# type: ignore[type-arg]` is the right choice because:
- It documents "yes, we know this violates the bound"
- It prevents type checker noise
- It doesn't hide actual bugs (the pattern is tested)
- It's localized to the specific multi-output modules

## Summary

**What's "wrong"**: `Dict[str, BaseModel]` doesn't inherit from `BaseModel`, violating the `TypeVar` bound.

**Why it works anyway**: Python doesn't enforce generic bounds at runtime, and the executor handles dicts correctly.

**Why type checker complains**: It's protecting you from potential attribute errors if `ModuleBase` tried to call `.model_fields` or other `BaseModel` methods on the output.

**Why ignore is OK here**: The multi-output pattern is a deliberate design choice with tested runtime behavior. The type system limitation is acceptable given the benefits of the flexible output routing.
