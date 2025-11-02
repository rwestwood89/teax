# Repository Guidelines

## Project Structure & Module Organization
Package logic lives in `simkit/`. 
- `simkit/core/` holds the async pipeline modules (rate data, battery config, performance simulation, cost, project analysis). 
 - Shared configuration helpers live in `simkit/config/`
 - IO adapters and serializers sit in `simkit/io/`. 
 - Tests mirror the package under `simkit/tests/`, with reusable fixtures in `simkit/tests/fixtures/`. 
Exploratory work and scenario walkthroughs are kept in `notebooks/`, 
Partner notes reside in `thoughts/`.
Read `tea_simulation_design_doc.md` in FULL for project intent and implementation details.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — create an isolated environment.
- `pip install -e .[dev]` — install the package plus pytest for local development.
- `pytest` — run the full suite; defaults route through `simkit/tests/` with `-q` for concise output.
- `pytest simkit/tests/test_pipeline.py -k happy_path` — target a specific scenario when iterating on the pipeline.

## Coding Style & Naming Conventions
Write Python 3.10+ with 4-space indentation, `black`-compatible formatting, and lint-friendly imports. Use type hints and dataclasses/Pydantic models to describe data payloads, mirroring patterns in `simkit/config/schema.py`. Module names stay lowercase with underscores; classes remain PascalCase (see `ProjectAnalyzerModule`), and test functions follow `test_*` naming.

## Testing Guidelines
Pytest drives validation via fixtures that build demo payloads; extend fixtures instead of hard-coding values inside tests. When adding modules, shadow their usage with unit tests under `simkit/tests/` that replicate the package folder structure. Include negative-path cases for validators (e.g., raising on missing config) and record any new datasets in `simkit/tests/fixtures/`. Run `pytest` before opening a PR and call out any expected failures.

## Commit & Pull Request Guidelines
Follow short, imperative commit subjects (`Add pipeline guardrails`). Batch related changes together and document rationale in the body when touching multiple modules. PRs should link relevant tickets, summarise behavioural impact, list test evidence (command output snippets), and attach config or result artifacts when changes affect IO bindings.

## Configuration & Data Fixtures
Scenario defaults and feature flags live in `simkit/config/`; prefer extending `defaults.py` or `flags.py` rather than inlining constants. Load profiles for demos should be stored alongside tests and referenced with relative paths so `entry_point_validate` continues to resolve fixtures during automation.
