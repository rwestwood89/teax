# Field Referencing Implementation Plan

**Document Type:** Implementation Plan
**Version:** v1.0
**Status:** Ready for Implementation
**Owner:** Reid Westwood
**Last Updated:** 2025-11-22
**Related Docs:**
- Spec: `thoughts/specs/field_referencing_spec.md`
- Design: `thoughts/specs/field_referencing/2025-11-22-design.md`

## Overview

This plan implements the Field Referencing feature, which allows pipeline modules to bind inputs to specific fields of upstream channel values using the syntax `Type channel.field`. This enables fine-grained data routing without intermediate unpacker modules.

**Source Documents:**
- **Spec:** `thoughts/specs/field_referencing_spec.md`
- **Design:** `thoughts/specs/field_referencing/2025-11-22-design.md`

## Implementation Strategy

**Phased Approach:**
1. **Phase 1:** Extend data model and implement YAML parsing for field references
2. **Phase 2:** Build validation infrastructure with channel type tracking
3. **Phase 3:** Implement runtime extraction and comprehensive testing

**Key Decisions:**
- Parser splits on first dot only to enable future nested path support
- Channel type map built once during validation to avoid repeated lookups
- Optional field validation passes but runtime fails if None (Python Optional semantics)
- Exact type match only in Phase 1 (no subclass polymorphism)

---

## Phase 1: Data Model & YAML Parsing

### Overview
Extends `PipelineChannelBinding` to store field paths and modifies `_parse_inputs()` to parse `channel.field` syntax. After this phase, YAML with field references can be parsed into structured bindings.

### Test Stencil
```python
# Test for Phase 1 - parsing field reference syntax
def test_parse_field_reference_single_level():
    raw = {"blanket": "BlanketConfig fusion_params.blanket_config"}
    bindings = _parse_inputs(raw)

    assert bindings["blanket"].channel_name == "fusion_params"
    assert bindings["blanket"].field_path == "blanket_config"
    assert bindings["blanket"].type_name == "BlanketConfig"
    assert bindings["blanket"].is_field_reference is True
```

### Changes Required

#### 1. Extend PipelineChannelBinding Data Model
**File:** `simkit/config/pipeline_schema.py`
**Location:** Lines 22-34

**Changes:**
- [x] Add `field_path: str | None = None` field to `PipelineChannelBinding` class
- [x] Add `is_field_reference` property that returns `self.field_path is not None`
- [x] Verify Pydantic validation still works with new optional field

**Code to add:**
```python
class PipelineChannelBinding(StrictBaseModel):
    """Represents either a provided channel or a dependency on one."""

    type_name: str | None
    channel_name: str
    field_path: str | None = None  # NEW: e.g., "blanket_config" for single-level extraction
    source: ChannelSource
    artifact_path: Path | None = None
    destination_filename: str | None = None

    @property
    def is_default(self) -> bool:
        return self.source is ChannelSource.DEFAULT

    @property
    def is_field_reference(self) -> bool:  # NEW
        """True if this binding extracts a field from a channel."""
        return self.field_path is not None
```

#### 2. Modify YAML Input Parser
**File:** `simkit/config/pipeline_schema.py`
**Location:** Lines 234-262 (`_parse_inputs` function)

**Changes:**
- [x] After splitting on whitespace, check if `channel_ref` contains a dot
- [x] If dot found, split `channel_ref` on first dot into `channel_name` and `field_path`
- [x] Validate `field_path` is not empty (reject `"Type channel."`)
- [x] Validate `field_path` contains no additional dots (reject nested paths in Phase 1)
- [x] Create binding with `field_path` populated when dot detected
- [x] Preserve existing behavior for bindings without dots

**Code modification:**
```python
def _parse_inputs(raw_inputs: Dict[str, Any]) -> Dict[str, PipelineChannelBinding]:
    """Parse input bindings from YAML, supporting field references like 'Type channel.field'."""
    bindings: Dict[str, PipelineChannelBinding] = {}
    for field, raw_value in raw_inputs.items():
        if not isinstance(raw_value, str):
            raise ValueError(
                f"Input '{field}' must be a string formatted as '<Type> <channel>' or 'None -> <channel>'"
            )
        value = raw_value.strip()

        # Handle default bindings (UNCHANGED)
        if value.lower().startswith("none"):
            channel_name = _parse_default_channel(value, field)
            binding = PipelineChannelBinding(
                type_name=None,
                channel_name=channel_name,
                source=ChannelSource.DEFAULT,
            )
        else:
            # Split on whitespace: "<Type> <channel_ref>"
            parts = value.split(None, 1)
            if len(parts) != 2:
                raise ValueError(
                    f"Input '{field}' must be formatted as '<Type> <channel>' or '<Type> <channel.field>'"
                )

            type_name, channel_ref = parts

            # NEW: Check for field reference (contains dot)
            if "." in channel_ref:
                # Split on first dot only
                dot_index = channel_ref.index(".")
                channel_name = channel_ref[:dot_index].strip()
                field_path = channel_ref[dot_index + 1:].strip()

                # Phase 1: Reject nested field paths
                if "." in field_path:
                    raise ValueError(
                        f"Input '{field}': Nested field paths not supported in Phase 1 "
                        f"(got '{channel_ref}'). Use single-level fields only (e.g., 'channel.field')."
                    )

                # Validate field_path is not empty
                if not field_path:
                    raise ValueError(
                        f"Input '{field}': Field path cannot be empty (got '{channel_ref}')"
                    )

                binding = PipelineChannelBinding(
                    type_name=type_name.strip(),
                    channel_name=channel_name,
                    field_path=field_path,
                    source=ChannelSource.MODULE,
                )
            else:
                # Standard channel binding (no field reference) - UNCHANGED
                binding = PipelineChannelBinding(
                    type_name=type_name.strip(),
                    channel_name=channel_ref.strip(),
                    source=ChannelSource.MODULE,
                )

        bindings[field] = binding
    return bindings
```

