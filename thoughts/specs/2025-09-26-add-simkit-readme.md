# Spec: Add simkit README

**Document Type:** Specification
**Version:** v1.0
**Status:** Draft
**Owner:** Reid W
**Last Updated:** 2025-09-26
**Related Docs:** tea_simulation_design_doc.md
**Related Ticket:** thoughts/tickets/add-simkit-readme.md
**Current Branch Name:** ss_viz
**Current Commit:** 61a5a6d762b1f4f36af7d70f7a49fb7fa998d4d7

## Overview
Create a contributor-facing README inside `simkit/` that orients newcomers to the async demo package, explains module responsibilities, and describes how to run both the automated pipeline and manual notebook workflows without digging through source code.

## Problem Statement
New contributors struggle to understand how the async demo modules fit together and where to start when running simulations. Without consolidated documentation, they must reverse-engineer responsibilities from the codebase, slowing onboarding and increasing the risk of misuse.

### Current State
There is no README within `simkit/`. Contributors rely on sparse comments or the broader project README, which does not detail the async pipeline layout, execution commands, or supporting configuration locations.

### Desired Outcome
A concise, accurate README that introduces the async demo modules, points to the correct entry points, and guides contributors to supporting configuration, flags, and fixtures so they can run demos confidently.

## Requirements
- The system SHALL provide a `simkit/README.md` summarizing each top-level subpackage’s purpose and the role it plays in the async demo in no more than 80 lines.
- The system SHALL, WHEN orienting a contributor to run the async pipeline, describe the required command(s) and any environment prerequisites to execute the pipeline entry point successfully.
- The system SHALL, WHEN documenting manual workflows, reference the relevant notebooks under `notebooks/` and outline how to launch them for exploratory runs.
- The system SHALL, WHEN describing configuration support, highlight where defaults, feature flags, and fixtures reside so contributors can locate and extend them.
- The system SHALL ensure all referenced paths, filenames, and commands reflect the current repository structure at the time the README is merged.
- The system SHOULD include relative links to representative tests and notebooks that demonstrate pipeline and manual usage patterns for deeper exploration.

## Acceptance Criteria
### Core Functionality
- [ ] The system SHALL provide a `simkit/README.md` that summarizes each top-level subpackage’s purpose and responsibilities in under 80 lines.
- [ ] The system SHALL describe how to run the async pipeline using the documented entry-point command(s).
- [ ] WHEN a contributor reads the README THEN they can locate defaults, feature flags, and fixtures via explicit path references.

### Edge Case Handling
- [ ] The system SHALL call out the manual notebook workflow, including how to launch it or where to find instructions, even if notebooks require setup outside the README.
- [ ] WHEN referenced modules or files do not exist or are renamed THEN the README SHALL be updated to match the current structure (i.e., no stale paths or commands).

### Quality & Integration
- [ ] The system SHOULD include links or relative paths to the most relevant notebooks and tests for further exploration.
- [ ] The system SHALL pass a peer review for clarity and accuracy before the ticket closes.

## Scope Boundaries
### In Scope
- High-level descriptions of the async demo package layout, responsibilities, and usage patterns.
- Instructions for running the pipeline via CLI and for starting manual notebook explorations.
- References to configuration defaults, feature flags, and test fixtures supporting the async demos.

### Out of Scope
- Detailed API or parameter-level documentation for individual modules.
- Changes to code, tests, or notebooks; only documentation updates are required.
- Broader project documentation outside the `simkit/` package directory.

## Edge Cases & Considerations
- Ensure the README remains accurate if additional subpackages or modules are introduced; future updates must maintain the ≤80-line constraint.
- Call out any environment setup (e.g., virtualenv activation) that might block newcomers from running commands successfully.
- Highlight that notebooks may depend on local data or fixtures so readers verify availability before execution.

## Success Criteria
- README exists at `simkit/README.md`, passes review for clarity, and references current paths and commands.
- Contributors can run the async pipeline and locate manual notebook instructions without requesting additional guidance.
- Documentation remains within the 80-line requirement to keep the guide concise and scannable.

## Status Tracking
- Implementation Plan: pending
- Validation Evidence: pending
- Related Tickets: thoughts/tickets/add-simkit-readme.md
