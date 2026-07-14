# Audit: Model Evaluator and Typed Entry (Item 10)

**Verdict:** Certify-with-notes
**Audited:** 2026-07-12
**Branch:** constraint-exec-epic
**Commit:** 99443c1 (Phase 4 final); base 8a6bcdf (pre-Item-10)

---

## Summary

Item 10 delivers what the spec, design rev 2, and the [OWNER] Shape A gate specify. The five
phase commits are purely additive (1770 insertions, 0 deletions), confined to
`simkit/evaluation/`, `tests/evaluation/`, and the committed sealed-package fixture — no existing
runtime or test file was touched. Every one of the seven claims in the brief is borne out by the
code and fixtures I traced: the isolation guard has real teeth (AST allowlist + package-absent
subprocess), the entry source is Shape A with no raw-mapping validation, the failure taxonomy is
structurally correct, the canonical vocabulary is pinned and the projection is read-only, and the
NaN parity test asserts `isnan` on a *compared* output field, not just verdict strings.

One hard limit on this audit: **I could not execute the test suite.** `pytest` and `python`
require interactive approval that is unavailable in this non-interactive session; only `git` and
file reads ran. So every runtime claim (suite green, the four pre-existing failures, the isolation
mutation probe, NaN propagation end-to-end) is verified by static trace of code + fixtures +
assertions, not by a live run. The static evidence is strong and internally consistent, but the
four **Requested live probes** below are what convert it to executed certainty. The
certify-with-notes verdict reflects that gap plus a few minor coverage observations — none of
which is a spec failure.

## Findings

### Plan completion

All four product phases (0–4) trace to real, correctly-shaped code and tests. Phase notes are
honest and specific (e.g. the Phase 4 note documenting the isolation-test subprocess fix as a
correction to Phase 1 work). Two deviations recorded in the plan are additive precision, not
contradictions:

- `MappingEntrySource.validate` raises `EvaluationFailed(phase=ENTRY_VALIDATION)` directly rather
  than a bare `ValueError` (`entry_source.py:47,57`). This is what makes INV2 phase-tagged at the
  source. Sound.
- `project(...)` takes `provenance` as a required keyword-only third param rather than patching a
  frozen model afterward (`projection.py:20`). Keeps the isolation-clean module free of
  fingerprint/versioning knowledge. Sound.

One item was implemented ahead of its planned phase: the `preparation`-phase wrapping around
`build_graph` (`evaluator.py:96–103`) landed in Phase 2, not Phase 4. Recorded in both phase
notes. Fine.

### Spec conformance

- **SC1 — S5 invariants as kept teax tests.** Present and correctly shaped:
  mapping-vs-file parity (`test_parity.py`), pre-execution rejection
  (`test_prepared_evaluator.py:39`, phase `entry_validation`), fresh-context isolation
  (`test_prepared_evaluator.py:55`), no output dir in no-persist mode
  (`test_prepared_evaluator.py:48`). Runtime-green pending Probe 2.
- **SC2 — S4-lineage → evidence, vocabulary pinned here.** `CANONICAL_HEADLINE`
  (`evidence.py:20`) pins `satisfied | violated | indeterminate | not_assessed` and maps the
  generated headlines (`all_satisfied`, `violation`, `indeterminate`, `not_assessed` — confirmed
  the exact set emitted at `constraint_report_aggregator.py:38–45`). Report held opaque
  (`ModelEvidence.report: Any`, `evidence.py:58`); no generated class imported by any runtime
  type (see SC3). Closable in Item 10 as claimed. **Met.**
- **SC3 — no-generated-import kept isolation test.** Two legs in `test_isolation.py`: AST
  allowlist scan over the four clean modules (walks the whole tree, so it catches
  `TYPE_CHECKING`/string-annotation imports) and a package-absent **subprocess** construction.
  The allowlist is `{pydantic, simkit, stdlib}` — robust to the `wi014_s4` name and Item 9's
  rename. Structurally correct; mutation-probe confirmation is Probe 3. **Met (structure).**
