# Spec: Support PYRONDO_INPUT_DIR for Entry Artifact Resolution

**Document Type:** Specification
**Version:** v1.0
**Status:** Complete
**Owner:** Reid W
**Last Updated:** 2025-09-22
**Related Docs:** tea_simulation_design_doc.md
**Related Ticket:** thoughts/tickets/add-input-dir-env.md
**Current Branch Name:** dev
**Current Commit:** 4e417edbee39fa2ad4491ad25458e1ab817aa4f8

## Overview
Pipeline specifications currently rely on literal file paths for entry artifacts. Adding `PYRONDO_INPUT_DIR` support enables reusable fixtures and environment-specific layouts by allowing artifact paths to resolve against a shared input directory while retaining backwards compatibility with literal references.

## Problem Statement
Simulation pipeline configs must reference external artifacts such as geography, financial parameters, and load profiles. Today, these paths must match each developer or CI environment perfectly because only literal resolution is supported. Teams resort to copying fixtures or editing configs, increasing setup friction and introducing drift between environments.

### Current State
The entry loader resolves artifact paths exactly as written. Relative paths are interpreted against the spec location or current working directory, but there is no standardized lookup for shared fixture roots, and `.env` files are not loaded automatically.

### Desired Outcome
Pipeline specs can reference artifacts relative to a shared input directory without editing YAML per environment. The system loads environment variables from the project `.env` file, uses `PYRONDO_INPUT_DIR` when provided, falls back to `run_data/inputs` when absent, and clearly communicates when resolution fails after both attempts.

## Requirements
WHEN the pipeline executor initializes entry artifacts, THEN the system SHALL call `loadenv()` so environment variables from the project `.env` file are available.
The system SHALL treat the literal artifact path exactly as provided, supporting absolute paths and paths relative to the pipeline spec directory.
WHEN the literal path cannot be found, THEN the system SHALL construct a candidate path by prefixing the artifact path with `PYRONDO_INPUT_DIR` and attempt to load the artifact from that location.
WHEN `PYRONDO_INPUT_DIR` is not defined in the environment, THEN the system SHALL default it to `<project-root>/run_data/inputs` before attempting the prefix fallback.
WHEN neither the literal nor `PYRONDO_INPUT_DIR`-prefixed paths resolve to an existing artifact, THEN the system SHALL raise a validation error that enumerates both attempted locations.
The system SHALL record the chosen artifact path for provenance and diagnostics in the pipeline execution context.

## Acceptance Criteria
### Core Functionality
- [x] The system SHALL invoke `loadenv()` so environment variables from a project-root `.env` file are loaded before resolving entry artifacts.
- [x] The system SHALL resolve each entry artifact by first evaluating the literal path and returning the artifact when it exists.
- [x] WHEN the literal path does not exist THEN the system SHALL resolve the artifact by prefixing the path with `PYRONDO_INPUT_DIR` and return it when found.

### Edge Case Handling
- [x] WHEN both the literal and `PYRONDO_INPUT_DIR`-prefixed paths fail to resolve THEN the system SHALL raise a validation error that lists both attempted locations.
- [x] WHEN `PYRONDO_INPUT_DIR` is unset in the environment THEN the system SHALL default it to `<project-root>/run_data/inputs` before the fallback is attempted.

### Quality & Integration
- [x] The system SHOULD cover literal-path success, `PYRONDO_INPUT_DIR` fallback success, and dual-failure scenarios with automated tests.
- [x] The system SHALL document the lookup order and default `PYRONDO_INPUT_DIR` in the pipeline spec or developer docs.

## Scope Boundaries
### In Scope
- Adjusting entry artifact resolution logic to incorporate `loadenv()` and `PYRONDO_INPUT_DIR` fallback.
- Adding automated tests that exercise literal paths, fallback success, and failure messaging.
- Documenting the lookup order and default behaviour for contributors.

### Out of Scope
- Changing how non-entry artifacts or downstream modules resolve resources.
- Handling multiple input directories or remote storage backends.
- Introducing dynamic runtime discovery of `.env` files beyond the project root convention.

## Edge Cases & Considerations
- Developers may run pipelines from different working directories; resolution must anchor relative paths to the spec file while using project root for defaults.
- Environments without a `.env` file should still operate correctly using the default `run_data/inputs` directory.
- Error messaging should be actionable, listing the attempted absolute paths so users can diagnose missing fixtures quickly.

## Success Criteria
- Local and CI runs can execute pipelines referencing shared fixtures without editing YAML paths.
- Automated tests confirm literal and fallback path handling and verify failure messaging.
- Documentation clearly instructs contributors on setting `PYRONDO_INPUT_DIR` via `.env` and the default location when it is absent.

## Status Tracking
- Implementation Plan: Implemented in `SerialPipelineExecutor`, with env helper and tests.
- Validation Results: `python -m pytest` (all tests passed on developer machine).
- Ticket: thoughts/tickets/add-input-dir-env.md
