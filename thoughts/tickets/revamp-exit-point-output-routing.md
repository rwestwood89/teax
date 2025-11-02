# Ticket: Redesign ExitPoint Output Routing

**Created:** 2025-09-22 08:39 PDT
**Priority:** High
**Type:** Design
**Status:** In Progress

## Overview
Align the `ExitPoint` module with the entry-point channel pattern by making outputs declarative (`<name>: <Class> <filename>`), introducing an output directory convention, and centralising output writers.

## Description
- Modify the pipeline schema so `ExitPoint` declares only outputs; each entry uses `<channel_name>: <Type> <filename>`.
- Introduce metadata defaults for `PYRONDO_OUTPUT_DIR` and optional run name prefix. Follow pattern used for input artifacts. 
- Generate a run folder per execution using the metadata run name (if provided) plus a short unique suffix.
- Add an output write router that maps type -> writer (`json`, `parquet`, etc.) and persists each channel to the declared filename inside the run folder. Follow similar pattern to `_ENTRY_LOADERS`. 
- Update executor to leverage the router; remove hardcoded calls in `execute_pipeline`.
- Document the new spec structure and runtime behaviour.
- Add tests covering run folder naming, file emission, and metadata overrides.

## Acceptance Criteria
- ExitPoint outputs follow the new `<Type> <filename>` pattern and are written via the router.
- Run folders are created with the expected naming convention and contain all declared artifacts.
- Updated plan/design/spec documents describe the new ExitPoint contract and metadata controls.
