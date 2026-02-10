# Implementation Plan: ExitPoint Bare Primitive Type Support

**Status:** Complete
**Created:** 2026-02-10
**Last Updated:** 2026-02-10

## Source Documents
- **Spec:** `.project/active/exitpoint-primitive-types/spec.md`
- **Design:** `.project/active/exitpoint-primitive-types/design.md` -- See here for component details, dependencies, architecture

## Implementation Strategy

**Phasing Rationale:**
Phase 1 delivers the critical path (ExitPoint write) that unblocks sysml-codegen. Phase 2 completes the symmetric API (EntryPoint read + type resolution). Phase 3 validates everything end-to-end. Each phase is self-contained with its own tests and validation.

**Overall Validation Approach:**
- Each phase starts with tests
- Each phase has automated + manual validation
- Full regression suite (`pytest`) run after each phase

---

## Phase 1: Primitive Writer + OutputRouter Registration

### Goal
Enable ExitPoint to serialize bare `float`, `int`, `str`, `bool` to JSON files. This is the critical path that unblocks sysml-codegen multi-output pipelines.

### Test Stencil (Write This First)
```python
# tests/io/test_output_router.py - add to existing file

def test_write_json_primitive_float(tmp_path):
    path = tmp_path / "value.json"
    writers.write_json_primitive(42.0, path)
    assert json.loads(path.read_text()) == 42.0

def test_write_json_primitive_int(tmp_path):
    path = tmp_path / "value.json"
    writers.write_json_primitive(7, path)
    assert json.loads(path.read_text()) == 7

def test_write_json_primitive_str(tmp_path):
    path = tmp_path / "value.json"
    writers.write_json_primitive("hello", path)
    assert json.loads(path.read_text()) == "hello"

def test_write_json_primitive_bool(tmp_path):
    path = tmp_path / "value.json"
    writers.write_json_primitive(True, path)
    assert json.loads(path.read_text()) is True

def test_default_router_has_primitive_handlers():
    router = create_default_router()
    for type_name in ("float", "int", "str", "bool"):
        assert router.has_handler(type_name)

def test_output_router_writes_primitive_float(tmp_path):
    router = create_default_router()
    bindings = {
        "result": PipelineChannelBinding(
            type_name="float", channel_name="result",
            source=ChannelSource.MODULE, destination_filename="result.json",
        )
    }
    values = {"result": 42.0}
    result = router.write_outputs(bindings, values, base_output_dir=tmp_path, run_name="test")
    written = json.loads((result.run_dir / "result.json").read_text())
    assert written == 42.0
```

### Changes Required

**See `design.md#component-1-primitive-writer-writerspymd` for:** function signature, behavior, JSON format rationale

**See `design.md#component-2-default-router-registration-output_routerpy` for:** handler entries, propagation behavior

**Specific file changes:**

#### 1. Test File
**File:** `simkit/tests/io/test_output_router.py` (EXTEND)
- [x] Add 6 test functions per stencil above

#### 2. Writer Function
**File:** `simkit/io/writers.py` (after line 49)
- [x] Add `write_json_primitive()` per `design.md#component-1`

#### 3. Router Registration
**File:** `simkit/io/output_router.py` (lines 262-272 in `create_default_router()`)
- [x] Add 4 primitive handler entries per `design.md#component-2`

### Validation

**Automated:**
- [x] `pytest packages/teax-simkit/simkit/tests/io/test_output_router.py -v` -- All pass including 6 new tests (19 total)
- [x] `pytest packages/teax-simkit/` -- No regressions in framework tests (120 passed)

**What We Know Works After This Phase:**
- `write_json_primitive()` serializes all 4 types to raw JSON
- Default router recognizes `"float"`, `"int"`, `"str"`, `"bool"` as valid ExitPoint types
- OutputRouter.write_outputs() successfully writes primitive values to disk

---

## Phase 2: Schema Type Registry + Entry Loaders + Type Resolution

### Goal
Complete the symmetric API: primitive types resolvable by `_resolve_schema_type()` and loadable at EntryPoint. Introduces the `_PRIMITIVE_TYPES` constant as single source of truth.

### Test Stencil (Write This First)
```python
# tests/core/test_custom_schema_registration.py - add to existing file

def test_schema_registry_includes_primitives():
    registry = _build_schema_type_registry()
    for name, expected_type in [("float", float), ("int", int), ("str", str), ("bool", bool)]:
        assert name in registry
        assert registry[name] is expected_type

def test_resolve_schema_type_primitives_with_registry():
    registry = _build_schema_type_registry()
    for name, expected in [("float", float), ("int", int), ("str", str), ("bool", bool)]:
        assert _resolve_schema_type(name, registry) is expected

def test_resolve_schema_type_primitives_fallback():
    # No registry (type_registry=None) -- fallback path
    for name, expected in [("float", float), ("int", int), ("str", str), ("bool", bool)]:
        assert _resolve_schema_type(name, None) is expected

def test_primitive_entry_loaders_registered():
    for t in (float, int, str, bool):
        assert t in _BUILTIN_ENTRY_LOADERS

def test_primitive_entry_loader_reads_float(tmp_path):
    path = tmp_path / "value.json"
    path.write_text("42.0")
    result = _BUILTIN_ENTRY_LOADERS[float](path)
    assert isinstance(result, float)
    assert result == 42.0

def test_primitive_entry_loader_rejects_type_mismatch(tmp_path):
    path = tmp_path / "value.json"
    path.write_text('"hello"')  # str, not int
    with pytest.raises(TypeError, match="Expected int"):
        _BUILTIN_ENTRY_LOADERS[int](path)
```

