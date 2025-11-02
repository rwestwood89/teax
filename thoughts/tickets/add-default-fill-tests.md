# Ticket: Add coverage for default-filling validation paths

**Created:** 2025-09-20 21:25 UTC
**Priority:** Medium
**Type:** Bug
**Status:** Open

## Overview

Extend module tests to assert that `validate_and_fill_default` injects defaults when optional inputs are omitted.

## Description

- Add tests for `RateDataModule`, `ConfigureBatteryModule`, and other modules where defaults are expected (e.g., missing timezone/currency, absent design prefs).
- Ensure the tests intentionally omit optional fields and confirm returned objects include defaults from `simkit/config/defaults.py`.
- Include negative assertions where defaults should not overwrite already provided values.
- Success criteria: new tests in `simkit/tests/` fail before change, pass after, and increase confidence in default-handling behavior.
