# TypeVar Options for Multi-Output Pattern

## The Goal

Allow `OutputModel` to be either:
1. A `BaseModel` subclass (single output)
2. `Dict[str, BaseModel]` (multi output)

## Option 1: Union Bound (Doesn't Work)

You might think to try:

```python
from typing import TypeVar, Union, Dict
from pydantic import BaseModel

OutputModel = TypeVar("OutputModel", bound=Union[BaseModel, Dict[str, BaseModel]])
```

**Problem**: This doesn't work because `bound` expects a **class**, not a union type. You'll get:

```
TypeError: Constraints cannot be combined with bound=...
```

## Option 2: Constrained TypeVar (Close, but Limited)

```python
OutputModel = TypeVar("OutputModel", BaseModel, Dict[str, BaseModel])
```

**What this means**: `OutputModel` can be **exactly** `BaseModel` or **exactly** `Dict[str, BaseModel]`, nothing else.

**Problem**: This is too restrictive! You want `BatteryTelemetry8760` (a subclass of BaseModel), not just `BaseModel` itself. Constrained TypeVars don't allow subclasses.

**Also**: `Dict[str, BaseModel]` is a generic alias, not a concrete type, which makes this even messier.

## Option 3: Protocol (Most Flexible)

Use structural typing instead of nominal typing:

```python
from typing import Protocol, TypeVar, runtime_checkable
from pydantic import BaseModel

@runtime_checkable
class ModuleOutput(Protocol):
    """Structural type for module outputs."""
    pass  # No required methods - just a marker

OutputModel = TypeVar("OutputModel", bound=ModuleOutput)
```

Then make both patterns satisfy the protocol:

```python
# Option 3a: Make BaseModel satisfy it (it already does - empty protocol)
# BaseModel is already compatible

# Option 3b: Runtime check in executor
if isinstance(data, BaseModel):
    # Single output
elif isinstance(data, dict):
    # Multi output
```

**Problem**: This is too permissive - it accepts anything. You lose type safety.

## Option 4: Union in Generic (This Works!)

Instead of constraining the `TypeVar`, use it **unconstrained** and express the union at the usage site:

```python
from typing import TypeVar, Union, Dict, Mapping
from pydantic import BaseModel

# Unconstrained TypeVar
OutputModel = TypeVar("OutputModel")

class ModuleBase(Generic[InputModel, OutputModel]):
    def run(self, *args, **kwargs) -> ModuleResult[OutputModel]:
        raise NotImplementedError
```

Then at usage:

```python
# Single output
class SimpleModule(ModuleBase[SimpleInput, SimpleOutput]):
    ...

# Multi output
class MultiModule(ModuleBase[MultiInput, Dict[str, BaseModel]]):
    ...
```

**Pros**:
- ✅ No type errors
- ✅ Both patterns work
- ✅ Type checker understands both cases

**Cons**:
- ❌ Loses constraint that outputs should be BaseModel-related
- ❌ Could accidentally allow `ModuleBase[Input, str]` or other nonsense
- ❌ Less self-documenting

## Option 5: Union Alias (Clearest Intent)

Define an explicit union type alias:

```python
from typing import TypeVar, Union, Dict, TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    # For type checkers, define the union
    ModuleOutputType = Union[BaseModel, Dict[str, BaseModel]]
    OutputModel = TypeVar("OutputModel", bound=ModuleOutputType)
else:
    # At runtime, just use BaseModel bound to avoid issues
    OutputModel = TypeVar("OutputModel", bound=BaseModel)
```

**Problem**: `bound` still doesn't accept unions even in `TYPE_CHECKING` block. This gives the same error as Option 1.

## Option 6: Separate TypeVars (Most Explicit)

Create two different base classes:

```python
SingleOutputModel = TypeVar("SingleOutputModel", bound=BaseModel)
MultiOutputModel = TypeVar("MultiOutputModel", bound=Mapping)

class SingleOutputModuleBase(Generic[InputModel, SingleOutputModel]):
    def run(self, *args, **kwargs) -> ModuleResult[SingleOutputModel]:
        raise NotImplementedError

class MultiOutputModuleBase(Generic[InputModel, MultiOutputModel]):
    def run(self, *args, **kwargs) -> ModuleResult[MultiOutputModel]:
        raise NotImplementedError
```

**Pros**:
- ✅ Type safe
- ✅ Explicit about single vs multi output
- ✅ Each has appropriate constraints

**Cons**:
- ❌ Code duplication
- ❌ Two base classes to maintain
- ❌ Breaks existing code that expects single `ModuleBase`

## Option 7: ParamSpec + Overload (Advanced)

Use `@overload` to declare both signatures:

```python
from typing import overload, TypeVar, Dict, Mapping
from pydantic import BaseModel

SingleOutput = TypeVar("SingleOutput", bound=BaseModel)
MultiOutput = TypeVar("MultiOutput", bound=Mapping[str, BaseModel])

class ModuleBase(Generic[InputModel, OutputModel]):
    @overload
    def __init__(self: "ModuleBase[InputModel, SingleOutput]") -> None: ...

    @overload
    def __init__(self: "ModuleBase[InputModel, Dict[str, BaseModel]]") -> None: ...

    def __init__(self) -> None:
        pass
```

**Problem**: This is complex, hard to maintain, and doesn't actually solve the TypeVar bound issue.

## Option 8: Keep Bound + Use type: ignore (Pragmatic Winner)

```python
# In base.py - keep as-is
OutputModel = TypeVar("OutputModel", bound=BaseModel)

# In single-output modules - no issues
class SimpleModule(ModuleBase[Input, BatteryTelemetry8760]):
    ...

# In multi-output modules - explicit ignore
class MultiModule(
    ModuleBase[Input, Dict[str, schema.StrictBaseModel]]  # type: ignore[type-arg]
):
    """Multi-output module. See: thoughts/research/type_system_explanation.md"""
    ...
```

**Pros**:
- ✅ Minimal code change
- ✅ Documents intentionality with comment
- ✅ Doesn't weaken single-output type safety
- ✅ Localized to just multi-output modules (rare)

**Cons**:
- ❌ Type checker can't verify multi-output correctness
- ❌ Slightly inelegant

## My Recommendation

**Option 8** (current approach with `# type: ignore`) is the best choice because:

1. **Multi-output is rare**: Only `SynchronousSimModule` uses it in the entire codebase
2. **Single-output benefits from strict typing**: Most modules get full type safety
3. **Runtime testing covers the gap**: The multi-output pattern is tested in `test_pipeline.py`
4. **Simple to understand**: No complex type gymnastics
5. **Localized exceptions**: Only affects the ~2 modules that need multiple outputs

## Alternative Worth Considering: Option 4 (Unconstrained TypeVar)

If you expect multi-output to become common, **Option 4** is worth it:

```python
# In base.py
InputModel = TypeVar("InputModel", bound=BaseModel)
OutputModel = TypeVar("OutputModel")  # Remove bound constraint

class ModuleBase(Generic[InputModel, OutputModel]):
    ...
```

**Trade-off analysis**:
- Lose: Type constraint that outputs should be BaseModel (minor - convention enforces this)
- Gain: No type errors on multi-output modules
- Risk: Someone could write `ModuleBase[Input, int]` (but would fail at runtime anyway)

The constraint `bound=BaseModel` provides **documentation value** more than runtime safety, since:
- Python doesn't enforce TypeVar bounds at runtime
- The executor does runtime type checking (`isinstance(data, Mapping)`)
- Tests would catch incorrect output types

## Bottom Line

Given the current codebase:
- **Keep Option 8** (type: ignore) for now
- **Consider Option 4** (remove bound) if you add 2+ more multi-output modules
- **Avoid Options 1-3, 5-7** (too complex or don't work)

The type system wasn't designed for this "two valid output modes" pattern. The pragmatic choice is to acknowledge the limitation rather than contort the code to satisfy the type checker.