### Changes Required

**See `design.md#component-3-schema-type-registry-pipeline_executorpy` for:** `_PRIMITIVE_TYPES` constant, registry spread, fallback path, return type annotation

**See `design.md#component-4-entry-loaders-pipeline_executorpy` for:** `_load_json_primitive()` helper, loader registration, type checking rationale

**Specific file changes:**

#### 1. Test File
**File:** `simkit/tests/core/test_custom_schema_registration.py` (EXTEND)
- [x] Add 6 test functions per stencil above
- [x] Update `test_all_user_facing_schemas_registered`: change `len(registry) == 8` to `len(registry) == 12`, add primitive assertions
- [x] Add import for `_resolve_schema_type` (from `pipeline_executor`)
- [x] Also update `test_returns_dict_with_builtin_schemas` count from 8 to 12

#### 2. Implementation
**File:** `simkit/core/pipeline_executor.py`
- [x] Add `_PRIMITIVE_TYPES` constant (single source of truth) per `design.md#3a`
- [x] Spread `**_PRIMITIVE_TYPES` into `_build_schema_type_registry()` registry dict per `design.md#3b`
- [x] Add primitive fallback in `_resolve_schema_type()` else branch per `design.md#3c`
- [x] Widen `_resolve_schema_type()` return type to `-> type` per `design.md#3d`
- [x] Add `_load_json_primitive()` helper per `design.md#component-4`
- [x] Add 4 primitive loaders to `_BUILTIN_ENTRY_LOADERS` per `design.md#component-4`
- [x] Widen `_BUILTIN_ENTRY_LOADERS` type annotation from `Dict[type[BaseModel], Any]` to `Dict[type, Any]`

### Validation

**Automated:**
- [x] `pytest packages/teax-simkit/simkit/tests/core/test_custom_schema_registration.py -v` -- All 26 pass including 6 new + 2 updated tests
- [x] `pytest packages/teax-simkit/` -- No regressions (126 passed)

**What We Know Works After This Phase:**
- `_PRIMITIVE_TYPES` is single source of truth (used by both registry and fallback)
- `_resolve_schema_type("float")` works with and without custom type registry
- Entry loaders can read primitive JSON files with type checking
- Type mismatch raises `TypeError` (not silent coercion)

---

## Phase 3: Integration Tests + YAML Fixture

### Goal
End-to-end pipeline verification with primitive ExitPoint types -- both file-based and in-memory modes. This is the final validation that all components work together.

### Test Stencil (Write This First)
```python
# tests/test_toy_pipeline.py - add to existing file

class TestToyPipelinePrimitiveExit:

    def test_toy_pipeline_with_primitive_exit_type(self, toy_registry, tmp_path):
        """Pipeline with bare float ExitPoint writes correct JSON."""
        spec_path = PIPELINE_CONFIGS_DIR / "toy_linear_primitive_exit.yaml"
        router = create_output_router_with_json_schemas(
            ["RootModel[float]"], include_builtins=True,
        )
        result = execute_pipeline(
            spec_path=str(spec_path), output_dir=str(tmp_path),
            registry=toy_registry, custom_schema_types=[ToyInput],
            output_router=router,
        )
        assert "doubled_value" in result.outputs
        assert result.outputs["doubled_value"] == 20.0  # bare float, not RootModel
        output_dir = Path(result.manifest.base_output_dir) / result.manifest.run_directory
        written = json.loads((output_dir / "doubled_value.json").read_text())
        assert written == 20.0

    def test_toy_pipeline_with_primitive_exit_in_memory(self, toy_registry):
        """In-memory mode with bare float ExitPoint validates correctly."""
        spec_path = PIPELINE_CONFIGS_DIR / "toy_linear_primitive_exit.yaml"
        router = create_output_router_with_json_schemas(
            ["RootModel[float]"], include_builtins=True, in_memory=True,
        )
        result = execute_pipeline(
            spec_path=str(spec_path), output_dir=None,
            registry=toy_registry, custom_schema_types=[ToyInput],
            output_router=router,
        )
        assert result.manifest is not None
        float_artifact = next(
            a for a in result.manifest.artifacts if a.type_name == "float"
        )
        assert float_artifact.produced is True
```

### Changes Required

**Specific file changes:**

