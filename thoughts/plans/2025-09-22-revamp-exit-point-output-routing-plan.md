# Revamp ExitPoint Output Routing Implementation Plan

**Document Type:** Implementation Plan
**Version:** v1.0
**Status:** Implementation In Progress
**Owner:** Reid W
**Last Updated:** 2025-09-22 14:23:30 PDT
**Related Docs:** tea_simulation_design_doc.md, thoughts/specs/2025-09-22-revamp-exit-point-output-routing.md
**Current Branch Name:** dev
**Current Commit:** ff7724d5c7323e8f3a4958ed6d3ae1fa9727d036

## Overview
Introduce a declarative output contract for ExitPoint modules so pipeline configs own artifact naming, the executor routes outputs through type-specific writers into structured run folders, and every run emits a manifest capturing delivered files plus metadata. Plan doubles as lightweight design, detailing schema updates, routing layer, and executor integration required to satisfy the spec.

**Source Documents:**
- **Spec:** `thoughts/specs/2025-09-22-revamp-exit-point-output-routing.md`
- **Design:** _(embedded in this plan; no separate design document provided)_

## Implementation Strategy
Adopt a three-phase rollout: (1) extend pipeline schema/validation with new ExitPoint output syntax using the golden fixture to lock expectations, (2) build output-routing infrastructure (writer registry, run-folder resolver, manifest models), and (3) integrate the executor to honor declared outputs, write artifacts, and emit manifests with full test coverage.

## Phase 1: Exit Schema & Validation Update

### Overview
Update the golden pipeline YAML and schema layer so ExitPoint outputs declare `<channel>: <Type> <filename>`, enforce filename uniqueness, and surface filename metadata for downstream routing.

### Test Stencil
```python
# Test/usage stencil for Phase 1 - write this first
def test_exit_point_outputs_parse_with_filenames(sample_pipeline_spec):
    spec = build_pipeline_spec(sample_pipeline_spec)
    exit_outputs = spec.modules["exit_point"].outputs
    rate_binding = exit_outputs["rate_info"]
    assert rate_binding.type_name == "RateInfo"
    assert rate_binding.channel_name == "rate_info"
    assert rate_binding.destination_filename == "rate_info.json"
```

### Changes Required

#### 1. Golden Pipeline Fixture
**File:** `simkit/tests/fixtures/pipeline_configs/demo_linear_alt.yaml`
**Changes:**
- [x] Convert `exit_point.outputs` to declare filenames (e.g., `rate_info: RateInfo rate_info.json`).
- [x] Add multiple channels for each ExitPoint artifact mirroring executor outputs (e.g., `telemetry: BatteryTelemetry8760 telemetry.parquet`).
- [ ] Annotate comments if needed to clarify new syntax for maintainers.

```yaml
  exit_point:
    module_type: ExitPoint
    outputs:
      rate_info: RateInfo rate_info.json
      battery_config: BatteryConfig battery_config.json
      cost_breakdown: CostBreakdown cost_breakdown.json
      telemetry: BatteryTelemetry8760 telemetry.parquet
      financial_results: FinancialResults financial_results.json
```

#### 2. Schema Data Model Enhancements
**File:** `simkit/config/pipeline_schema.py`
**Changes:**
- [x] Extend `PipelineChannelBinding` with a `destination_filename: str | None` field for ExitPoint outputs.
- [x] Update `_parse_module` to detect ExitPoint modules and parse outputs as `<Type> <filename>`; ensure filename stored on binding.
- [x] Enhance `_parse_outputs` to validate filenames (non-empty, no path traversal) and maintain backward compatibility for non-exit modules.
- [x] Enforce uniqueness of `destination_filename` across ExitPoint outputs during module parsing.

```python
if module_type == "ExitPoint":
    outputs = _parse_exit_outputs(module_key, raw_outputs)
```

#### 3. Validation Rules
**File:** `simkit/core/pipeline_validator.py`
**Changes:**
- [x] Adjust `_validate_outputs` to skip filename equality checks for exit modules while still enforcing type alignment.
- [x] Add dedicated ExitPoint validation ensuring every declared channel has a filename and the registry descriptor still matches expected output fields.

```python
if module.is_exit:
    _validate_exit_outputs(module)
    return
```