- **SC4 — three phases distinguishable.** `test_failure_taxonomy.py` shows module exception →
  `module_execution`, entry rejection → `entry_validation`, indeterminate → evidence (no raise).
  Three distinguishable places. **Met (structure).**
- **SC5 — non-finite input reaches the verdict, not the guard.** `ToyPlantParams` is a plain
  non-strict `float` model (`schemas/toy_plant_params.py`), so NaN passes construction; the
  entry source does zero float validation (`entry_source.py` — isinstance only); the Kleene
  `_cmp` returns `None` → `indeterminate` on a non-finite operand
  (`demo_plant_affordable.py:20–30,46–54`). `test_prepared_evaluator.py:17` asserts NaN budget →
  `indeterminate` with finite area/cost. Arithmetic confirmed statically. **Met.**
- **SC6 — both backends agree, NaN case in fixture set.** `test_parity.py:41` compares
  area/cost (NaN-aware) and responses (string-exact) across all four cases;
  `test_f_output_exercises_nan_aware_rule_on_a_compared_output` asserts `math.isnan` on
  `area` AND `cost` for **both** legs — i.e. on a *compared output field*, directly answering
  the brief's claim 3. F-budget's compared outputs are asserted finite while the verdict is
  `indeterminate` (`test_parity.py:68`). Fixtures use bare `NaN` tokens (`f_output.json`,
  `f_budget.json`). **Met (structure); runtime-green pending Probe 2.**
- **SC7 — RootModel[float] continuity regression.** Spec declares this "already discharged this
  run" (S5 carry-forward) and "recorded as done, not re-planned." It is not in Item 10's diff;
  not re-verified here. Consistent with the spec's own framing.

**Non-goals respected.** No study store/runner/strategies, no contract authoring, no proposal
validation, no frozen on-disk non-finite encoding. The report is held opaque; the `{"__nonfinite__"}`
tag is digest-input only (`evaluator.py:34–47`), never the evidence encoding — matches the
non-goal boundary.

### Design conformance

- **D1 Shape A** — `entry_source.py` accepts instantiated models only (`isinstance(value,
  expected_type)`), refuses a wrong channel-model instance naming expected vs got
  (`entry_source.py:56–66`: "expects {expected}, got {got}"), and does **no** raw-mapping
  validation. It never references a generated class statically — `expected_types` is supplied via
  `from_spec(spec, schema_types)`. This is the reserved gate decided the Shape A way; no
  validate-raw path crept in. **Conforms.** (Brief claim 5 satisfied.)
- **D2 layer split** — the four isolation-clean modules (`evidence`, `entry_source`, `failure`,
  `projection`) import allowlist-only; `evaluator.py`/`package_load.py` are the only
  package-touching modules and are outside the scanned set. Confirmed the AST scan set is exactly
  those four. **Conforms.**
- **D3** — `evaluate(typed_inputs) -> ModelEvidence`, no `attempt_number` (`evaluator.py:31,109`).
  **Conforms.**
- **D4** — failure raised as `EvaluationFailed` carrying frozen `EvaluationFailure`;
  `retryable` defaults `False` and is never overridden anywhere in `evaluator.py`/`entry_source.py`.
  `test_every_raised_failure_is_terminal` guards it. **Conforms.**
- **D5** — in-memory router built unconditionally via
  `create_output_router_with_json_schemas(..., in_memory=True)` (`evaluator.py:86`). **Conforms.**
- **D6** — read-only headline normalization; report attached opaque and unmodified. `project`
  reads `report.headline`/`report.results` by attribute, never sets anything on `report`, and
  attaches it as-is (`projection.py:28–43`). `test_report_attached_unchanged` asserts identity.
  **Conforms.** (Brief claim 4, "report-never-mutated," satisfied — see note below on strength.)
- **D7** — `ProvisionalPackageLoader` symlinks under the declared name and verifies the seal
  inline (`package_load.py:42–70`); no on-disk directory name hard-coded (caller supplies
  `link_root`, `package_name`, `package_dir`). **Conforms.**