#### 1. YAML Fixture
**File:** `simkit/tests/fixtures/pipeline_configs/toy_linear_primitive_exit.yaml` (NEW)
- [x] Create pipeline YAML that uses `float` as ExitPoint type
- [x] Pattern: `ToyPrimitiveOutputModule` (MultiOutput with bare float field) produces bare float in channel

#### 2. Toy Module
**File:** `simkit/tests/core/toy_modules.py` (EXTEND)
- [x] Add `ToyPrimitiveMultiOutput(MultiOutput)` with `doubled_value: float` field
- [x] Add `ToyPrimitiveOutputModule` that doubles input and outputs via MultiOutput extraction

#### 3. Test File
**File:** `simkit/tests/test_toy_pipeline.py` (EXTEND)
- [x] Add `TestToyPipelinePrimitiveExit` class with 2 tests per stencil
- [x] Add `import json`
- [x] Add `ToyPrimitiveOutputModule` to imports and `toy_registry` fixture

### Validation

**Automated:**
- [x] `pytest packages/teax-simkit/simkit/tests/test_toy_pipeline.py -v` -- All 13 pass including 2 new tests
- [x] `pytest` (from root) -- Full regression, 197 passed across both packages

**Manual:**
- [ ] Inspect written JSON file to confirm raw format (e.g., `42.0` not `{"value": 42.0}`)

**What We Know Works After This Phase:**
- Full pipeline execution with primitive ExitPoint type (file-based)
- In-memory mode correctly validates primitive ExitPoint bindings
- All spec acceptance criteria satisfied

---

## Environment Setup

**See CLAUDE.md for full environment rules:**
```bash
source .venv/bin/activate
pytest                                    # All tests from root
pytest packages/teax-simkit/              # Framework tests only
pytest packages/teax-simkit/simkit/tests/io/test_output_router.py -v  # Specific test file
```

---

## Risk Management

**See `design.md#potential-risks` for detailed risk analysis**

**Phase-Specific Mitigations:**
- **Phase 1**: No existing code modified, only additive. Zero regression risk.
- **Phase 2**: `test_all_user_facing_schemas_registered` count change is expected. Update in same commit as production code.
- **Phase 3**: YAML fixture wiring may need adjustment -- the exact channel plumbing depends on how ExitPoint resolves field references on `RootModel[float]` channels. If ExitPoint can't do field extraction, we may need a multi-output toy module that produces bare floats directly.

## Implementation Notes

[TO BE FILLED DURING IMPLEMENTATION]

### Phase 1 Completion
**Completed:** 2026-02-10
**Actual Changes:**
- Added `write_json_primitive()` to `simkit/io/writers.py:52-68` -- serializes bare primitives to raw JSON with `indent=2`
- Added 4 primitive WriteHandler entries (`float`, `int`, `str`, `bool`) to `create_default_router()` in `simkit/io/output_router.py:271-275`
- Added 6 test functions to `simkit/tests/io/test_output_router.py:342-399`
**Issues:** None
**Deviations:** None -- implementation matched plan exactly

### Phase 2 Completion
**Completed:** 2026-02-10
**Actual Changes:**
- Added `_PRIMITIVE_TYPES` constant to `simkit/core/pipeline_executor.py:317-322`
- Spread `**_PRIMITIVE_TYPES` into `_build_schema_type_registry()` registry dict at line 468
- Added primitive fallback check in `_resolve_schema_type()` else branch at lines 361-363
- Widened `_resolve_schema_type()` return type from `-> type[schema.StrictBaseModel]` to `-> type`
- Added `_load_json_primitive()` helper and 4 primitive loaders to `_BUILTIN_ENTRY_LOADERS` at end of file
- Widened `_BUILTIN_ENTRY_LOADERS` annotation from `Dict[type[BaseModel], Any]` to `Dict[type, Any]`
- Added 6 tests in `TestPrimitiveTypeSupport` class in `test_custom_schema_registration.py`
- Updated 2 existing count assertions from 8 to 12
**Issues:** One additional count assertion (`test_returns_dict_with_builtin_schemas`) needed updating beyond what the plan identified. Fixed immediately.
**Deviations:** None significant

### Phase 3 Completion
**Completed:** 2026-02-10
**Actual Changes:**
- Created `ToyPrimitiveMultiOutput` and `ToyPrimitiveOutputModule` in `simkit/tests/core/toy_modules.py`
- Created `simkit/tests/fixtures/pipeline_configs/toy_linear_primitive_exit.yaml`
- Added `TestToyPipelinePrimitiveExit` class with 2 tests to `simkit/tests/test_toy_pipeline.py`
- Updated `toy_registry` fixture to include `ToyPrimitiveOutputModule`
**Issues:** None
**Deviations:** Plan suggested using ToyDoublerModule with field extraction at ExitPoint, but ExitPoint reads channels directly (no field extraction). Created `ToyPrimitiveOutputModule` (MultiOutput with bare float field) instead -- `to_channel_dict()` naturally extracts bare floats into channels. This is the realistic multi-output pattern that sysml-codegen uses.

---

**Status**: Draft -> In Progress -> Complete