#### 4. Schema & Validator Tests
**Files:** `simkit/tests/pipeline/test_pipeline_schema.py`, `simkit/tests/pipeline/test_pipeline_dag.py`
**Changes:**
- [x] Update fixtures/assertions to expect new filenames on ExitPoint bindings.
- [x] Add regression tests covering duplicate filenames and malformed exit output syntax.
- [x] Ensure non-exit modules continue to parse without filenames.

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/pipeline/test_pipeline_schema.py -k exit_point`
- [x] `pytest simkit/tests/pipeline/test_pipeline_dag.py -k exit`
- [x] `pytest simkit/tests/test_pipeline.py::test_execute_pipeline_end_to_end` (ensures fixture still valid)

#### Manual Verification:
- [x] Inspect `demo_linear_alt.yaml` to confirm filenames align with intended artifacts.
- [x] Confirm failure message when two exit outputs use identical filenames.
- [ ] Verify docs/comments communicate new syntax expectations.

## Implementation Notes - Phase 1
**Completed:** 2025-09-22 17:00 PDT
**Changes Made:**
- Updated `simkit/tests/fixtures/pipeline_configs/demo_linear_alt.yaml` so ExitPoint declares only filename-bearing outputs for upstream channels (`rate_info`, `battery_config`, `cost_breakdown`, `telemetry`, `financial_results`).
- Extended `simkit/config/pipeline_schema.py` to capture `destination_filename`, enforce that ExitPoint outputs reference known upstream channels, and keep channel providers limited to entry/processing modules.
- Added ExitPoint-specific validation in `simkit/core/pipeline_validator.py` and ensured schema types resolve while guarding against duplicate filenames.
- Adjusted `simkit/core/pipeline_graph.py` so ExitPoint outputs introduce dependencies on their channel providers without registering new channels, preserving execution order.
- Updated `simkit/core/pipeline_executor.py` to collect ExitPoint outputs directly from the channel map, and refreshed pipeline schema/DAG tests to cover filename parsing, duplicate detection, missing channel failures, and validator behavior.

**Issues Encountered:**
- ExitPoint outputs initially reused upstream channel names, triggering duplicate-provider errors and allowing the exit module to sort before producers until the parser, validator, and graph builder coordinated on explicit provider checks and dependencies.

**Deviations from Plan:**
- Added explicit dependency wiring in `PipelineGraph` for ExitPoint outputs so the exit module still executes last; the original plan did not anticipate this control-flow adjustment.

---

## Phase 2: Output Routing Infrastructure

### Overview
Create the runtime components that resolve run folders, register type-based writers (`json`, `parquet`), generate unique short IDs, and assemble manifests describing generated artifacts.

### Test Stencil
```python
# Test/usage stencil for Phase 2 - write this first
def test_output_router_writes_artifacts_and_manifest(tmp_path, router, exit_bindings, payload):
    result = router.write_outputs(exit_bindings, payload, base_output_dir=tmp_path)
    assert result.manifest_path.exists()
    assert (result.run_dir / "telemetry.parquet").exists()
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["artifacts"][0]["type"] == "BatteryTelemetry8760"
```

### Changes Required

#### 1. Manifest Models
**File:** `simkit/config/schema.py`
**Changes:**
- [x] Introduce `RunArtifactRecord` and `RunManifest` Pydantic models capturing filename, type, channel, and metadata context.
- [x] Decouple run summarization from the legacy `PipelineResult` bundle in favor of manifests and channel payloads.

```python
class RunArtifactRecord(StrictBaseModel):
    channel: str
    type_name: str
    relative_path: str
```

#### 2. Writer Registry & Router Implementation
**Files:** `simkit/io/output_router.py` (new), `simkit/io/__init__.py`
**Changes:**
- [x] Create `OutputRouter` class encapsulating writer registry and run-folder resolution logic.
- [x] Register `json` and `parquet` writers mapping schema types to persistence functions (`write_json_model`, `write_parquet_telemetry`).
- [x] Implement manifest emission returning `RunManifest` instance and path.
- [x] Expose router entry points through `simkit/io/__init__.py` for easy import.

```python
router = OutputRouter(
    writers={
        "json": WriteHandler(fn=writers.write_json_model, extension=".json"),
        "parquet": WriteHandler(fn=writers.write_parquet_telemetry, extension=".parquet"),
    }
)
```

#### 3. Environment Helper
**File:** `simkit/config/environment.py`
**Changes:**
- [x] Add `resolve_output_dir(preferred: Path | None = None)` that mirrors input-dir override behavior using `PYRONDO_OUTPUT_DIR`.
- [x] Include optional `run_name` handling consistent with metadata spec.

#### 4. Utility Functions
**File:** `simkit/io/writers.py`
**Changes:**
- [x] Provide generic `write_json_payload` helper reused by manifest writing.
- [x] Ensure telemetry writer remains accessible for router registration.

#### 5. Router Unit Tests
**Files:** `simkit/tests/io/test_output_router.py` (new), `simkit/tests/fixtures/__init__.py`
**Changes:**
- [x] Add fixtures for sample exit bindings and payload data structures.
- [x] Test short ID generation, directory creation, and manifest structure.
- [x] Cover error paths: missing writer type, duplicate filenames, unsupported schema types.

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/io/test_output_router.py`
- [x] `pytest simkit/tests/config/test_environment.py -k output_dir`
- [x] `pytest simkit/tests -k "manifest or router"`

