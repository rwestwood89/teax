# Ticket: Support Custom Module Package Registration in Pipeline Executor

**Created:** 2025-11-07
**Priority:** High
**Type:** Design
**Status:** Open

## Overview

TEAx pipeline executor cannot discover or execute custom modules from external packages (e.g., fusion_simkit). Need mechanism to register custom module packages for pipeline execution.

## Description

**Problem:**
- `execute_pipeline()` currently only finds built-in TEAx modules
- External packages like fusion_simkit cannot register custom modules with TEAx
- Pipeline YAML referencing custom module_type fails with "Module 'X' requires unknown channel"

**Root Cause:**
TEAx `execute_pipeline()` and `SerialPipelineExecutor` have hardcoded module discovery. No mechanism exists for external packages to register custom modules for pipeline execution.

**Impact:**
- Blocks fusion_modeling Phase 0 validation (end-to-end pipeline tests)
- Blocks all future code-generated module packages from executing via TEAx
- Custom domain-specific modules cannot integrate with TEAx pipelines

### Reference
Read `/home/reid/apps/fusion_modeling/tests/teax_simkit` in FULL for context on usage patterns referenced below

**Concrete Use Case (Fusion Modeling):**
```python
# fusion_simkit generates custom modules following ModuleBase pattern
from fusion_simkit.modules import AlphaNeutronSplitModule, BlanketThermalPowerModule

# Modules work individually (8/8 tests pass)
module = AlphaNeutronSplitModule()
result = module.run({"p_fusion": 2600.0})  # ✅ Works

# But TEAx pipeline execution fails
from teax.simkit.core.pipeline import execute_pipeline
execute_pipeline("fusion_pipeline.yaml", "outputs/")
# ❌ Error: Module 'alpha_neutron_split' requires unknown channel 'p_fusion_input.p_fusion'
```

**Implementation Options:**

### Option A: Registry Parameter (RECOMMENDED)
Add optional `registry` parameter to `execute_pipeline()`:

```python
# teax/simkit/core/pipeline.py
def execute_pipeline(
    spec_path: Path,
    output_dir: Path,
    registry: PipelineModuleRegistry | None = None  # ← NEW
) -> PipelineResult:
    """Execute pipeline with optional custom module registry.

    Args:
        spec_path: Path to pipeline YAML
        output_dir: Output directory
        registry: Optional custom module registry. If None, uses default TEAx modules.
    """
    if registry is None:
        registry = get_default_registry()  # Built-in TEAx modules

    executor = SerialPipelineExecutor(registry=registry)
    spec = load_pipeline_spec(spec_path)
    return executor.execute(spec, output_dir)
```

**User Code:**
```python
from fusion_simkit import create_fusion_registry
from teax.simkit.core.pipeline import execute_pipeline

registry = create_fusion_registry()  # Contains AlphaNeutronSplit, etc.
result = execute_pipeline("fusion_pipeline.yaml", "outputs/", registry=registry)
```

**Pros:**
- Simple, explicit, testable
- Backward compatible (registry=None uses default)
- ~50 LOC change in TEAx
- User controls exactly which modules are available

**Cons:**
- User must explicitly pass registry (acceptable tradeoff)

### Option B: Global Registry Pattern
Add global registration mechanism:

```python
# teax/simkit/core/pipeline_registry.py
_GLOBAL_REGISTRIES = []

def register_module_package(registry: PipelineModuleRegistry):
    """Register a custom module package globally."""
    _GLOBAL_REGISTRIES.append(registry)

def get_combined_registry() -> PipelineModuleRegistry:
    """Get combined global registry (built-in + custom)."""
    combined = get_default_registry()
    for reg in _GLOBAL_REGISTRIES:
        combined.merge(reg)  # Assumes merge() method exists
    return combined
```

**User Code:**
```python
from fusion_simkit import create_fusion_registry
from teax.simkit.core.pipeline_registry import register_module_package
from teax.simkit.core.pipeline import execute_pipeline

register_module_package(create_fusion_registry())
result = execute_pipeline("fusion_pipeline.yaml", "outputs/")
```

**Pros:**
- Zero config after registration
- Modules available to all pipelines

**Cons:**
- Global state (harder to test, potential conflicts)
- Requires `PipelineModuleRegistry.merge()` method

### Option C: Entry Point Discovery (Future Enhancement)
Use Python entry points for auto-discovery:

```toml
# fusion_simkit/pyproject.toml
[project.entry-points."teax.modules"]
fusion = "fusion_simkit:create_fusion_registry"
```

```python
# teax/simkit/core/plugin_discovery.py (NEW)
import importlib.metadata

def discover_module_packages() -> list[PipelineModuleRegistry]:
    """Discover custom module packages via entry points."""
    registries = []
    for entry_point in importlib.metadata.entry_points(group="teax.modules"):
        register_func = entry_point.load()
        registries.append(register_func())
    return registries
```

**Pros:**
- Standard Python plugin pattern
- Zero import statements needed
- Scales to many module packages

**Cons:**
- More complex implementation (~100 LOC)
- Requires pyproject.toml generation in code generator
- Discovery happens at import time (less explicit)

## Recommendation

**Implement Option A first** (registry parameter):
- Simplest, quickest implementation (~50 LOC)
- Unblocks fusion_modeling Phase 0 immediately
- Backward compatible
- Can add Option C later as enhancement

**Estimated Effort:**
- Option A: 0.5-1 day (modify `execute_pipeline()`, add tests)
- Documentation: 0.25 day

**Files to Modify:**
- `teax/simkit/core/pipeline.py` - Add `registry` parameter to `execute_pipeline()`
- `teax/simkit/core/serial_executor.py` - Pass registry to `SerialPipelineExecutor`
- `teax/simkit/tests/pipeline/test_pipeline_execution.py` - Add custom registry tests

**Success Criteria:**
- `execute_pipeline(path, output, registry=custom_registry)` works
- Tests pass with custom module registry
- fusion_modeling Phase 4 pipeline tests pass (3/3 tests green)
- Documentation updated with custom module registration pattern

## References

**Blocked Work:**
- fusion_modeling Phase 0: `tests/teax_simkit/test_fusion_pipeline.py` (3 tests written, blocked on execution)
- fusion_modeling Phase 0: `tests/teax_simkit/PHASE4_BLOCKER_NOTES.md` (detailed analysis)
- fusion_modeling Gap Analysis: `project/research/codegen_requirements_from_phase0.md#gap-6`

**Working Examples:**
- fusion_modeling Phase 3: `tests/teax_simkit/test_module_registration.py` - Shows ModuleDescriptor pattern
- fusion_modeling Phase 3: `tests/teax_simkit/conftest.py` - Shows `create_fusion_registry()` pattern

**Pipeline YAML:**
- fusion_modeling: `tests/teax_simkit/fixtures/fusion_pipeline.yaml` - Ready for execution once registration works

**Value:**
Without this enhancement, fusion_modeling code generator cannot produce TEAx-executable modules. This blocks Phase 1+ implementation and prevents automated fusion physics workflows.
