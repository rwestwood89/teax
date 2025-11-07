# Spec: Custom Module Package Registration in Pipeline Executor

**Document Type:** Specification
**Version:** v1.0
**Status:** Draft
**Owner:** Reid Westwood
**Last Updated:** 2025-11-07
**Related Docs:**
- [Design Ticket](../tickets/custom-module-package-registration.md)
- [Phase 4 Blocker Analysis](/home/reid/apps/fusion_modeling/tests/teax_simkit/PHASE4_BLOCKER_NOTES.md)
**Related Ticket:** thoughts/tickets/custom-module-package-registration.md

## Overview

Enable external packages (like fusion_simkit) to register custom TEAx modules for pipeline execution by adding an optional registry parameter to `execute_pipeline()`. This unblocks code-generated module packages from integrating with TEAx's pipeline orchestration system.

## Problem Statement

External packages that generate custom TEAx modules cannot integrate with TEAx's pipeline execution system because there is no mechanism for registering their modules with the pipeline executor. The TEAx `execute_pipeline()` function and `SerialPipelineExecutor` have hardcoded module discovery that only finds built-in TEAx modules. When a pipeline YAML file references a custom module type from an external package (e.g., `module_type: AlphaNeutronSplit` from fusion_simkit), execution fails with errors like "Module 'alpha_neutron_split' requires unknown channel."

This architectural gap prevents domain-specific module packages from being orchestrated via TEAx pipelines, blocking the entire code generation workflow where SysML models are transformed into executable TEAx modules.

### Current State

- `execute_pipeline()` has no parameter for custom module discovery
- `SerialPipelineExecutor` only finds modules hardcoded in TEAx
- External packages can create `ModuleBase`-compliant modules that work individually (validated: 8/8 tests pass in fusion_modeling Phase 0)
- External packages can create `PipelineModuleRegistry` objects with `ModuleDescriptor` metadata
- Pipeline YAML files can be written referencing custom module types
- **BUT**: Pipeline execution fails because custom modules cannot be discovered

### Desired Outcome

External packages can pass a custom `PipelineModuleRegistry` to `execute_pipeline()`, enabling their modules to be discovered, instantiated, and orchestrated through TEAx's pipeline execution system. This enables:

1. **fusion_modeling Phase 0 validation**: 3 end-to-end pipeline tests execute successfully
2. **Code generation workflows**: SysML → Python modules → TEAx execution pipeline works end-to-end
3. **Domain-specific integration**: Any package can create custom TEAx modules and execute them via pipelines

## Requirements

The system SHALL provide a mechanism for external packages to register custom modules with the TEAx pipeline executor through an optional registry parameter.

WHEN a custom registry is not provided, the system SHALL maintain backward compatibility by using the default built-in TEAx module registry.

WHEN a custom registry is provided, the system SHALL validate the registry for basic integrity (duplicate module types, missing required fields) before pipeline execution.

WHEN a pipeline references a module type, the system SHALL discover and instantiate that module from the provided registry (or default registry if none provided).

## Acceptance Criteria

### Core Functionality
- [ ] The system SHALL accept an optional `registry` parameter in `execute_pipeline(spec_path, output_dir, registry=None)`
- [ ] WHEN `registry=None` THEN the system SHALL use the default built-in TEAx module registry
- [ ] WHEN a custom `registry` is provided THEN the system SHALL use it for module discovery and instantiation
- [ ] The system SHALL pass the registry to `SerialPipelineExecutor` during pipeline execution
- [ ] WHEN a pipeline YAML references a module_type in the custom registry THEN the system SHALL successfully instantiate that module using the registry's factory function

### Validation & Error Handling
- [ ] WHEN a custom registry contains duplicate module_type registrations THEN the system SHALL raise a clear ValidationError before pipeline execution
- [ ] WHEN a ModuleDescriptor is missing required fields (factory, required_inputs, outputs) THEN the system SHALL raise a clear ValidationError
- [ ] WHEN a pipeline YAML references a module_type not in the registry THEN the system SHALL raise a clear error message identifying the missing module

### Integration & Data Flow
- [ ] The system SHALL correctly route channel data between custom modules based on ModuleDescriptor input/output specifications
- [ ] WHEN custom modules produce outputs THEN those outputs SHALL be available to downstream modules via channel routing
- [ ] The system SHALL execute multi-module pipelines with custom modules in correct topological order

### Edge Cases
- [ ] WHEN a custom module factory function raises an exception THEN the system SHALL propagate the error with context about which module failed
- [ ] WHEN a custom module's required_inputs don't match available channels THEN the system SHALL raise a clear error before execution

### Quality & Integration
- [ ] The system SHOULD maintain backward compatibility (existing code without `registry` parameter continues to work)
- [ ] The implementation SHOULD be approximately 50 lines of code or less in TEAx core
- [ ] Error messages SHOULD clearly identify which module and which field caused validation failures

