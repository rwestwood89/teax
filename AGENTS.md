# Repository Guidelines

## Project Structure & Module Organization

The repository contains two packages in `packages/`:

**teax-simkit** (`packages/teax-simkit/simkit/`): Core simulation framework
- `simkit/core/` - Pipeline orchestration, module base classes, registry
- `simkit/config/` - Generic schemas, pipeline configuration
- `simkit/io/` - I/O adapters and serializers
- `simkit/evaluation/` - Sealed-package loading and single-case evaluation (see `docs/evaluation-and-study.md`)
- `simkit/study/` - Grid search over an evaluator, crash-safe persistence, `teax-study` CLI (see `docs/evaluation-and-study.md`)
- `simkit/tests/` - Framework tests

**battery-tea-demo** (`packages/battery-tea-demo/battery_tea/`): Example implementation
- `battery_tea/modules/` - Battery TEA modules (rate data, battery config, etc.)
- `battery_tea/schemas.py` - Battery-specific Pydantic models
- `battery_tea/tests/` - Battery module tests
- `battery_tea/notebooks/` - Jupyter demos

Partner notes reside in `thoughts/`.
Read `tea_simulation_design_doc.md` in FULL for project intent and implementation details.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — create an isolated environment.
- `pip install -e packages/teax-simkit[dev] && pip install -e packages/battery-tea-demo[dev]` — install packages for local development.
- `pytest` — run the full suite for both packages.
- `pytest packages/teax-simkit/` — run framework tests only.
- `pytest packages/battery-tea-demo/` — run battery demo tests only.

## Coding Style & Naming Conventions
Write Python 3.10+ with 4-space indentation, `black`-compatible formatting, and lint-friendly imports. Use type hints and dataclasses/Pydantic models to describe data payloads, mirroring patterns in `simkit/config/schema.py`. Module names stay lowercase with underscores; classes remain PascalCase (see `ProjectAnalyzerModule`), and test functions follow `test_*` naming.

## Testing Guidelines
Pytest drives validation via fixtures that build demo payloads; extend fixtures instead of hard-coding values inside tests. Framework tests go in `packages/teax-simkit/simkit/tests/`. Domain module tests go in `packages/battery-tea-demo/battery_tea/tests/`. Include negative-path cases for validators and record new datasets in the appropriate fixtures directory. Run `pytest` before opening a PR.

## Commit & Pull Request Guidelines
Follow short, imperative commit subjects (`Add pipeline guardrails`). Batch related changes together and document rationale in the body when touching multiple modules. PRs should link relevant tickets, summarise behavioural impact, list test evidence (command output snippets), and attach config or result artifacts when changes affect IO bindings.

## Configuration & Data Fixtures
Generic framework defaults and flags live in `packages/teax-simkit/simkit/config/`. Domain-specific defaults (e.g., battery parameters) live in the domain package (e.g., `packages/battery-tea-demo/battery_tea/defaults.py`). Test fixtures are stored in each package's test directory.