#### 3. Create Phase 1 Unit Tests
**File:** `simkit/tests/core/test_pipeline_schema_field_reference.py` (NEW)

**Changes:**
- [x] Create new test file for field reference parsing
- [x] Test: Parse single-level field reference correctly
- [x] Test: Reject nested field paths (Phase 1 restriction)
- [x] Test: Standard bindings still work (backward compatibility)
- [x] Test: Reject empty field path (`"Type channel."`)
- [x] Test: Default bindings unchanged (`"None -> channel"`)
- [x] Test: Mix of standard, field reference, and default bindings

**Tests to implement:**
```python
import pytest
from simkit.config.pipeline_schema import _parse_inputs, ChannelSource


def test_parse_field_reference_single_level():
    """Parse 'Type channel.field' correctly into binding."""
    raw = {"blanket": "BlanketConfig fusion_params.blanket_config"}
    bindings = _parse_inputs(raw)

    assert bindings["blanket"].channel_name == "fusion_params"
    assert bindings["blanket"].field_path == "blanket_config"
    assert bindings["blanket"].type_name == "BlanketConfig"
    assert bindings["blanket"].is_field_reference is True
    assert bindings["blanket"].source is ChannelSource.MODULE


def test_parse_field_reference_rejects_nested():
    """Reject nested field paths in Phase 1."""
    raw = {"temp": "FloatValue fusion_params.blanket.temperature"}

    with pytest.raises(ValueError, match="Nested field paths not supported"):
        _parse_inputs(raw)


def test_parse_standard_binding_unchanged():
    """Ensure 'Type channel' still works without field path."""
    raw = {"geo": "Geography geo"}
    bindings = _parse_inputs(raw)

    assert bindings["geo"].channel_name == "geo"
    assert bindings["geo"].field_path is None
    assert bindings["geo"].is_field_reference is False


def test_parse_field_reference_empty_field_rejected():
    """Reject empty field path like 'Type channel.'"""
    raw = {"blanket": "BlanketConfig fusion_params."}

    with pytest.raises(ValueError, match="Field path cannot be empty"):
        _parse_inputs(raw)


def test_parse_default_binding_unchanged():
    """Default bindings still work with None -> syntax."""
    raw = {"design_prefs": "None -> design_pref_default"}
    bindings = _parse_inputs(raw)

    assert bindings["design_prefs"].source is ChannelSource.DEFAULT
    assert bindings["design_prefs"].field_path is None


def test_parse_multiple_bindings_mixed():
    """Mix of standard, field reference, and default bindings."""
    raw = {
        "geo": "Geography geo",
        "blanket": "BlanketConfig fusion_params.blanket_config",
        "design_prefs": "None -> design_pref_default"
    }
    bindings = _parse_inputs(raw)

    assert not bindings["geo"].is_field_reference
    assert bindings["blanket"].is_field_reference
    assert bindings["design_prefs"].is_default
```

### Success Criteria

#### Automated Verification:
- [x] All Phase 1 unit tests pass: `pytest simkit/tests/core/test_pipeline_schema_field_reference.py`
- [x] Existing pipeline schema tests still pass: `pytest simkit/tests/pipeline/test_pipeline_schema.py`
- [x] Type checking passes: `mypy simkit/config/pipeline_schema.py`
- [x] Linting passes: `ruff check simkit/config/pipeline_schema.py`

#### Manual Verification:
- [x] `PipelineChannelBinding` can be instantiated with `field_path` set
- [x] `is_field_reference` property correctly identifies field references
- [x] Parser correctly splits `"Type channel.field"` into components
- [x] Parser rejects nested paths with clear error message
- [x] Existing YAML pipelines parse without errors (backward compatibility)

### Implementation Notes - Phase 1
**Completed:** 2025-11-22
**Changes Made:**
- Extended `PipelineChannelBinding` with `field_path: str | None = None` (simkit/config/pipeline_schema.py:27)
- Added `is_field_reference` property to `PipelineChannelBinding` (simkit/config/pipeline_schema.py:37-39)
- Modified `_parse_inputs()` to parse `channel.field` syntax (simkit/config/pipeline_schema.py:240-303)
  - Detects dots in channel references
  - Splits on first dot only to enable future nested path support
  - Validates field_path is not empty
  - Rejects nested paths in Phase 1 with clear error message
  - Preserves exact existing behavior for standard and default bindings
- Created comprehensive test suite (simkit/tests/core/test_pipeline_schema_field_reference.py)
  - 6 tests covering parsing, validation, backward compatibility
  - All tests pass

**Test Results:**
- Phase 1 tests: 6/6 passed
- Existing pipeline schema tests: 11/11 passed (backward compatibility confirmed)

**Issues Encountered:**
- None - implementation proceeded exactly as planned

**Deviations from Plan:**
- None - all changes implemented as specified

---

## Phase 2: Validation Infrastructure

### Overview
Implements channel type tracking and field reference validation using Pydantic introspection. After this phase, pipelines with field references are validated at load time, catching typos and type mismatches.

