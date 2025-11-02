# Ticket: Support PYRONDO_INPUT_DIR for Entry Artifact Resolution

**Created:** 2025-09-22 08:39 PDT
**Priority:** Medium
**Type:** Design
**Status:** Closed

## Overview
Add support for resolving entry-point artifact paths via an `PYRONDO_INPUT_DIR` environment variable so pipeline specs can reference shared fixture roots without embedding absolute paths.

## Description
- Update the executor entry loader to resolve artifacts by (1) attempting the provided path verbatim (absolute paths, `./`, `../`, `~/`), and (2) if not found, prefixing the path with the configured `PYRONDO_INPUT_DIR`.
- Accept `PYRONDO_INPUT_DIR` from environment (with a sensible default, e.g., cwd) and document the behaviour.
- Add tests covering relative paths plus `PYRONDO_INPUT_DIR` fallback.
- Ensure spec validation errors surface clear messages when neither resolution succeeds.

## Acceptance Criteria
- Entry artifact loading supports the fallback order described above.
- Tests demonstrate both direct and `PYRONDO_INPUT_DIR`-prefixed paths.
- Documentation (plan/design/spec) updated to mention `PYRONDO_INPUT_DIR` usage.
