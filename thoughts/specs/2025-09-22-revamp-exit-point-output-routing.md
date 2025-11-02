# Spec: Revamp ExitPoint Output Routing

**Document Type:** Specification
**Version:** v1.0
**Status:** Implementation In Progress
**Owner:** Reid W
**Last Updated:** 2025-09-22
**Related Docs:** tea_simulation_design_doc.md
**Related Ticket:** thoughts/tickets/revamp-exit-point-output-routing.md
**Current Branch Name:** dev
**Current Commit:** ff7724d5c7323e8f3a4958ed6d3ae1fa9727d036

## Overview
This feature introduces a declarative output contract for the ExitPoint module so that pipeline configurations explicitly describe emitted artifacts, and the executor can direct outputs to structured run folders with consistent metadata. Aligning ExitPoint with the entry-point channel pattern improves auditability, automation friendliness, and flexibility for downstream tooling.

## Problem Statement
ExitPoint currently writes artifacts through hardcoded logic inside the executor, which hides filenames and formats from configuration and prevents orchestration tooling from knowing what files a run will produce. Operators must infer artifact locations, making it difficult to automate post-processing, track outputs across runs, or override destinations at runtime.

### Current State
- Pipeline schemas let EntryPoint inputs declare named channels, but ExitPoint outputs are still imperative code paths.
- Writers are invoked directly in `execute_pipeline`, mixing orchestration control flow with IO concerns.
- Output folders are not tied to run metadata, yielding ad hoc directory structures that downstream systems cannot predict.

### Desired Outcome
- Pipeline authors declare ExitPoint outputs using the `<channel_name>: <Type> <filename>` syntax parallel to entry-point inputs.
- A run folder, scoped by metadata and unique suffix, encapsulates all artifacts for a single execution.
- The executor routes each declared output through centralized writers and records a manifest summarizing the run outputs and metadata, enabling deterministic downstream integration.
- Pipeline execution returns a structured run result that exposes the manifest plus the produced exit-channel payloads, without assuming a fixed bundle shape.

## Requirements
- The system SHALL validate ExitPoint configuration entries so that each output channel is expressed as `<channel_name>: <Type> <filename>` and reject configurations that do not conform before runtime.
- The system SHALL ensure each declared ExitPoint channel corresponds to an upstream-produced channel and fail validation if a referenced channel is absent.
- WHEN the executor initializes a run THEN the system SHALL resolve the effective output directory using `PYRONDO_OUTPUT_DIR`, applying metadata overrides consistent with entry-point handling.
- WHEN a run name is supplied via metadata THEN the system SHALL create a run folder under the resolved output directory using `<run-name>-<short-id>`; otherwise it SHALL use a default deterministic base name combined with the short ID.
- The system SHALL register output writers keyed by `Type` (starting with `json` and `parquet`) and fail fast if a declared type lacks a registered writer.
- WHEN the pipeline emits outputs THEN the system SHALL invoke the matching writer for each channel, persisting the artifact to the declared filename within the run folder.
- AFTER writing all artifacts THEN the system SHALL produce a JSON manifest inside the run folder that enumerates the emitted files, their relative paths, declared types, and the metadata context applied during execution.
- The manifest SHALL record each artifact as `{channel, type_name, relative_path, produced}` and store run metadata (run name, short id, output directory, pipeline metadata snapshot).
- The system SHOULD generate short IDs that are unique per executor invocation to avoid run folder collisions within the same output directory.

## Acceptance Criteria
### Core Functionality
- [ ] The system SHALL require every ExitPoint output declaration to follow `<channel_name>: <Type> <filename>` and reject invalid schemas.
- [ ] The system SHALL resolve `PYRONDO_OUTPUT_DIR` (respecting metadata overrides) and create a run folder named `<run-name>-<short-id>` for each execution.
- [ ] WHEN the pipeline runs THEN the executor SHALL route each declared output through the type→writer router and persist the artifact to the declared filename inside the run folder.
- [ ] The system SHALL emit a JSON metadata manifest in the run folder describing all written files and the metadata context.

### Edge Case Handling
- [ ] WHEN `PYRONDO_OUTPUT_DIR` is missing THEN the system SHALL fall back to the default output directory without failing.
- [ ] WHEN a declared `Type` has no registered writer THEN the system SHALL fail before execution starts with a descriptive error.
- [ ] WHEN two outputs declare the same filename THEN the system SHALL fail validation before writing any files.

### Quality & Integration
- [ ] The system SHOULD ensure run-folder short IDs are unique per process invocation to prevent collisions.
- [ ] The system SHALL be covered by automated tests for run folder naming, content routing, metadata overrides, and manifest emission.

## Scope Boundaries
### In Scope
- Updating ExitPoint schema validation and related config parsing to require declarative output entries.
- Implementing the output router with `json` and `parquet` writers and integrating it into the executor.
- Managing run folder creation, metadata override resolution, and manifest generation.

### Out of Scope
- Supporting additional output formats beyond `json` and `parquet`.
- Providing backward compatibility with legacy ExitPoint configurations.
- Enhancing downstream consumers; they will adapt once artifacts become declarative.

## Edge Cases & Considerations
- Multiple pipeline runs may target the same output directory; ensure short IDs avoid collisions while keeping paths human-readable.
- Validation must detect duplicate filenames to prevent accidental overwrites.
- Manifests should account for optional outputs (e.g., conditionally produced channels) by recording absence explicitly if required for audits.
- Consider logging the resolved output path and manifest location for observability.

## Success Criteria
- Pipeline authors can statically determine all artifacts produced by a run from the ExitPoint configuration and manifest.
- Automated tests confirm run folder naming, routing logic, metadata overrides, and manifest content across positive and negative scenarios.
- Execution logs and manifests provide enough information for downstream systems to ingest outputs without inspecting code.

## Status Tracking
- Implementation Plan: _TBD_
- Validation Reports: _TBD_
- Related Tickets: thoughts/tickets/revamp-exit-point-output-routing.md
