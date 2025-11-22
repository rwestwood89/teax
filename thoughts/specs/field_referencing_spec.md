# Field Referencing Feature Specification

**Version:** 1.0
**Status:** Implementation Complete
**Author:** System
**Date:** 2025-11-21
**Last Updated:** 2025-11-22
**Completed:** 2025-11-22

---

## Overview

**Field Referencing** allows pipeline modules to bind inputs to **specific fields** of upstream channel values, rather than consuming the entire model. This enables fine-grained data routing without requiring intermediate "unpacker" modules.

### Motivation

Consider a large configuration model with many fields:

```python
class FusionParams(StrictBaseModel):
    p_thermal_electric: float
    p_fusion: float
    blanket_config: BlanketConfig
    coolant_config: CoolantConfig
    plasma_config: PlasmaConfig
    # ... 45 more fields
```

**Current approach:** Pass entire `FusionParams` to every module, even if each only needs 1-2 fields.

**Field referencing approach:** Extract only needed fields at pipeline orchestration level:

```yaml
entry_point:
  inputs:
    fusion_params: FusionParams catf_baseline.json

blanket_thermal:
  inputs:
    blanket_config: BlanketConfig fusion_params.blanket_config  # Extract field

coolant_pump:
  inputs:
    coolant_config: CoolantConfig fusion_params.coolant_config  # Extract different field
```

---

## Syntax Specification

### Grammar

**Input binding with field reference:**
```
<field_name>: <Type> <channel>.<field_path>
```

**Components:**
- `<field_name>`: Module input parameter name (Python identifier)
- `<Type>`: Expected type of the **extracted field** (must be a Pydantic `BaseModel` subclass name)
- `<channel>`: Name of the channel containing the parent model
- `<field_path>`: Dot-separated path to the field within the parent model

**Examples:**
```yaml
# Single-level field extraction
blanket: BlanketConfig fusion_params.blanket_config

# Nested field extraction (Phase 2)
temperature: RootModel[float] fusion_params.blanket_config.temperature

# Primitive wrapped in RootModel
power: RootModel[float] fusion_params.p_thermal_electric
```

### Token Rules

1. **Channel name** (`<channel>`):
   - Must reference an existing channel produced by upstream module or EntryPoint
   - Must not contain dots (`.`)

2. **Field path** (`<field_path>`):
   - **Phase 1:** Single identifier (no nested dots)
     - Valid: `blanket_config`
     - Invalid: `blanket_config.temperature`
   - **Phase 2+:** Dot-separated identifiers for nested access
     - Valid: `blanket_config.temperature`
     - Valid: `coolant.pump.flow_rate`

3. **Type name** (`<Type>`):
   - Must be a valid Pydantic `BaseModel` subclass name
   - Must exist in `simkit.config.schema` module
   - Must match the **actual type** of the extracted field (validated at pipeline validation time)
   - Supports `RootModel[T]` for wrapping primitives (e.g., `RootModel[float]`, `RootModel[str]`)

---

## Semantic Rules

### Rule 1: Field Extraction Happens at Executor Level

Field extraction is **not** a module responsibility. The pipeline executor extracts the field and passes it to the module.

**Module signature:**
```python
class CoolantPumpModule(ModuleBase[CoolantPumpInput, CoolantPumpOutput]):
    def run(self, coolant_config: CoolantConfig, **kwargs):
        # Receives ONLY CoolantConfig, not entire FusionParams
        ...
```

**Pipeline YAML:**
```yaml
coolant_pump:
  inputs:
    coolant_config: CoolantConfig fusion_params.coolant_config
```

The executor extracts `fusion_params.coolant_config` before calling `run()`.

### Rule 2: Field Path Must Exist and Be Accessible

