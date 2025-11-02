# Spec: Synchronous Simulation Module Integration

**Document Type:** Specification
**Version:** v1.0
**Status:** Implementation In Progress
**Owner:** Reid W
**Last Updated:** 2025-09-23 17:38:06Z
**Related Docs:** tea_simulation_design_doc.md
**Related Ticket:** thoughts/tickets/synchronous-sim.md
**Current Branch Name:** synchronous_sim
**Current Commit:** dc2c35a428c2a6aa6abe9f92e26d7679f198a317

## Overview
Introduce a synchronous simulation wrapper that keeps forecasting, business-logic, and MATLAB-based dynamics components aligned while still fitting inside the existing asynchronous pipeline orchestration. This bridge enables scenario analysts to exercise the Simulink physics/control model using the same pipeline entry points that drive the rest of the toolkit.

## Problem Statement
The async pipeline cannot yet execute in-loop simulations that depend on MATLAB-hosted dynamics, blocking validation of guidance strategies that require tight coupling between forecast, decision logic, and physics. We need a functional module that hides the MATLAB integration details while delivering the typed inputs/outputs expected by the orchestration layer.

### Current State
Pipeline runs cover only async modules with Python-native implementations. No integration exists to spin up MATLAB Engine, call a Simulink model, or feed guidance from upstream logic into the physics loop. Testing of the physics/control model therefore happens in isolation, outside the pipeline.

### Desired Outcome
Operators can configure and invoke a `SynchronousSim` module through the pipeline, have it coordinate mock forecast, business logic, and MATLAB dynamics step-by-step, and receive typed outputs suitable for downstream modules or reporting. Failures in any subcomponent produce actionable errors rather than silent faults.

## Requirements
- The system SHALL WHEN the pipeline registry loads a module configuration referencing `synchronous_sim` THEN instantiate a `SynchronousSim` functional module that exposes `validate_and_fill_default` and `run` methods consistent with core module patterns.
- The system SHALL WHEN `validate_and_fill_default` executes THEN verify that time index, initial battery state, pricing data, and subcomponent configs are present, filling documented defaults where optional values are omitted.
- The system SHALL WHEN `run` executes with validated inputs THEN iterate the forecast, business-logic, and dynamics components in lockstep for each time-step, producing typed collections of forecasts, guidances, and telemetry.
- The system SHALL WHEN initializing the dynamics bridge THEN start MATLAB Engine using `DynamicSimConfig`, load the specified Simulink model, and expose a `step` interface returning telemetry objects per tick.
- The system SHALL WHEN any component raises during initialization or stepping THEN stop execution, annotate the failure with timestamp and component metadata, and raise a structured error for the pipeline orchestrator to capture.
- The system SHOULD WHEN operating in development or test contexts THEN allow injection of stub dynamics implementations so that tests can run without MATLAB installed.

## Acceptance Criteria
### Core Functionality
- [ ] The system SHALL expose a `SynchronousSim` module that the async pipeline can instantiate via the module registry with a config payload.
- [ ] WHEN `SynchronousSim.run` receives validated inputs THEN it SHALL iterate the forecast, business-logic, and dynamics components in-lockstep across the provided time index and return typed outputs (forecasts, guidances, telemetry).
- [ ] The system SHALL wrap MATLAB Engine startup and Simulink model loading behind a Python bridge that reads model identifiers and signal names from `DynamicSimConfig`.

### Edge Case Handling
- [ ] WHEN MATLAB Engine initialization fails or the configured model cannot be loaded THEN the system SHALL surface a structured exception that the pipeline can capture and log.
- [ ] WHEN any component raises during a time-step THEN the system SHALL halt the loop, record the failure context (timestamp, component), and propagate an error without returning partial outputs.

### Quality & Integration
- [ ] The system SHOULD provide lightweight stub implementations and configs for forecast and business-logic components suitable for integration tests.
- [ ] The system SHALL include an end-to-end integration test that exercises the module within the async pipeline using stubs/mocks for external dependencies.
- [ ] The system SHALL include unit or integration coverage demonstrating the module’s happy path and one failure path using the stubs (with MATLAB interactions mocked).

## Scope Boundaries
### In Scope
- Implementing the `SynchronousSim` module, including validation, orchestration loop, and typed outputs.
- Creating stub/mock components and configs for forecast and business logic to demonstrate the integration flow.
- Building the MATLAB Engine bridge class with configuration-driven model loading and per-step telemetry extraction.
- Adding automated tests (unit and end-to-end) that run without a real MATLAB installation by mocking the dynamics bridge.

### Out of Scope
- Delivering production-grade forecast or business-logic algorithms beyond simple stubs.
- Packaging or distributing MATLAB/Simulink assets or managing MATLAB licensing.
- Introducing advanced orchestration features such as sweep/optimization pipelines or async scheduling changes.
- Modeling exhaustive telemetry schemas beyond what is required to prove the integration pattern.

## Edge Cases & Considerations
- MATLAB Engine startup latency may affect pipeline timing; consider caching or fast-restart options in configuration.
- Configuration errors (bad paths, missing signals) should map to explicit validation messages before runtime when possible.
- Long-running simulations need guardrails on loop execution time; future work may require timeout controls.
- Telemetry data size could grow quickly; ensure outputs remain memory-manageable for hour-level runs.

## Success Criteria
Successful completion means analysts can run a pipeline scenario that invokes the synchronous sim module, observe forecast/guidance/telemetry outputs produced by the orchestrated loop, and see descriptive errors when the MATLAB bridge or subcomponents fail. Automated tests cover the happy path and a representative failure path without requiring MATLAB in CI.

## Status Tracking
Implementation plan: TBD.
Validation artifacts: TBD.
Linked tickets: thoughts/tickets/synchronous-sim.md.
