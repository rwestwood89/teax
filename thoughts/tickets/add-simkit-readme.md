# Ticket: Add simkit README for async demo modules

**Created:** 2025-09-20 21:25 UTC
**Priority:** Medium
**Type:** Design
**Status:** Open

## Overview

Document the async demo package with a README that explains module responsibilities, entry points, and how to run the pipeline/manual demos.

## Description

- Create `simkit/README.md` describing the package layout, module purposes, and links to pipeline/manual usage.
- Include instructions for running the async pipeline (`python -m simkit.core.pipeline` or tests) and the manual notebook workflow.
- Highlight where defaults, flags, and fixtures live to help new contributors.
- Success criteria: README exists at `simkit/README.md`, reviewed for clarity, and referenced sections align with current project structure.
- Should be as detailed as possible while keeping under 80 lines. 