## Scope Boundaries

### In Scope
- Adding `registry` parameter to `execute_pipeline()` function
- Passing registry to `SerialPipelineExecutor` constructor/methods
- Basic registry validation (duplicate module types, missing required fields)
- Clear error messages for validation failures
- Backward compatibility when `registry=None`
- Documentation of usage pattern for external packages

### Out of Scope
- Global registry pattern (deferred as Option B future enhancement)
- Entry point auto-discovery via Python entry points (deferred as Option C future enhancement)
- Creating or modifying the `PipelineModuleRegistry` class itself (already exists in TEAx)
- Auto-generating registry creation code in code generators (that's fusion_modeling Phase 1+)
- Merging multiple registries together
- Advanced validation (type compatibility checking, circular dependency detection, semantic validation)
- Registry versioning or migration
- Hot-reloading of registry during execution

## Edge Cases & Considerations

### Registry Validation
- **Duplicate module_type**: If registry contains two modules with same `module_type`, fail fast with clear error listing the duplicate
- **Missing factory**: If `ModuleDescriptor.factory` is None or missing, fail with error identifying which module_type is invalid
- **Missing input/output specs**: If `required_inputs` or `outputs` is None/missing, fail with clear error
- **Empty registry**: Empty custom registry is valid (though likely user error) - document this behavior

### Module Instantiation
- **Factory function fails**: Wrap factory exceptions with context about which module_type failed to instantiate
- **Factory returns None**: Treat as error, fail with clear message
- **Factory returns wrong type**: If factory doesn't return `ModuleBase` subclass, fail with type error

### Channel Routing
- **Missing required channel**: If module declares `required_inputs` but pipeline doesn't provide matching channel, fail before execution with clear error listing missing channels
- **Type mismatches**: Document that registry validation does NOT check type compatibility between channels (deferred to future enhancement)
- **Optional inputs**: Document that `optional_inputs` in ModuleDescriptor are not validated (module handles missing optional inputs)

### Backward Compatibility
- **Existing tests**: All existing TEAx pipeline tests must pass without modification
- **Default behavior**: `execute_pipeline(path, output_dir)` without registry parameter must work exactly as before
- **Error messages**: Error messages for built-in modules should not change

## Success Criteria

The feature is complete when:

1. **fusion_modeling Phase 0 tests pass**: All 3 tests in `tests/teax_simkit/test_fusion_pipeline.py` execute successfully with custom fusion registry
2. **Backward compatibility verified**: All existing TEAx pipeline tests pass without modification
3. **Usage pattern documented**: External packages can follow documented pattern to create and use custom registries
4. **Error handling validated**: Clear error messages for all validation failure scenarios
5. **Code changes minimal**: Implementation requires ~50 LOC or less in TEAx core (as estimated in ticket)

### Concrete Validation

The following user code pattern must work:

```python
# fusion_simkit creates custom registry
from fusion_simkit import create_fusion_registry
from teax.simkit.core.pipeline import execute_pipeline

# Pass registry to execute_pipeline
registry = create_fusion_registry()  # Contains AlphaNeutronSplit, BlanketThermalPower, etc.
result = execute_pipeline("fusion_pipeline.yaml", "outputs/", registry=registry)

# Pipeline executes successfully
assert result.outputs["p_electric_gross"] > 0
```

Where `fusion_pipeline.yaml` contains:

```yaml
modules:
  - name: alpha_split
    module_type: AlphaNeutronSplit
    inputs:
      p_fusion: p_fusion_input.p_fusion
    outputs:
      - p_alpha
      - p_neutron
```

And `create_fusion_registry()` should be simple way of taking module references (e.g. in /home/reid/apps/fusion_modeling/tests/teax_simkit/modules) into the correct format/payload for the `execute_pipeline` method.


## Status Tracking

**Implementation Plan**: TBD (will link to thoughts/plans/ when created)
**Validation Report**: TBD (will link to thoughts/validation/ when tests pass)
**Related Ticket**: [thoughts/tickets/custom-module-package-registration.md](../tickets/custom-module-package-registration.md)

### Files to Modify (from ticket analysis)
- `teax/simkit/core/pipeline.py` - Add `registry` parameter to `execute_pipeline()`
- `teax/simkit/core/serial_executor.py` - Accept and use registry in `SerialPipelineExecutor`
- `teax/simkit/core/pipeline_registry.py` - Add validation methods (if not already present)
- `teax/simkit/tests/pipeline/test_pipeline_execution.py` - Add custom registry tests

### Estimated Effort (from ticket)
- Implementation: 0.5-1 day
- Documentation: 0.25 day
- Testing: Included in implementation (pytest tests)

### Unblocks
- fusion_modeling Phase 0 validation (3 end-to-end pipeline tests)
- fusion_modeling Phase 1+ code generation implementation
- All future domain-specific module packages
