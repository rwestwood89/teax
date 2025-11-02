# Spec: Pipeline Configuration Refactor

**Document Type:** Specification
**Version:** v1.0 (Draft)
**Status:** Implementation In Progress
**Owner:** Open
**Last Updated:** 2025-09-22
**Related Docs:** tea_simulation_design_doc.md, thoughts/plans/2025-09-21-dynamic-pipeline-construction-plan.md

## Overview
Streamline pipeline execution by eliminating the separate scenario configuration YAML, sourcing all runtime inputs from the pipeline specification.

## Problem Statement
The current executor path still depends on a `ScenarioDemo` payload derived from `entry_point_validate`. This duplicates data already available via entry bindings, introduces special-case behaviour (overrides, feature flag plumbing), and encourages contributors to encode bespoke module wiring outside the pipeline spec. It conflicts with the goal that pipeline behaviour should be fully determined by the pipeline definition.

## Goals
- Remove reliance on the scenario YAML for runtime data; the pipeline spec becomes the single source of truth.
- Delete the `ScenarioDemo` dependency, scenario overrides, and unused feature flag plumbing from the executor.
- Introduce an optional metadata section in the pipeline spec for provenance-only values (e.g., scenario name).


## Non-Goals
- Changing the pipeline DAG schema for modules/edges beyond the additions listed here.
- Modifying module business logic or registry descriptors beyond parameter alignment already complete.

## Requirements
1. The pipeline specification SHALL include an optional top-level `metadata` block for provenance fields such as `scenario_name` or notes.
2. The executor SHALL load all input artifacts solely from the pipeline spec bindings; the scenario configuration file SHALL no longer be required.
3. Overrides expressed via scenario YAML SHALL be removed; contributors will edit the pipeline spec (or duplicate it) to change inputs.
4. Feature flags SHALL be removed from the executor API 
5. Provenance generation SHALL derive scenario metadata from the spec metadata rather than `ScenarioDemo`.
6. Update `thoughts/designs/2025-09-21-dynamic-pipeline-construction-design.md` to v2.0 which captures these changes.

## Proposed Changes
### Schema Updates
- Extend `PipelineSpecification` to accept an optional `metadata` dictionary (e.g., `name`, `notes`).

### Executor Simplification
- Remove `ScenarioDemo` from `PipelineExecutionContext`; store only overrides (if any) and channel data.
- Delete override handling and feature flag fan-out; modules will receive no flag dict.
- Update provenance composition to read from spec metadata.

### Entry Validation
- `entry_point_validate` will only normalise the spec path (and perhaps basic metadata checking); it will stop building a `ScenarioDemo` object.
- Tests will load pipeline specs directly and no longer fabricate scenario YAML files, simplifying fixtures.

## Migration Considerations
- Demo & test fixtures: remove `simkit/tests/fixtures/pipeline_scenario.yaml` usage; update tests to point directly at the spec.
- CLI / notebooks: ensure any helpers that previously expected scenario YAML now accept spec paths.

## Testing Strategy
- Adjust existing pytest suites (`test_pipeline_schema.py`, `test_pipeline_dag.py`, `test_pipeline.py`) to reflect metadata additions and scenario/flags removal.

## Open Questions
- Do we need a helper for cloning specs with tweaks (replacement for overrides)? Possibly a small script or make it out-of-scope.
- How should metadata defaults be expressed (e.g., pipeline version)? Possibly handled via plan documentation.