**INV1–INV6** all map to real code/tests. INV5 ("indeterminate is always evidence; the four
phases are the only failures") holds: violated and satisfied both return evidence without raising
(`test_prepared_evaluator.py:25`), and indeterminate returns evidence
(`test_failure_taxonomy.py:54`). Brief claim 4's "violated-never-raises": the `violated` path
runs the module cleanly, the aggregator emits headline `violation` → normalized `violated`, and
`evaluate` returns — no raise site on that path. Confirmed by trace + `test_satisfied_and_violated_verdicts`.

### Code integrity

No slop or failure-honesty problems. The two broad `except Exception` catches
(`evaluator.py:97,114`) are the *intended* normalization boundary — they re-raise as a typed
`EvaluationFailed` carrying phase + cause, never swallow into a safe default. That is the correct
pattern for this seam, and it matches the design's phase→failure map. The seal check raises
loudly on any mismatch or unhashed extra (`package_load.py:52–60`). No backwards-compat shims, no
optional-param-papering.

**Minor observations (not failures, not blocking):**

1. **`preparation` and `output_write` phases have no kept test.** `evaluator.py:96–103` wraps
   `build_graph` to emit `phase=preparation`, but no test exercises a prepare-time validation
   failure; `output_write` is asserted unreachable in no-persist mode but not exercised on the
   file-backed leg. Spec SC3 only requires the three-outcome distinction (which is tested), so
   this is a coverage gap, not a spec gap. If Item 11 depends on `preparation` surfacing
   correctly, add a test that feeds a topology-invalid spec.
2. **`module_or_channel` is left `None` on `module_execution` failures** (`evaluator.py:114–120`).
   The design says "when known"; the catch-all doesn't parse the module out of the executor
   exception. Within spec ("when known"), but a downstream consumer expecting the failing module
   name won't get it. Worth stating explicitly for Item 11.
3. **"Report never mutated" is proven by identity, not content-immutability.**
   `test_report_attached_unchanged` asserts `evidence.report is report`; combined with the
   code (projection never calls setattr on `report`), the claim holds. A content snapshot would
   be strictly stronger, but the report object is the generated model held opaque and the code
   demonstrably never writes to it. Sufficient.

---

## Certification

**Checked (static trace of code + fixtures + test assertions, at commit 99443c1):**

- Item 10 is additive-only and touches no existing file (`git diff --stat 8a6bcdf 99443c1`:
  1770 insertions, 0 deletions, all under `evaluation/`, `tests/evaluation/`, and the fixture
  tree). This is the structural basis for "no new failure hiding among the four pre-existing ones."
- The four pre-existing hard-coded-checkout-path failures are real and predate Item 10: exactly
  four tests in `test_no_battery_deps.py` (lines 72/84/95/106) hard-code `cwd="/home/reid/teax"`
  (repo is at `/home/reid/1cfe/teax`, so the dir does not exist → `FileNotFoundError`). The file
  was last modified in `ea13013` ("Phase 5 implemented"), an ancestor of the pre-Item-10 base
  `8a6bcdf`. Item 10 never touched it.
- Isolation guard structure, AST scan coverage of TYPE_CHECKING, the package-absent subprocess.
- Shape A entry source; no raw-mapping validation; expected/got diagnostic.
- Canonical vocabulary pinned; generated headline set matches; read-only projection; opaque report.
- Failure taxonomy structure; retryable=False everywhere; three distinguishable outcomes.
- Fixture arithmetic (area = length·width, cost = area·unit_cost, budget feeds only the
  constraint), so F-budget → finite outputs + indeterminate, F-output → NaN area/cost.
- NaN-parity test asserts `isnan` on compared output fields on both legs.
- Public API `__init__.py` exports all 13 names.
- Seal check runs at fixture setup for every `prepared`/`file_backed` test (session-scoped).
- All cross-package imports the evaluator relies on resolve (`_build_entry_loaders`,
  `_build_schema_type_registry`, `entry_point_validate`, `create_output_router_with_json_schemas`,
  `_execute_entry`/`build_graph`/`run` hooks all present).

**Checkboxes marked:** spec success criteria SC1–SC6 (SC7 pre-discharged, left as the spec
records it); plan Phases 0–4 were already checked by the implementer and I did not alter them.
I marked the spec criteria on the strength of the static trace; the loud caveat below governs.

**Not checked (execution blocked — requires the live probes below):**

- No test was actually run. Suite-green, the exact pre-Item-10 failure *set* (that it is exactly
  those four and nothing else), the isolation mutation probe going RED, and NaN propagation
  end-to-end are all **unverified by execution**. My confidence is from static consistency, which
  can miss an environment/import/collection issue a run would catch.
- I did not re-verify SC7's RootModel regression (out of Item 10's diff, spec declares it done).
- I did not independently re-hash the sealed fixture tree against its contract (the loader does
  this at runtime; not run here).