#### Manual Verification:
- [x] Execute router in REPL to confirm directories structure `<run-name>-<short-id>/artifact`.
- [x] Inspect generated manifest JSON for expected keys (`artifacts`, `metadata`).
- [x] Validate short IDs reset between processes but remain unique per invocation.

## Implementation Notes - Phase 2
**Completed:** 2025-09-22 17:25 PDT
**Changes Made:**
- Added `RunArtifactRecord`/`RunManifest` models and removed the legacy `PipelineResult` bundle so manifests plus exit-channel payloads describe run outputs (`simkit/config/schema.py:203`).
- Implemented `OutputRouter` with default type handlers, manifest emission, and exported helpers (`simkit/io/output_router.py:16`, `simkit/io/__init__.py:1`).
- Introduced `resolve_output_dir` and accompanying `OutputDirResolution` to normalize run names and honor `PYRONDO_OUTPUT_DIR` (`simkit/config/environment.py:9`, `simkit/config/environment.py:39`).
- Added `write_json_payload` plus router-focused fixtures and tests covering success and failure paths (`simkit/io/writers.py:15`, `simkit/tests/fixtures/__init__.py:5`, `simkit/tests/io/test_output_router.py:1`).
- Created dedicated config tests for output-directory resolution and verified manifest-focused pytest targets.

**Issues Encountered:**
- Pydantic rejected early attempts to embed `PipelineMetadata` due to import cycles with `pipeline_schema`; resolved by storing manifest metadata as a plain dictionary.
- Ensuring run-name sanitization stayed consistent required moving normalization into `environment.resolve_output_dir` so both router and future executor logic share the same utility.

**Deviations from Plan:**
- Manifest metadata is persisted as a generic mapping rather than the pipeline schema model to avoid circular imports while still capturing run context.
- Added extension validation for writers during routing to fail fast when filenames do not match registered handlers.

---

## Phase 3: Executor & E2E Integration

### Overview
Wire the output router into the pipeline executor so declared outputs drive artifact writing, manifests record run metadata, and legacy hardcoded writers are removed without altering return values.

### Test Stencil
```python
# Test/usage stencil for Phase 3 - write this first
def test_execute_pipeline_emits_manifest(tmp_path, sample_spec_path):
    result = execute_pipeline(sample_spec_path, tmp_path)
    run_dir = next(tmp_path.glob("demo-linear-*.json"), None)
    manifest = json.loads(run_dir.joinpath("manifest.json").read_text())
    assert manifest["metadata"]["run_name"] == "pipeline_result_bundle"
```

### Changes Required

#### 1. Executor Integration
**File:** `simkit/core/pipeline_executor.py`
**Changes:**
- [x] Pass ExitPoint binding metadata (channel→filename) to new router instead of returning raw channel map.
- [x] Add support for optional outputs (skip writing if channel absent) noting manifest record.
- [x] Surface errors when declared type lacks writer before run begins.

#### 2. Pipeline Entrypoint Adjustments
**File:** `simkit/core/pipeline.py`
**Changes:**
- [x] Update `execute_pipeline` to resolve run folder via `resolve_output_dir` and `OutputRouter` results.
- [x] Remove direct file writes in favor of router invocation.
- [x] Return the executor's `RunResult`, enriched with metadata/provenance, instead of the legacy bundle.
- [ ] Log or debug print resolved run dir and manifest path for observability (optional).

#### 3. Manifest Persistence
**File:** `simkit/io/output_router.py`
**Changes:**
- [x] After writing all artifacts, materialize manifest JSON (likely `manifest.json`) in run folder.
- [x] Provide method returning manifest path for tests.