At **pipeline validation time**, the validator must verify:
1. The parent channel exists and has a known type
2. The field path exists in the parent type's Pydantic schema
3. The field is **not private** (doesn't start with `_`)
4. The field type matches the declared binding type

### Rule 3: Type Compatibility

The **extracted field's type** must **exactly match** the declared type in the binding.

**Valid:**
```python
# Model definition
class FusionParams(StrictBaseModel):
    blanket_config: BlanketConfig  # Type is BlanketConfig

# YAML binding
blanket: BlanketConfig fusion_params.blanket_config  # ✅ Matches
```

**Invalid:**
```python
# Model definition
class FusionParams(StrictBaseModel):
    blanket_config: BlanketConfig

# YAML binding
blanket: dict fusion_params.blanket_config  # ❌ Type mismatch (BlanketConfig ≠ dict)
```

### Rule 4: Optional Fields

If the field path includes an `Optional` field, validation passes **but runtime may fail** if the value is `None`.

**Model:**
```python
class FusionParams(StrictBaseModel):
    optional_config: BlanketConfig | None = None
```

**YAML:**
```yaml
blanket: BlanketConfig fusion_params.optional_config  # ✅ Validates
```

**Runtime behavior:**
- If `fusion_params.optional_config` is `None`, executor raises `PipelineExecutionError`:
  ```
  Field 'optional_config' on channel 'fusion_params' is None (expected BlanketConfig)
  ```

**Design decision:** We **validate** Optional fields at pipeline validation time, but **fail at runtime** if the value is `None`. This is consistent with Python's typing system (Optional indicates possibility, not guarantee).

### Rule 5: No Field Extraction from EntryPoint

EntryPoint bindings **cannot** use field references (they load entire files).

**Invalid:**
```yaml
entry_point:
  inputs:
    blanket: BlanketConfig fusion_params.blanket_config  # ❌ EntryPoint has no upstream channels
```

**Valid:**
```yaml
entry_point:
  inputs:
    fusion_params: FusionParams catf_baseline.json  # ✅ Load entire file
```

### Rule 6: No Field Extraction in ExitPoint

ExitPoint bindings reference channels, not fields. If you need to persist a field, route it through an intermediate channel.

**Workaround (if needed):**
```yaml
some_module:
  outputs:
    blanket_config: BlanketConfig blanket_channel

exit_point:
  outputs:
    blanket_config: BlanketConfig blanket_config.json
```

---

## Validation Rules

### Validation-Time Checks

The `PipelineValidator` must enforce:

#### 1. Channel Existence
```python
# Pseudo-code
if binding.field_path is not None:
    if binding.channel_name not in provided_channels:
        raise PipelineValidationError(
            f"Channel '{binding.channel_name}' not found "
            f"(required for field reference '{binding.channel_name}.{binding.field_path}')"
        )
```

#### 2. Field Existence (Phase 1: Single-Level)
```python
# Get the type of the parent channel
parent_type = get_channel_type(binding.channel_name)  # e.g., FusionParams

# Check field exists
if binding.field_path not in parent_type.model_fields:
    raise PipelineValidationError(
        f"Type '{parent_type.__name__}' has no field '{binding.field_path}'"
    )
```

#### 3. Field Type Compatibility
```python
# Get actual field type from Pydantic model
field_info = parent_type.model_fields[binding.field_path]
actual_type = field_info.annotation

# Resolve expected type from binding
expected_type = _resolve_schema_type(binding.type_name)

# Check compatibility
if not _types_compatible(actual_type, expected_type):
    raise PipelineValidationError(
        f"Type mismatch for field '{binding.channel_name}.{binding.field_path}': "
        f"expected {binding.type_name}, but field has type {actual_type.__name__}"
    )
```

**Type compatibility rules:**
- Exact match: `actual_type == expected_type` ✅
- Optional unwrapping: `actual_type = Optional[BlanketConfig]`, `expected_type = BlanketConfig` ✅
  - Validation passes, runtime checks for `None`
- Subclass: `actual_type` is subclass of `expected_type` ❌ (reject for Phase 1, revisit later)

#### 4. No Private Fields
```python
if binding.field_path.startswith("_"):
    raise PipelineValidationError(
        f"Cannot extract private field '{binding.field_path}' from channel '{binding.channel_name}'"
    )
```

#### 5. No Computed Fields (Phase 1)
Pydantic `@computed_field` properties are **not accessible** via field references in Phase 1.

```python
# In model
class FusionParams(StrictBaseModel):
    p_thermal: float

    @computed_field
    @property
    def p_electric(self) -> float:
        return self.p_thermal * 0.4

# In YAML
power: RootModel[float] fusion_params.p_electric  # ❌ Computed field not supported (Phase 1)
```

**Validation:** Check that field is in `model_fields`, not `computed_fields`.

---

## Implementation Requirements

### 1. Data Model Changes

**File:** `simkit/config/pipeline_schema.py`

**Modify `PipelineChannelBinding`:**
```python
class PipelineChannelBinding(StrictBaseModel):
    """Represents either a provided channel or a dependency on one."""

    type_name: str | None
    channel_name: str
    field_path: str | None = None  # NEW: Field path for extraction (e.g., "blanket_config")
    source: ChannelSource
    artifact_path: Path | None = None
    destination_filename: str | None = None

    @property
    def is_field_reference(self) -> bool:
        """True if this binding extracts a field from a channel."""
        return self.field_path is not None
```

### 2. Parsing Changes

**File:** `simkit/config/pipeline_schema.py`

**Modify `_parse_inputs()` function (line 234-262):**

```python
def _parse_inputs(raw_inputs: Dict[str, Any]) -> Dict[str, PipelineChannelBinding]:
    bindings: Dict[str, PipelineChannelBinding] = {}
    for field, raw_value in raw_inputs.items():
        if not isinstance(raw_value, str):
            raise ValueError(
                f"Input '{field}' must be a string formatted as '<Type> <channel>' or 'None -> <channel>'"
            )
        value = raw_value.strip()

        if value.lower().startswith("none"):
            channel_name = _parse_default_channel(value, field)
            binding = PipelineChannelBinding(
                type_name=None,
                channel_name=channel_name,
                source=ChannelSource.DEFAULT,
            )
        else:
            parts = value.split(None, 1)
            if len(parts) != 2:
                raise ValueError(f"Input '{field}' must be formatted as '<Type> <channel>'")

            type_name, channel_ref = parts

            # NEW: Parse field reference
            if "." in channel_ref:
                channel_name, field_path = channel_ref.split(".", 1)

                # Phase 1: Only allow single-level field paths
                if "." in field_path:
                    raise ValueError(
                        f"Input '{field}': Nested field paths not supported (got '{channel_ref}'). "
                        f"Use single-level fields only (e.g., 'channel.field')."
                    )

                binding = PipelineChannelBinding(
                    type_name=type_name.strip(),
                    channel_name=channel_name.strip(),
                    field_path=field_path.strip(),
                    source=ChannelSource.MODULE,
                )
            else:
                # No field reference - standard channel binding
                binding = PipelineChannelBinding(
                    type_name=type_name.strip(),
                    channel_name=channel_ref.strip(),
                    source=ChannelSource.MODULE,
                )

        bindings[field] = binding
    return bindings
```

### 3. Validation Changes

**File:** `simkit/core/pipeline_validator.py`

**Add new validation function:**

```python
def validate_field_reference(
    binding: PipelineChannelBinding,
    parent_channel_type_name: str,
    module_key: str,
    field_name: str,
) -> None:
    """
    Validate that a field reference binding is well-formed.

    Args:
        binding: The binding with field_path set
        parent_channel_type_name: The type name of the parent channel
        module_key: Module key for error messages
        field_name: Input field name for error messages

    Raises:
        PipelineValidationError: If validation fails
    """
    from simkit.config import schema

    # Resolve parent type
    try:
        parent_type = getattr(schema, parent_channel_type_name)
    except AttributeError:
        raise PipelineValidationError(
            f"Unknown schema type '{parent_channel_type_name}' for channel '{binding.channel_name}'",
            module=module_key,
        )

    # Check field exists in parent type
    if binding.field_path not in parent_type.model_fields:
        available_fields = ", ".join(sorted(parent_type.model_fields.keys()))
        raise PipelineValidationError(
            f"Module '{module_key}' input '{field_name}': "
            f"Type '{parent_channel_type_name}' has no field '{binding.field_path}'. "
            f"Available fields: {available_fields}",
            module=module_key,
            details={
                "channel": binding.channel_name,
                "parent_type": parent_channel_type_name,
                "field_path": binding.field_path,
                "available_fields": list(parent_type.model_fields.keys()),
            },
        )

    # Check field is not private
    if binding.field_path.startswith("_"):
        raise PipelineValidationError(
            f"Module '{module_key}' input '{field_name}': "
            f"Cannot extract private field '{binding.field_path}' from channel '{binding.channel_name}'",
            module=module_key,
        )

    # Get actual field type
    field_info = parent_type.model_fields[binding.field_path]
    actual_type_annotation = field_info.annotation

    # Unwrap Optional if present
    actual_type = _unwrap_optional(actual_type_annotation)
    is_optional = actual_type != actual_type_annotation

    # Resolve expected type from binding
    try:
        expected_type = getattr(schema, binding.type_name)
    except AttributeError:
        raise PipelineValidationError(
            f"Module '{module_key}' input '{field_name}': "
            f"Unknown type '{binding.type_name}'",
            module=module_key,
        )

    # Check type compatibility
    if actual_type != expected_type:
        raise PipelineValidationError(
            f"Module '{module_key}' input '{field_name}': "
            f"Type mismatch for field '{binding.channel_name}.{binding.field_path}'. "
            f"Expected type '{binding.type_name}', but field has type '{actual_type.__name__}'",
            module=module_key,
            details={
                "expected_type": binding.type_name,
                "actual_type": actual_type.__name__,
                "is_optional": is_optional,
            },
        )

    # Phase 1: Disallow computed fields
    if binding.field_path in parent_type.model_computed_fields:
        raise PipelineValidationError(
            f"Module '{module_key}' input '{field_name}': "
            f"Cannot extract computed field '{binding.field_path}' (not supported in Phase 1)",
            module=module_key,
        )


def _unwrap_optional(type_annotation) -> type:
    """
    Unwrap Optional[T] to T. Returns original type if not Optional.

    Handles:
    - Optional[BlanketConfig] → BlanketConfig
    - BlanketConfig | None → BlanketConfig
    - BlanketConfig → BlanketConfig
    """
    import types
    import typing

    # Check for Union types (including Optional which is Union[T, None])
    if hasattr(type_annotation, "__origin__") and type_annotation.__origin__ is typing.Union:
        args = type_annotation.__args__
        # Remove None from union args
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1:
            return non_none_args[0]

    return type_annotation
```

**Integrate into existing validation flow:**

In the main `validate()` function, after checking channel existence:

```python
def validate(spec: PipelineSpecification, registry: PipelineModuleRegistry) -> None:
    # ... existing validation logic ...

    # NEW: Validate field references
    for module_key, module_spec in spec.modules.items():
        if module_spec.is_entry or module_spec.is_exit:
            continue

        for field_name, binding in module_spec.inputs.items():
            if binding.is_field_reference:
                # Get parent channel's type
                parent_channel_type = _get_channel_type(binding.channel_name, spec, registry)

                # Validate field reference
                validate_field_reference(
                    binding=binding,
                    parent_channel_type_name=parent_channel_type,
                    module_key=module_key,
                    field_name=field_name,
                )
```

### 4. Execution Changes

**File:** `simkit/core/pipeline_executor.py`

**Modify `_resolve_input()` function (line 290-293):**

```python
def _resolve_input(binding: PipelineChannelBinding, context: PipelineExecutionContext) -> Any:
    """
    Resolve an input binding to its actual value.

    Handles:
    - Default bindings (return None)
    - Standard channel bindings (return channel value)
    - Field reference bindings (extract field from channel value)
    """
    if binding.source is ChannelSource.DEFAULT:
        return None

    value = context.get_channel(binding.channel_name)

    # NEW: Extract field if this is a field reference
    if binding.field_path:
        try:
            extracted = getattr(value, binding.field_path)
        except AttributeError:
            # Defensive check (should be caught by validator)
            raise PipelineExecutionError(
                f"Channel '{binding.channel_name}' has no field '{binding.field_path}' "
                f"(type: {type(value).__name__})"
            )

        # Check for None on Optional fields
        if extracted is None:
            raise PipelineExecutionError(
                f"Field '{binding.field_path}' on channel '{binding.channel_name}' is None "
                f"(expected {binding.type_name})"
            )

        return extracted

    return value
```

### 5. Error Handling

**New exception class** (if not exists):

```python
class PipelineExecutionError(Exception):
    """Raised when pipeline execution fails at runtime."""
    pass
```

**Error messages must be actionable:**

❌ **Bad:** `Field 'blanket_config' not found`

✅ **Good:**
```
Module 'blanket_thermal' input 'blanket': Type 'FusionParams' has no field 'blanket_config'.
Available fields: p_thermal_electric, p_fusion, blanket_configuration, coolant_config, plasma_config
```

---

## Examples

### Example 1: Extract Sub-Model

**Models:**
```python
class BlanketConfig(StrictBaseModel):
    material: str
    thickness_m: float
    temperature_k: float

class FusionParams(StrictBaseModel):
    p_fusion: float
    blanket_config: BlanketConfig
    coolant_config: CoolantConfig
```

**YAML:**
```yaml
entry_point:
  inputs:
    fusion_params: FusionParams catf_baseline.json

blanket_thermal:
  module_type: BlanketThermalModule
  inputs:
    blanket_config: BlanketConfig fusion_params.blanket_config  # Extract field
  outputs:
    thermal_output: ThermalOutput thermal_data
```

**Execution:**
1. EntryPoint loads `catf_baseline.json` → `FusionParams` instance
2. Executor extracts `fusion_params.blanket_config` → `BlanketConfig` instance
3. `BlanketThermalModule.run(blanket_config=...)` receives only `BlanketConfig`

### Example 2: Extract Primitive (RootModel)

**Models:**
```python
from pydantic import RootModel

class FusionParams(StrictBaseModel):
    p_thermal_electric: float

# In schema.py, add:
class FloatValue(RootModel[float]):
    """Wrapper for float primitives in channels."""
    pass
```

**YAML:**
```yaml
entry_point:
  inputs:
    fusion_params: FusionParams catf_baseline.json

power_module:
  inputs:
    p_thermal: FloatValue fusion_params.p_thermal_electric  # Extract float
```

**Note:** `FloatValue` must be defined in `schema.py` as a `RootModel[float]`.

### Example 3: Multiple Modules, Different Fields

**YAML:**
```yaml
entry_point:
  inputs:
    fusion_params: FusionParams catf_baseline.json

blanket_thermal:
  inputs:
    blanket_config: BlanketConfig fusion_params.blanket_config

coolant_pump:
  inputs:
    coolant_config: CoolantConfig fusion_params.coolant_config

plasma_controller:
  inputs:
    plasma_config: PlasmaConfig fusion_params.plasma_config
```

Each module receives only its relevant sub-config.

---

## Edge Cases

### Edge Case 1: Optional Fields

**Model:**
```python
class FusionParams(StrictBaseModel):
    optional_blanket: BlanketConfig | None = None
```

**YAML:**
```yaml
blanket_thermal:
  inputs:
    blanket_config: BlanketConfig fusion_params.optional_blanket
```

**Behavior:**
- ✅ **Validation passes** (field exists, type matches)
- ⚠️ **Runtime fails** if `fusion_params.optional_blanket` is `None`:
  ```
  PipelineExecutionError: Field 'optional_blanket' on channel 'fusion_params' is None (expected BlanketConfig)
  ```

**Rationale:** We can't know at validation time if the value will be `None`. This matches Python's Optional semantics.

### Edge Case 2: Field Name Collision

**Model:**
```python
class FusionParams(StrictBaseModel):
    config: BlanketConfig  # Field named "config"
```

**YAML:**
```yaml
# Two modules, same source field, different binding names
module1:
  inputs:
    blanket: BlanketConfig fusion_params.config

module2:
  inputs:
    my_config: BlanketConfig fusion_params.config
```

**Behavior:** ✅ **Valid** - Different binding names, same source field.

### Edge Case 3: Nested Models (Phase 2)

**Model:**
```python
class CoolantConfig(StrictBaseModel):
    pump: PumpConfig

class PumpConfig(StrictBaseModel):
    flow_rate: float
```

**YAML (Phase 2):**
```yaml
# Phase 2: Multi-level field path
flow_module:
  inputs:
    flow_rate: RootModel[float] fusion_params.coolant_config.pump.flow_rate
```

**Phase 1:** ❌ Raises validation error (nested paths not supported)

### Edge Case 4: Channel and Field Same Name

**Model:**
```python
class FusionParams(StrictBaseModel):
    fusion_params: BlanketConfig  # Field name = channel name (confusing but legal)
```

**YAML:**
```yaml
module1:
  inputs:
    blanket: BlanketConfig fusion_params.fusion_params  # channel.field
```

**Behavior:** ✅ **Valid** - Channel is `fusion_params`, field is `fusion_params`.

### Edge Case 5: Field Type is Also a Channel

**Channels:**
- `fusion_params` → `FusionParams`
- `standalone_blanket` → `BlanketConfig`

**Model:**
```python
class FusionParams(StrictBaseModel):
    blanket_config: BlanketConfig
```

**YAML:**
```yaml
# Both bindings produce same type, different sources
module1:
  inputs:
    blanket: BlanketConfig fusion_params.blanket_config  # From field

module2:
  inputs:
    blanket: BlanketConfig standalone_blanket  # From channel
```

**Behavior:** ✅ **Valid** - Different sources, same type.

---

## Testing Strategy

### Unit Tests

**File:** `simkit/tests/core/test_pipeline_schema_field_reference.py`

```python
def test_parse_field_reference_single_level():
    """Parse 'Type channel.field' correctly."""
    raw = {"blanket": "BlanketConfig fusion_params.blanket_config"}
    bindings = _parse_inputs(raw)

    assert bindings["blanket"].channel_name == "fusion_params"
    assert bindings["blanket"].field_path == "blanket_config"
    assert bindings["blanket"].type_name == "BlanketConfig"
    assert bindings["blanket"].is_field_reference is True


def test_parse_field_reference_rejects_nested_phase1():
    """Reject nested field paths in Phase 1."""
    raw = {"temp": "RootModel[float] fusion_params.blanket.temperature"}

    with pytest.raises(ValueError, match="Nested field paths not supported"):
        _parse_inputs(raw)


def test_parse_standard_binding_no_dot():
    """Ensure 'Type channel' still works (no field path)."""
    raw = {"geo": "Geography geo"}
    bindings = _parse_inputs(raw)

    assert bindings["geo"].channel_name == "geo"
    assert bindings["geo"].field_path is None
    assert bindings["geo"].is_field_reference is False
```

**File:** `simkit/tests/core/test_pipeline_validator_field_reference.py`

```python
def test_validate_field_exists():
    """Validation passes when field exists."""
    # Setup: FusionParams with blanket_config field
    # Call: validate_field_reference(...)
    # Assert: No exception


def test_validate_field_not_exists():
    """Validation fails when field doesn't exist."""
    # Setup: FusionParams without 'missing_field'
    # Call: validate_field_reference(binding with field_path='missing_field')
    # Assert: Raises PipelineValidationError with helpful message


def test_validate_type_mismatch():
    """Validation fails when field type doesn't match binding."""
    # Setup: FusionParams.blanket_config is BlanketConfig
    # Call: validate_field_reference(binding with type_name='CoolantConfig')
    # Assert: Raises PipelineValidationError


def test_validate_optional_field_allowed():
    """Validation passes for Optional fields (fails at runtime if None)."""
    # Setup: FusionParams.optional_blanket: BlanketConfig | None
    # Call: validate_field_reference(binding with type_name='BlanketConfig')
    # Assert: No exception (validation passes)


def test_validate_private_field_rejected():
    """Validation fails for private fields."""
    # Setup: FusionParams._internal_field
    # Call: validate_field_reference(binding with field_path='_internal_field')
    # Assert: Raises PipelineValidationError
```

**File:** `simkit/tests/core/test_pipeline_executor_field_reference.py`

```python
def test_execute_field_reference_extraction():
    """Executor extracts field and passes to module."""
    # Setup: Pipeline with field reference
    # Execute: execute_pipeline(spec)
    # Assert: Module receives extracted field, not full model


def test_execute_optional_field_none_raises():
    """Runtime error when Optional field is None."""
    # Setup: FusionParams with optional_blanket=None
    # Execute: Pipeline with field reference to optional_blanket
    # Assert: Raises PipelineExecutionError


def test_execute_multiple_field_references():
    """Multiple modules extract different fields from same channel."""
    # Setup: fusion_params channel with 3 sub-configs
    # Execute: 3 modules each extract different sub-config
    # Assert: Each module receives only its field
```

### Integration Tests

**File:** `simkit/tests/test_pipeline_field_reference_e2e.py`

```python
def test_e2e_fusion_params_field_extraction(tmp_path):
    """End-to-end test: Load FusionParams, extract fields, run modules."""
    # 1. Create test input JSON with FusionParams
    # 2. Create pipeline YAML with field references
    # 3. Execute pipeline
    # 4. Assert outputs are correct
    # 5. Verify modules received only extracted fields (via logging/instrumentation)
```

---

## Phase 1 Deliverables

**Must Have:**
1. ✅ Parse single-level field references: `channel.field`
2. ✅ Validate field existence at pipeline validation time
3. ✅ Validate type compatibility (exact match)
4. ✅ Extract fields at runtime in `_resolve_input()`
5. ✅ Support `RootModel[T]` for primitives
6. ✅ Error messages with available fields listed
7. ✅ Unit tests for parsing, validation, execution
8. ✅ Integration test (E2E)
9. ✅ Update `TEAX_README.md` with field reference syntax
10. ✅ Update `CLAUDE.md` with implementation notes

**Out of Scope (Phase 1):**
- ❌ Nested field paths (`channel.field.subfield`)
- ❌ Computed fields
- ❌ Field references in EntryPoint/ExitPoint
- ❌ Subclass polymorphism (must be exact type match)

**Future (Phase 2+):**
- Nested field paths
- Computed field support
- Type coercion (e.g., `int` → `float`)
- Wildcard field extraction (e.g., `fusion_params.*` → expand all fields)

---

## Open Questions

1. **Should we allow field references in `outputs`?**
   - Example: `outputs: { blanket: BlanketConfig result.blanket_config }`
   - Pros: Symmetry with inputs
   - Cons: Modules should control their own output structure
   - **Decision:** No (Phase 1). Outputs are module-controlled.

2. **Should we support `List` field extraction?**
   - Example: `first_item: ItemType channel.item_list[0]`
   - **Decision:** No (Phase 1). Use a dedicated "indexer" module if needed.

3. **Should we support field references in default bindings?**
   - Example: `blanket: BlanketConfig None -> fusion_params_default.blanket_config`
   - **Decision:** No (Phase 1). Defaults are for modules that provide default values, not for extracting from other channels.

---

## Appendix: Type Compatibility Rules

**Phase 1: Exact Match Only**

| Field Type | Binding Type | Valid? |
|------------|--------------|--------|
| `BlanketConfig` | `BlanketConfig` | ✅ |
| `BlanketConfig \| None` | `BlanketConfig` | ✅ (validates, runtime checks for None) |
| `float` | `RootModel[float]` | ✅ |
| `BlanketConfig` | `CoolantConfig` | ❌ Type mismatch |
| `SubBlanket` (subclass) | `BlanketConfig` | ❌ No subclass polymorphism (Phase 1) |
| `BlanketConfig` | `BaseModel` | ❌ No base class polymorphism (Phase 1) |

**Phase 2+: Consider Subclass Polymorphism**

---

## Appendix: RootModel Pattern

For primitives, use Pydantic's `RootModel`:

```python
# In simkit/config/schema.py
from pydantic import RootModel

class FloatValue(RootModel[float]):
    """Wrapper for float values in channels."""
    pass

class IntValue(RootModel[int]):
    """Wrapper for int values in channels."""
    pass

class StrValue(RootModel[str]):
    """Wrapper for string values in channels."""
    pass
```

**YAML usage:**
```yaml
power_module:
  inputs:
    p_thermal: FloatValue fusion_params.p_thermal_electric
```

**Module receives:**
```python
def run(self, p_thermal: FloatValue, **kwargs):
    actual_float = p_thermal.root  # Access wrapped value
    # Or: FloatValue auto-coerces in many contexts
```

**Alternative (if RootModel is too verbose):** Consider adding auto-wrapping in the executor for common primitives.

---

**End of Specification**
