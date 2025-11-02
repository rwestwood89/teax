# Ticket: Enrich pipeline provenance with runtime metadata

**Created:** 2025-09-20 21:25 UTC
**Priority:** Medium
**Type:** Design
**Status:** Open

## Overview

Enhance the pipeline provenance payload to include dependency versions and runtime metadata promised in the demo plan.

## Description

- Update `simkit/core/pipeline.py` to capture library versions (e.g., numpy, pandas, pydantic) and Python runtime info when composing `schema.Provenance`.
- Persist the richer provenance into the `provenance.json` artifact and ensure schema/doc updates cover new fields.
- Add tests validating the presence of the new metadata and adjust fixtures/notebook output expectations accordingly.
- Success criteria: provenance payload includes config hash, feature flags, module versions, dependency versions, and runtime stamps, with tests covering the additions.