### Test Stencil
```python
# Test for Phase 2 - field reference validation
def test_validate_field_exists(sample_registry, sample_output_router):
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="FusionParams",
        field_path="blanket_config",
        expected_type="BlanketConfig",
    )

    validator = PipelineValidator(sample_registry, sample_output_router)
    graph = validator.validate(spec)  # Should not raise
    assert graph is not None
```

### Changes Required

#### 1. Build Channel Type Map
**File:** `simkit/core/pipeline_validator.py`
**Location:** Add new method to `PipelineValidator` class

**Changes:**
- [ ] Create `_build_channel_type_map()` method in `PipelineValidator`
- [ ] Iterate through all modules in spec (skip exit modules)
- [ ] For entry modules: extract type from artifact bindings
- [ ] For regular modules: extract type from registry descriptor outputs
- [ ] Return `Dict[str, str]` mapping channel names to type names
- [ ] Handle MultiOutput by using descriptor output types (not channel dict)

**Code to add:**
```python
def _build_channel_type_map(
    self,
    spec: PipelineSpecification,
) -> Dict[str, str]:
    """
    Build a mapping of channel names to their type names.

    Used for field reference validation to determine parent channel types.
    Iterates through all non-exit modules and records their output channel types.

    Args:
        spec: The pipeline specification

    Returns:
        Dict mapping channel_name -> type_name (string)
    """
    channel_types: Dict[str, str] = {}

    for module_key, module_spec in spec.modules.items():
        if module_spec.is_exit:
            continue

        if module_spec.is_entry:
            # Entry module: types come from artifact bindings
            for binding in module_spec.outputs.values():
                if binding.type_name is not None:
                    channel_types[binding.channel_name] = binding.type_name
            continue

        # Regular module: get types from registry descriptor
        descriptor = self._registry.get(module_spec.module_type)

        for field, binding in module_spec.outputs.items():
            # Get expected type from descriptor
            expected_type = descriptor.outputs.get(field)
            if expected_type is not None:
                channel_types[binding.channel_name] = expected_type.__name__

    return channel_types
```

#### 2. Integrate Channel Type Map into Validation
**File:** `simkit/core/pipeline_validator.py`
**Location:** Lines 47-62 (`validate` method)

**Changes:**
- [ ] Call `_build_channel_type_map(spec)` at start of `validate()` method
- [ ] Pass `channel_types` dict to `_validate_inputs()` calls
- [ ] Update `_validate_inputs()` signature to accept `channel_types` parameter

**Code modification:**
```python
def validate(self, spec: PipelineSpecification) -> PipelineGraph:
    self._assert_entry_exit(spec)

    # NEW: Build channel type map for field reference validation
    channel_types = self._build_channel_type_map(spec)

    for module in spec.modules.values():
        if module.is_entry:
            continue
        if module.is_exit:
            self._validate_exit_module(module)
            continue
        descriptor = self._resolve_descriptor(module)
        self._validate_outputs(module, descriptor)
        self._validate_inputs(module, descriptor, channel_types)  # NEW: pass channel_types

    try:
        graph = self._builder.build(spec)
    except PipelineGraphError as exc:
        raise PipelineValidationError(str(exc)) from exc
    return graph
```

#### 3. Implement Optional Type Unwrapping
**File:** `simkit/core/pipeline_validator.py`
**Location:** Add new method to `PipelineValidator` class

**Changes:**
- [ ] Create `_unwrap_optional()` method in `PipelineValidator`
- [ ] Check if type annotation has `__origin__` attribute and is `typing.Union`
- [ ] Extract union args and filter out `None` type
- [ ] Return single non-None arg if union is `Optional[T]` pattern
- [ ] Return original annotation if not Optional

**Code to add:**
```python
def _unwrap_optional(self, type_annotation) -> type:
    """
    Unwrap Optional[T] to T. Returns original type if not Optional.

    Handles Python 3.10+ union syntax and typing.Optional:
    - Optional[BlanketConfig] → BlanketConfig
    - BlanketConfig | None → BlanketConfig
    - BlanketConfig → BlanketConfig (unchanged)

    Args:
        type_annotation: Type annotation to unwrap

    Returns:
        The unwrapped type (T) or original if not Optional
    """
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

#### 4. Implement Field Reference Validation
**File:** `simkit/core/pipeline_validator.py`
**Location:** Add new method to `PipelineValidator` class

**Changes:**
- [ ] Create `_validate_field_reference()` method in `PipelineValidator`
- [ ] Resolve parent type using `getattr(schema, parent_channel_type_name)`
- [ ] Check field exists in `parent_type.model_fields`
- [ ] Check field is not private (doesn't start with `_`)
- [ ] Extract field type annotation and unwrap Optional if present
- [ ] Resolve expected type using `getattr(schema, binding.type_name)`
- [ ] Check exact type match between actual and expected
- [ ] Check field is not in `parent_type.model_computed_fields` (Phase 1)
- [ ] Raise `PipelineValidationError` with helpful details for all failure cases

**Code to add:**
```python
def _validate_field_reference(
    self,
    binding: PipelineChannelBinding,
    parent_channel_type_name: str,
    module_key: str,
    field_name: str,
) -> None:
    """
    Validate that a field reference binding is well-formed.

    Performs comprehensive validation:
    1. Parent type exists in schema module
    2. Field exists in parent type
    3. Field is not private (no leading underscore)
    4. Field is not computed (Phase 1 restriction)
    5. Field type matches declared binding type (exact match)

    Args:
        binding: The binding with field_path set
        parent_channel_type_name: The type name of the parent channel
        module_key: Module key for error messages
        field_name: Input field name for error messages

    Raises:
        PipelineValidationError: If any validation check fails
    """
    from ..config import schema

    # 1. Resolve parent type
    try:
        parent_type = getattr(schema, parent_channel_type_name)
    except AttributeError:
        raise PipelineValidationError(
            f"Module '{module_key}' input '{field_name}': "
            f"Unknown schema type '{parent_channel_type_name}' for channel '{binding.channel_name}'",
            module=module_key,
        )

    # 2. Check field exists in parent type
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

    # 3. Check field is not private
    if binding.field_path.startswith("_"):
        raise PipelineValidationError(
            f"Module '{module_key}' input '{field_name}': "
            f"Cannot extract private field '{binding.field_path}' from channel '{binding.channel_name}'",
            module=module_key,
        )

    # 4. Get actual field type
    field_info = parent_type.model_fields[binding.field_path]
    actual_type_annotation = field_info.annotation

    # Unwrap Optional if present
    actual_type = self._unwrap_optional(actual_type_annotation)
    is_optional = actual_type != actual_type_annotation

    # 5. Resolve expected type from binding
    try:
        expected_type = getattr(schema, binding.type_name)
    except AttributeError:
        raise PipelineValidationError(
            f"Module '{module_key}' input '{field_name}': "
            f"Unknown type '{binding.type_name}'",
            module=module_key,
        )

    # 6. Check type compatibility (exact match in Phase 1)
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

    # 7. Phase 1: Disallow computed fields
    if binding.field_path in parent_type.model_computed_fields:
        raise PipelineValidationError(
            f"Module '{module_key}' input '{field_name}': "
            f"Cannot extract computed field '{binding.field_path}' (not supported in Phase 1)",
            module=module_key,
        )