## Requested live probes (for the orchestrator to run)

Run from repo root `/home/reid/1cfe/teax` with `.venv/bin/`.

1. **Pre-existing-failures comparison (brief claim 1).**
   ```
   git stash -u  # if needed to clean worktree
   git checkout 8a6bcdf
   .venv/bin/pytest packages/teax-simkit -q
   git checkout constraint-exec-epic
   ```
   *Expected:* at `8a6bcdf`, exactly four failures, all in `test_no_battery_deps.py`
   (`test_no_battery_imports_in_framework`, `test_no_battery_config_imports`,
   `test_no_load_profile_imports`, `test_no_geography_imports`), each a `FileNotFoundError` on
   `/home/reid/teax`. Any other failure at base, or any *new* failure at HEAD beyond these four
   (excluding the new `tests/evaluation` suite), fails the item.

2. **Full evaluation suite + framework regression (SC1/SC6, runtime-green).**
   ```
   .venv/bin/pytest packages/teax-simkit/simkit/tests/evaluation -q
   .venv/bin/pytest packages/teax-simkit -q
   ```
   *Expected:* 25 passed in `tests/evaluation`; framework suite green except the four pre-existing
   failures from Probe 1.

3. **Isolation mutation probe (brief claim 2).** In
   `packages/teax-simkit/simkit/evaluation/evidence.py`, add near the top:
   ```python
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       import wi014_s4  # noqa
   ```
   Then:
   ```
   .venv/bin/pytest packages/teax-simkit/simkit/tests/evaluation/test_isolation.py::test_clean_modules_import_only_allowlist -q
   ```
   *Expected:* RED — `AssertionError: evidence.py imports disallowed root 'wi014_s4'`. **Revert**
   the edit afterward and re-run to confirm GREEN.

4. **File-backed NaN + no-dir spot check (SC5/INV6, end-to-end on the real package).** Covered by
   Probe 2's `test_parity.py` and `test_prepared_evaluator.py`, but if a standalone confirmation is
   wanted, run just `test_f_output_exercises_nan_aware_rule_on_a_compared_output` and
   `test_no_output_directory_in_no_persist_mode`.
   *Expected:* both green; F-output's `area`/`cost` non-finite on both legs.

If Probes 1–3 return the expected results, this audit upgrades to a clean **Certify** with no open
items beyond the three minor coverage observations above.

---

ARTIFACT written; tracking updated below.

---

## Addendum: Probes 1–3 executed by orchestrator (2026-07-12)

- **Probe 1 (pre-existing failures):** at base `8a6bcdf`, exactly the four `test_no_battery_deps.py` failures; at HEAD, the identical set (plus zero new ones). Claim verified.
- **Probe 2 (suites):** `tests/evaluation` → **25 passed**; framework suite green except the four pre-existing failures.
- **Probe 3 (isolation mutation):** `TYPE_CHECKING`-guarded `import wi014_s4` in `evidence.py` → exact expected RED (`AssertionError: evidence.py imports disallowed root 'wi014_s4'`) → revert → isolation suite GREEN. (First attempt inserted above `__future__` and failed as a SyntaxError — re-run correctly; noting for honesty.) The AST scan has teeth, including TYPE_CHECKING blocks.
- Probe 4 subsumed by Probe 2 per the audit's own note.

**Final verdict: Certify** (upgraded from Certify-with-notes; all runtime claims now executed).