#### 4. Integration Tests
**Files:** `simkit/tests/test_pipeline.py`, `simkit/tests/core/test_pipeline_executor_entry.py`
**Changes:**
- [x] Extend `test_execute_pipeline_end_to_end` to assert run folder naming and manifest existence.
- [x] Add tests covering missing writer type failure and duplicate filenames rejection.
- [x] Introduce fixture to set `PYRONDO_OUTPUT_DIR` and verify override behavior.

### Success Criteria
#### Automated Verification:
- [x] `pytest simkit/tests/test_pipeline.py`
- [x] `pytest simkit/tests/core/test_pipeline_executor_entry.py`
- [x] `pytest simkit/tests -k manifest`

#### Manual Verification:
- [x] Run pipeline from CLI, inspect run folder structure and manifest contents.
- [x] Confirm executor error when unsupported output type declared.
- [x] Validate exit module can skip optional outputs without crash (if spec demands).

## Implementation Notes - Phase 3
**Completed:** 2025-09-22 21:30 PDT
**Changes Made:**
- Injected the output router into `SerialPipelineExecutor`, ensuring handlers exist up front and recording optional outputs without writing files (`simkit/core/pipeline_executor.py:31`).
- Swapped `execute_pipeline` over to the router-based flow, returning an enriched `RunResult` with manifests while honoring env-driven output directories (`simkit/core/pipeline.py:85`).
- Extended the router to track `produced` status, accept metadata payloads, and expose handler introspection, with schema updates to persist manifest details (`simkit/io/output_router.py:18`, `simkit/config/schema.py:209`).
- Refreshed pipeline, executor, and router tests to validate manifest contents, handler failures, optional-channel behavior, and environment overrides (`simkit/tests/test_pipeline.py:12`, `simkit/tests/io/test_output_router.py:19`, `simkit/tests/core/test_pipeline_executor_entry.py:137`).

**Issues Encountered:**
- Optional ExitPoint bindings lack explicit flags, so router treats missing channel values as optional artifacts; schema now records `produced=False` entries to document omissions.
- Pydantic recursion surfaced again when embedding pipeline metadata in manifests; resolved by serializing to a plain dictionary before persistence.

**Deviations from Plan:**
- `execute_pipeline` now accepts `output_dir=None` to leverage environment overrides directly, aligning executor and manual workflows.
- Added router-level checks for filename collisions post-sanitisation to guard optional outputs even when no file is written.

---

## Testing Strategy
### Unit Tests
- Output router behaviors (writer dispatch, manifest schema, error handling).
- Pipeline schema parsing for ExitPoint filenames and duplicate detection.
- Environment helper for output directory resolution and run-name derivation.

### Integration Tests
- End-to-end pipeline execution verifying run folder naming, manifest contents, and artifact persistence.
- Executor failure scenarios (missing writer, duplicate filenames) to ensure fail-fast behavior.

### Manual Testing Steps
1. Run `pytest simkit/tests/test_pipeline.py -k end_to_end` to populate a run folder.
2. Inspect generated manifest and artifacts under the resolved `PYRONDO_OUTPUT_DIR`.
3. Manually alter config to declare unknown writer type, verify descriptive failure at load time.

## Risk Management
### Identified Risks
- **Schema Drift:** Changing `PipelineChannelBinding` may affect many modules (medium likelihood).
  - *Mitigation*: Provide compatibility fallback path, update all schema tests.
  - *Rollback*: Revert binding field addition and keep filenames optional until routing ready.
- **Writer Coverage Gaps:** Exit outputs might reference schema types without writers (high likelihood early on).
  - *Mitigation*: Implement validation that checks `PipelineModuleRegistry` outputs against writer registry before execution.
  - *Rollback*: Temporarily map missing types to JSON writer where feasible.
- **Filesystem Permissions:** Creating run directories may fail in restricted environments (low likelihood).
  - *Mitigation*: Use `mkdir(parents=True, exist_ok=True)` and surface clear errors; allow output dir override.
  - *Rollback*: Allow fallback to temp directory if configured output not writable.

### Dependencies
- `pandas` availability for Parquet writing (already required by project).
- Environment variable management via `.env` loader; ensure docs mention `PYRONDO_OUTPUT_DIR`.

## References
- Original spec: `thoughts/specs/2025-09-22-revamp-exit-point-output-routing.md`
- Implementation design (this plan): `thoughts/plans/2025-09-22-revamp-exit-point-output-routing-plan.md`
- Related research: `tea_simulation_design_doc.md`
- Similar implementations: `simkit/core/pipeline.py`, `simkit/io/writers.py`