```

#### 5. Integrate Field Reference Validation into Input Validation
**File:** `simkit/core/pipeline_validator.py`
**Location:** Lines 145-186 (`_validate_inputs` method)

**Changes:**
- [ ] Update `_validate_inputs()` signature to accept `channel_types: Dict[str, str]` parameter
- [ ] After existing validation checks, add field reference validation block
- [ ] Check if binding `is_field_reference` is True
- [ ] Lookup parent channel type from `channel_types` dict
- [ ] Call `_validate_field_reference()` with binding and parent type
- [ ] Preserve all existing validation logic (no changes to standard binding validation)

**Code modification:**
```python
def _validate_inputs(
    self,
    module: PipelineModuleSpec,
    descriptor: ModuleDescriptor,
    channel_types: Dict[str, str],  # NEW parameter
) -> None:
    """Validate module inputs against descriptor metadata."""
    expected_inputs = set(descriptor.required_inputs) | set(descriptor.optional_inputs)
    actual_inputs = set(module.inputs.keys())
    missing_required = set(descriptor.required_inputs) - actual_inputs
    if missing_required:
        raise PipelineValidationError(
            "Missing required input bindings",
            module=module.key,
            details={"missing": sorted(missing_required)},
        )
    missing_optional = set(descriptor.optional_inputs) - actual_inputs
    if missing_optional:
        raise PipelineValidationError(
            "Optional inputs must be explicitly bound or defaulted",
            module=module.key,
            details={"missing_optional": sorted(missing_optional)},
        )

    unknown_inputs = actual_inputs - expected_inputs
    if unknown_inputs:
        raise PipelineValidationError(
            "Specification declares inputs not defined by registry",
            module=module.key,
            details={"unknown": sorted(unknown_inputs)},
        )

    for field, binding in module.inputs.items():
        expected_type = (
            descriptor.required_inputs.get(field)
            or descriptor.optional_inputs.get(field)
        )
        if expected_type is None:
            continue  # already handled unknown inputs
        if binding.source is ChannelSource.DEFAULT:
            if field not in descriptor.optional_inputs:
                raise PipelineValidationError(
                    "Default binding supplied for a required input",
                    module=module.key,
                    details={"input": field},
                )
        else:
            # NEW: Validate field references
            if binding.is_field_reference:
                parent_type_name = channel_types.get(binding.channel_name)
                if parent_type_name is None:
                    raise PipelineValidationError(
                        f"Module '{module.key}' input '{field}': "
                        f"Cannot resolve type for channel '{binding.channel_name}' "
                        f"(required for field reference validation)",
                        module=module.key,
                    )
                self._validate_field_reference(
                    binding=binding,
                    parent_channel_type_name=parent_type_name,
                    module_key=module.key,
                    field_name=field,
                )

            # Standard type check (existing logic - UNCHANGED)
            self._assert_type(binding, expected_type, module.key, field, "input")
```

#### 6. Create Phase 2 Unit Tests
**File:** `simkit/tests/core/test_pipeline_validator_field_reference.py` (NEW)

**Changes:**
- [ ] Create new test file for field reference validation
- [ ] Create test schema models (TestBlanketConfig, TestFusionParams with various field types)
- [ ] Test: Validation passes when field exists
- [ ] Test: Validation fails when field doesn't exist (check error lists available fields)
- [ ] Test: Validation fails on type mismatch
- [ ] Test: Validation passes for Optional fields
- [ ] Test: Validation fails for private fields
- [ ] Test: Validation fails for computed fields (Phase 1)
- [ ] Test: Channel type map correctly tracks entry and module outputs

**Tests to implement:**
```python
import pytest
from pydantic import computed_field
from simkit.config.schema import StrictBaseModel
from simkit.core.pipeline_validator import PipelineValidator, PipelineValidationError


# Test schema models
class TestBlanketConfig(StrictBaseModel):
    material: str
    thickness_m: float


