# Plan: ExitPoint Persistence Contract

**Status:** Certified (audit 2026-07-12) — pre-PR fusion-tea verification pending
**Approved scope:** All phases, 2026-07-11

## Phase 1: Default persistence handlers

- [x] Add tests for all eight scalar handler names, exact JSON bytes, wrapped/bare identity, falsy values, and extension enforcement.
- [x] Add tests that automatic custom-schema registration preserves default handlers while direct registration remains an override.
- [x] Register the four bare scalar names and four `RootModel` names in the default router.
- [x] Preserve existing handlers in `create_output_router_with_json_schemas()`.

## Phase 2: ExitPoint type validation

- [x] Add tests for truthful exit bindings, bare/wrapped mismatches, and unresolved producer types.
- [x] Add an executor-level test proving unknown exit types fail before module execution.
- [x] Cross-check each resolvable producer channel type against the ExitPoint declaration.

## Phase 3: End-to-end coverage and documentation

- [x] Add a defaults-only pipeline covering four bare scalars and one wrapped scalar.
- [x] Assert exact artifacts and manifest production records.
- [x] Document the ExitPoint persistence contract and update `CLAUDE.md` guidance.
- [x] Run focused and full validation.
- [x] Synchronize the spec and current-work status.

## Implementation Notes

Completion notes will be added as each phase finishes.

### Phase 1 Completion

**Completed:** 2026-07-11

**Changes Made:**

- Added the eight scalar handlers to `simkit/io/output_router.py` using the two existing JSON writers.
- Changed convenience registration to preserve every handler already supplied by the default router.
- Added real write-path tests for exact bytes, wrapped/bare identity, falsy values, extension enforcement, and override policy.

**Issues Encountered:**

- The shell had no `pytest`; validation uses the spike-proven `uv run --no-project` environment.

**Deviations from Plan:** None.

### Phase 2 Completion

**Completed:** 2026-07-11

**Changes Made:**

- Passed the existing channel-type map into ExitPoint validation.
- Added a focused type-contract check after handler validation, preserving the existing unknown-handler error.
- Added truthful, mismatch, unresolved-type, and executor fail-fast tests in `test_pipeline_validator_exit.py`.

**Issues Encountered:** None.

**Deviations from Plan:** None.

### Phase 3 Completion

**Completed:** 2026-07-11

**Changes Made:**

- Added a defaults-only scalar pipeline fixture, a focused toy module, and exact artifact/manifest assertions.
- Documented default scalar persistence, explicit-router ownership, `None`, EntryPoint, and type-mismatch boundaries.
- Corrected the battery integration fixture's five ExitPoint declarations to match its actual `RootModel` channels and registered those wrappers in the test harness.
- Updated the spec, design, backlog ticket, and current-work status.

**Issues Encountered:**

- Full suite: 208 passed, 4 pre-existing failures in `test_no_battery_deps.py`; each hard-codes the absent checkout path `/home/reid/teax`.
- The final fusion-tea workaround-free reproduction remains assigned to pre-PR, as specified by the design.

**Deviations from Plan:**

- The scalar toy module lives in `tests/core/toy_scalar_module.py` instead of the existing CRLF `toy_modules.py`, avoiding unrelated line-ending churn.