class TestFusionParams(StrictBaseModel):
    p_fusion: float
    blanket_config: TestBlanketConfig
    optional_blanket: TestBlanketConfig | None = None
    _private_field: str = "secret"

    @computed_field
    @property
    def p_electric(self) -> float:
        return self.p_fusion * 0.4


def test_validate_field_exists(sample_registry, sample_output_router):
    """Validation passes when field exists in parent type."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="blanket_config",
        expected_type="TestBlanketConfig",
    )

    validator = PipelineValidator(sample_registry, sample_output_router)
    graph = validator.validate(spec)
    assert graph is not None


def test_validate_field_not_exists(sample_registry, sample_output_router):
    """Validation fails when field doesn't exist, lists available fields."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="missing_field",
        expected_type="TestBlanketConfig",
    )

    validator = PipelineValidator(sample_registry, sample_output_router)
    with pytest.raises(PipelineValidationError) as exc_info:
        validator.validate(spec)

    assert "has no field 'missing_field'" in str(exc_info.value)
    assert "Available fields:" in str(exc_info.value)
    assert "blanket_config" in exc_info.value.details["available_fields"]


def test_validate_type_mismatch(sample_registry, sample_output_router):
    """Validation fails when field type doesn't match binding declaration."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="blanket_config",  # Actually TestBlanketConfig
        expected_type="Geography",     # Wrong type
    )

    validator = PipelineValidator(sample_registry, sample_output_router)
    with pytest.raises(PipelineValidationError, match="Type mismatch"):
        validator.validate(spec)


def test_validate_optional_field_allowed(sample_registry, sample_output_router):
    """Validation passes for Optional fields (runtime will check None)."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="optional_blanket",
        expected_type="TestBlanketConfig",
    )

    validator = PipelineValidator(sample_registry, sample_output_router)
    graph = validator.validate(spec)
    assert graph is not None


def test_validate_private_field_rejected(sample_registry, sample_output_router):
    """Validation fails for private fields (leading underscore)."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="_private_field",
        expected_type="str",
    )

    validator = PipelineValidator(sample_registry, sample_output_router)
    with pytest.raises(PipelineValidationError, match="Cannot extract private field"):
        validator.validate(spec)


def test_validate_computed_field_rejected(sample_registry, sample_output_router):
    """Validation fails for computed fields in Phase 1."""
    spec = create_spec_with_field_reference(
        parent_channel="fusion_params",
        parent_type="TestFusionParams",
        field_path="p_electric",  # @computed_field
        expected_type="float",
    )

    validator = PipelineValidator(sample_registry, sample_output_router)
    with pytest.raises(PipelineValidationError, match="computed field"):
        validator.validate(spec)


def test_build_channel_type_map(sample_spec, sample_registry):
    """Channel type map correctly tracks all output channels."""
    from simkit.io.output_router import create_default_router

    validator = PipelineValidator(sample_registry, create_default_router())
    channel_types = validator._build_channel_type_map(sample_spec)

    # Verify entry module outputs tracked
    assert "fusion_params" in channel_types
    # Verify regular module outputs tracked
    assert channel_types.get("rate_info") is not None
```

### Success Criteria

#### Automated Verification:
- [ ] All Phase 2 unit tests pass: `pytest simkit/tests/core/test_pipeline_validator_field_reference.py`
- [ ] Existing validator tests still pass: `pytest simkit/tests/core/test_pipeline_validator.py`
- [ ] Phase 1 tests still pass: `pytest simkit/tests/core/test_pipeline_schema_field_reference.py`
- [ ] Type checking passes: `mypy simkit/core/pipeline_validator.py`
- [ ] Linting passes: `ruff check simkit/core/pipeline_validator.py`

#### Manual Verification:
- [ ] Channel type map correctly identifies entry point channel types
- [ ] Channel type map correctly identifies module output channel types
- [ ] Field reference validation catches typos in field names
- [ ] Field reference validation provides helpful error with available fields
- [ ] Type mismatch errors show both expected and actual types
- [ ] Optional field validation passes (runtime will check None)
- [ ] Private and computed fields are rejected with clear errors

---

## Phase 3: Runtime Execution & Testing

### Overview
Implements runtime field extraction in executor and comprehensive test suite. After this phase, field references work end-to-end with full test coverage.

### Test Stencil
```python
# Test for Phase 3 - runtime field extraction
def test_execute_field_reference_extraction(tmp_path):
    fusion_params_path = tmp_path / "fusion_params.json"
    create_fusion_params_fixture(fusion_params_path)

    spec_path = tmp_path / "pipeline.yaml"
    create_pipeline_with_field_reference(spec_path, fusion_params_path)

    result = execute_pipeline(spec_path, output_dir=tmp_path)

    # Module received only BlanketConfig, not full FusionParams
    assert result.outputs is not None
```

### Changes Required

#### 1. Add Runtime Execution Exception
**File:** `simkit/core/pipeline_executor.py`
**Location:** Near top of file (around line 25)

**Changes:**
- [ ] Check if `PipelineExecutionError` exception already exists
- [ ] If not exists, create `PipelineExecutionError` exception class
- [ ] Add docstring explaining when this exception is raised

**Code to add (if not exists):**
```python
class PipelineExecutionError(Exception):
    """Raised when pipeline execution fails at runtime."""
    pass
```

#### 2. Implement Runtime Field Extraction
**File:** `simkit/core/pipeline_executor.py`
**Location:** Lines 290-293 (`_resolve_input` function)

**Changes:**
- [ ] After fetching channel value, check if `binding.field_path` is set
- [ ] If field path exists, use `getattr()` to extract field from channel value
- [ ] Wrap `getattr()` in try/except to catch `AttributeError`
- [ ] Check if extracted value is `None` (runtime validation for Optional fields)
- [ ] Raise `PipelineExecutionError` with helpful message if field is None
- [ ] Return extracted field value if extraction succeeds
- [ ] Preserve existing behavior for non-field-reference bindings

**Code modification:**
```python
def _resolve_input(binding: PipelineChannelBinding, context: PipelineExecutionContext) -> Any:
    """
    Resolve an input binding to its actual value.

    Handles three binding types:
    1. Default bindings (return None for module to fill)
    2. Standard channel bindings (return full channel value)
    3. Field reference bindings (extract field from channel value)  ← NEW

    Args:
        binding: The channel binding to resolve
        context: Execution context with channel storage

    Returns:
        The resolved value (channel value, extracted field, or None)

    Raises:
        PipelineExecutionError: If field extraction fails at runtime
        KeyError: If channel doesn't exist (shouldn't happen with proper validation)
    """
    if binding.source is ChannelSource.DEFAULT:
        return None

    # Fetch channel value
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
                f"(expected {binding.type_name}). Optional fields must have non-None values at runtime."
            )

        return extracted

    return value
```

#### 3. Create Phase 3 Executor Unit Tests
**File:** `simkit/tests/core/test_pipeline_executor_field_reference.py` (NEW)

**Changes:**
- [ ] Create new test file for executor field extraction
- [ ] Test: `_resolve_input` extracts field for field reference binding
- [ ] Test: `_resolve_input` returns full channel for standard binding (backward compat)
- [ ] Test: `_resolve_input` returns None for default binding (backward compat)
- [ ] Test: Optional field that is None raises `PipelineExecutionError`
- [ ] Test: Missing field raises `PipelineExecutionError` with helpful message

**Tests to implement:**
```python
import pytest
from simkit.config.schema import StrictBaseModel
from simkit.config.pipeline_schema import PipelineChannelBinding, ChannelSource
from simkit.core.pipeline_executor import (
    _resolve_input,
    PipelineExecutionContext,
    PipelineExecutionError,
)


class TestBlanketConfig(StrictBaseModel):
    material: str
    thickness_m: float


class TestFusionParams(StrictBaseModel):
    p_fusion: float
    blanket_config: TestBlanketConfig
    optional_blanket: TestBlanketConfig | None = None


def test_resolve_input_field_reference(sample_registry):
    """_resolve_input extracts field for field reference binding."""
    context = PipelineExecutionContext(sample_registry)
    fusion_params = TestFusionParams(
        p_fusion=100.0,
        blanket_config=TestBlanketConfig(material="steel", thickness_m=0.5)
    )
    context.set_channel("fusion_params", fusion_params)

    binding = PipelineChannelBinding(
        type_name="TestBlanketConfig",
        channel_name="fusion_params",
        field_path="blanket_config",
        source=ChannelSource.MODULE
    )

    result = _resolve_input(binding, context)
    assert isinstance(result, TestBlanketConfig)
    assert result.material == "steel"


def test_resolve_input_standard_binding(sample_registry):
    """_resolve_input returns full channel value for standard binding."""
    context = PipelineExecutionContext(sample_registry)
    fusion_params = TestFusionParams(
        p_fusion=100.0,
        blanket_config=TestBlanketConfig(material="steel", thickness_m=0.5)
    )
    context.set_channel("fusion_params", fusion_params)

    binding = PipelineChannelBinding(
        type_name="TestFusionParams",
        channel_name="fusion_params",
        source=ChannelSource.MODULE
    )

    result = _resolve_input(binding, context)
    assert isinstance(result, TestFusionParams)
    assert result.p_fusion == 100.0


def test_resolve_input_default_binding(sample_registry):
    """_resolve_input returns None for default binding (unchanged behavior)."""
    context = PipelineExecutionContext(sample_registry)

    binding = PipelineChannelBinding(
        type_name=None,
        channel_name="default_channel",
        source=ChannelSource.DEFAULT
    )

    result = _resolve_input(binding, context)
    assert result is None


def test_resolve_input_optional_field_none_raises(sample_registry):
    """Runtime error when Optional field is None."""
    context = PipelineExecutionContext(sample_registry)
    fusion_params = TestFusionParams(
        p_fusion=100.0,
        blanket_config=TestBlanketConfig(material="steel", thickness_m=0.5),
        optional_blanket=None  # Optional field is None
    )
    context.set_channel("fusion_params", fusion_params)

    binding = PipelineChannelBinding(
        type_name="TestBlanketConfig",
        channel_name="fusion_params",
        field_path="optional_blanket",
        source=ChannelSource.MODULE
    )

    with pytest.raises(PipelineExecutionError, match="is None"):
        _resolve_input(binding, context)
```

#### 4. Create End-to-End Integration Tests
**File:** `simkit/tests/test_pipeline_field_reference_e2e.py` (NEW)

**Changes:**
- [ ] Create new E2E test file for full pipeline field reference flow
- [ ] Test: Full pipeline with field extraction from EntryPoint
- [ ] Test: Multiple modules extract different fields from same channel
- [ ] Test: Validation fails on typo in field name
- [ ] Test: Runtime fails on Optional field that is None
- [ ] Include helper functions to create test fixtures and pipeline specs

**Tests to implement:**
```python
import json
import yaml
import pytest
from pathlib import Path
from simkit.core.pipeline import execute_pipeline
from simkit.core.pipeline_validator import PipelineValidationError
from simkit.core.pipeline_executor import PipelineExecutionError


def test_e2e_field_extraction_from_entry(tmp_path):
    """
    Full pipeline: EntryPoint → field extraction → modules → ExitPoint.

    Tests that modules receive only extracted fields, not full parent models.
    """
    # 1. Create test FusionParams JSON
    fusion_params = {
        "p_fusion": 500.0,
        "blanket_config": {
            "material": "tungsten",
            "thickness_m": 0.8,
            "temperature_k": 1500.0
        },
        "coolant_config": {
            "fluid_type": "helium",
            "flow_rate_kg_s": 10.0
        }
    }
    fusion_params_path = tmp_path / "fusion_params.json"
    fusion_params_path.write_text(json.dumps(fusion_params))

    # 2. Create pipeline YAML with field references
    pipeline_yaml = {
        "modules": {
            "entry_point": {
                "module_type": "EntryPoint",
                "inputs": {
                    "fusion_params": f"FusionParams {fusion_params_path}"
                }
            },
            "blanket_thermal": {
                "module_type": "BlanketThermalModule",
                "inputs": {
                    "blanket": "BlanketConfig fusion_params.blanket_config"
                },
                "outputs": {
                    "thermal_result": "ThermalOutput thermal_output"
                }
            },
            "exit_point": {
                "module_type": "ExitPoint",
                "outputs": {
                    "thermal_output": "ThermalOutput thermal_result.json"
                }
            }
        }
    }
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(yaml.dump(pipeline_yaml))

    # 3. Execute pipeline
    result = execute_pipeline(pipeline_path, output_dir=tmp_path)

    # 4. Verify execution succeeded
    assert result.outputs is not None
    assert "thermal_output" in result.outputs


def test_e2e_multiple_field_references(tmp_path):
    """Multiple modules extract different fields from same channel."""
    # Create FusionParams with multiple sub-configs
    # Create pipeline where 3 modules each extract different field
    # Verify all modules execute successfully
    pass  # Implement based on available test modules


def test_e2e_validation_fails_on_typo(tmp_path):
    """Validation catches typo in field name before execution."""
    fusion_params_path = tmp_path / "fusion_params.json"
    create_fusion_params_fixture(fusion_params_path)

    pipeline_yaml = {
        "modules": {
            "entry_point": {
                "module_type": "EntryPoint",
                "inputs": {"fusion_params": f"FusionParams {fusion_params_path}"}
            },
            "module1": {
                "module_type": "SomeModule",
                "inputs": {
                    "blanket": "BlanketConfig fusion_params.blanket_cfg"  # Typo!
                },
                "outputs": {"result": "Result result"}
            },
            "exit_point": {
                "module_type": "ExitPoint",
                "outputs": {"result": "Result result.json"}
            }
        }
    }
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(yaml.dump(pipeline_yaml))

    with pytest.raises(PipelineValidationError, match="has no field 'blanket_cfg'"):
        execute_pipeline(pipeline_path, output_dir=tmp_path)


def test_e2e_runtime_fails_on_optional_none(tmp_path):
    """Runtime error when Optional field is None."""
    fusion_params = {
        "p_fusion": 500.0,
        "blanket_config": {"material": "tungsten", "thickness_m": 0.8},
        "optional_blanket": None  # Optional field is None
    }
    fusion_params_path = tmp_path / "fusion_params.json"
    fusion_params_path.write_text(json.dumps(fusion_params))

    pipeline_yaml = {
        "modules": {
            "entry_point": {
                "module_type": "EntryPoint",
                "inputs": {"fusion_params": f"FusionParams {fusion_params_path}"}
            },
            "module1": {
                "module_type": "SomeModule",
                "inputs": {
                    "blanket": "BlanketConfig fusion_params.optional_blanket"  # None!
                },
                "outputs": {"result": "Result result"}
            },
            "exit_point": {
                "module_type": "ExitPoint",
                "outputs": {"result": "Result result.json"}
            }
        }
    }
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(yaml.dump(pipeline_yaml))

    with pytest.raises(PipelineExecutionError, match="is None"):
        execute_pipeline(pipeline_path, output_dir=tmp_path)


# Helper functions
def create_fusion_params_fixture(path: Path):
    """Create test FusionParams JSON fixture."""
    data = {
        "p_fusion": 500.0,
        "blanket_config": {
            "material": "tungsten",
            "thickness_m": 0.8,
            "temperature_k": 1500.0
        },
        "coolant_config": {
            "fluid_type": "helium",
            "flow_rate_kg_s": 10.0
        }
    }
    path.write_text(json.dumps(data))
```

### Success Criteria

#### Automated Verification:
- [ ] All Phase 3 unit tests pass: `pytest simkit/tests/core/test_pipeline_executor_field_reference.py`
- [ ] All E2E tests pass: `pytest simkit/tests/test_pipeline_field_reference_e2e.py`
- [ ] All Phase 1 & 2 tests still pass: `pytest simkit/tests/core/test_pipeline_schema_field_reference.py simkit/tests/core/test_pipeline_validator_field_reference.py`
- [ ] Existing executor tests still pass: `pytest simkit/tests/core/test_pipeline_executor.py`
- [ ] Full test suite passes: `pytest simkit/tests/`
- [ ] Type checking passes: `mypy simkit/core/pipeline_executor.py`
- [ ] Linting passes: `ruff check simkit/core/pipeline_executor.py`

#### Manual Verification:
- [ ] Field extraction works correctly at runtime
- [ ] Modules receive only extracted fields, not full parent models
- [ ] Optional field None check provides helpful error message
- [ ] Standard bindings still work without changes (backward compatibility)
- [ ] Default bindings still work without changes (backward compatibility)
- [ ] Error messages are actionable and include channel/field context

---

## Testing Strategy

### Unit Tests Coverage

**Phase 1 (Parsing):**
- Single-level field reference parsing
- Nested path rejection
- Empty field path rejection
- Standard binding backward compatibility
- Default binding backward compatibility
- Mixed binding types in single spec

**Phase 2 (Validation):**
- Field existence validation
- Field not found error with available fields
- Type mismatch detection
- Optional field handling
- Private field rejection
- Computed field rejection (Phase 1)
- Channel type map construction

**Phase 3 (Execution):**
- Field extraction from channel value
- Standard binding unchanged behavior
- Default binding unchanged behavior
- Optional field None runtime error
- Missing field defensive error

### Integration Tests Coverage

**End-to-End Scenarios:**
- Full pipeline with field extraction from EntryPoint
- Multiple modules extracting different fields from same channel
- Validation failure on field name typo
- Runtime failure on Optional field None
- Backward compatibility with existing pipelines

### Manual Testing Steps

1. **Test field reference parsing:**
   - [ ] Create YAML with `"Type channel.field"` syntax
   - [ ] Verify binding parses correctly with `field_path` set
   - [ ] Try nested path and verify Phase 1 rejection

2. **Test field reference validation:**
   - [ ] Create pipeline with typo in field name
   - [ ] Verify validation fails with helpful error listing available fields
   - [ ] Create pipeline with type mismatch
   - [ ] Verify validation fails with expected vs actual types

3. **Test field reference execution:**
   - [ ] Create test FusionParams JSON with sub-configs
   - [ ] Create pipeline extracting field from FusionParams
   - [ ] Execute pipeline and verify module receives only extracted field
   - [ ] Create pipeline with Optional field set to None
   - [ ] Verify runtime error with helpful message

4. **Test backward compatibility:**
   - [ ] Run existing pipeline specs without field references
   - [ ] Verify they still execute correctly
   - [ ] Verify no regression in existing tests

---

## Risk Management

### Identified Risks

**Risk 1: Channel type map doesn't handle MultiOutput correctly**
- **Likelihood:** Medium
- **Impact:** High (field references from MultiOutput channels would fail)
- **Mitigation:** Phase 1 restricts field references to direct module outputs; use descriptor output types, not channel dict
- **Rollback:** Can revert validation changes without affecting parser/executor if needed

**Risk 2: Pydantic introspection API changes between versions**
- **Likelihood:** Low (codebase already uses Pydantic v2)
- **Impact:** Medium (validation would break)
- **Mitigation:** Use consistent Pydantic v2 API (`model_fields`, `model_computed_fields`) throughout; add version check if needed
- **Rollback:** Parser changes standalone; validation can be disabled while fixing

**Risk 3: Type comparison fails for equivalent types from different imports**
- **Likelihood:** Low
- **Impact:** Medium (false type mismatch errors)
- **Mitigation:** Use identity check (`actual_type == expected_type`) which works for same type object; all types resolved from `simkit.config.schema`
- **Rollback:** Can adjust type compatibility check without changing other components

**Risk 4: Optional field validation passes but runtime fails (UX confusion)**
- **Likelihood:** High (intentional design decision)
- **Impact:** Low (technically correct, just potentially confusing)
- **Mitigation:** Clear error message explaining Optional fields must be non-None at runtime; document in error message
- **Rollback:** Could add warning during validation, but design decision is sound

**Risk 5: getattr() doesn't work with all Pydantic models**
- **Likelihood:** Very Low (StrictBaseModel guarantees)
- **Impact:** Medium (field extraction would fail)
- **Mitigation:** StrictBaseModel constraint ensures compatibility; defensive AttributeError catch; extensive testing
- **Rollback:** Can add alternative field access mechanism if needed

**Risk 6: Backward compatibility break in existing pipelines**
- **Likelihood:** Very Low (careful preservation of existing logic)
- **Impact:** Critical (would break production pipelines)
- **Mitigation:** Preserve exact existing logic for non-field-reference bindings; comprehensive regression tests; only add new code paths
- **Rollback:** All changes are additive; can disable field reference feature via feature flag if needed

### Dependencies

**Internal Dependencies:**
- Pydantic v2 API for model introspection
- Existing pipeline infrastructure (validator, executor, registry)
- StrictBaseModel base class for all data models
- Existing test fixtures and utilities

**External Dependencies:**
- None (all dependencies already in project)

**Sequencing Requirements:**
- Phase 1 must complete before Phase 2 (validation needs parsed bindings)
- Phase 2 must complete before Phase 3 (executor relies on validation)
- Each phase's tests must pass before proceeding to next phase

---

## References

**Original Documents:**
- Spec: `thoughts/specs/field_referencing_spec.md`
- Design: `thoughts/specs/field_referencing/2025-11-22-design.md`

**Codebase Files Modified:**
- `simkit/config/pipeline_schema.py` - Data model and parsing
- `simkit/core/pipeline_validator.py` - Validation infrastructure
- `simkit/core/pipeline_executor.py` - Runtime extraction

**Similar Implementations:**
- MultiOutput field extraction: `simkit/core/pipeline_executor.py:172-183`
- Type resolution from string: `simkit/core/pipeline_executor.py:281-287`
- Input parsing pattern: `simkit/config/pipeline_schema.py:234-262`

**Key Patterns:**
- Pydantic v2 field introspection: `model_fields`, `model_computed_fields`
- Pipeline validation error handling with details dict
- Executor input resolution with source-based routing

---

**End of Implementation Plan**
