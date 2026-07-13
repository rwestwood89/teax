# Implementation Plan: Study Policy, Query, and CLI Surface (Item 12)

**Status:** Draft
**Created:** 2026-07-12
**Last Updated:** 2026-07-12
**Branch:** constraint-exec-epic

## Source Documents
- **Spec:** `.project/active/study-policy-cli/spec.md`
- **Design:** `.project/active/study-policy-cli/design.md` ← component details, D1–D9, invariants,
  data flows. This plan does not restate them; it references them.

## Mechanism decisions this plan fixes (the design's "Open (plan decides)")

The design's Next-Stage Handoff left three mechanism calls to the plan. Fixed here so the
implementer does not re-open them:

- **`ObjectiveSpec`** = a frozen dataclass in `study/policy.py`: `output: str`,
  `role: Literal["minimize", "maximize", "penalty"]`, `penalty_threshold: float | None = None`.
  `response_roles` = `Mapping[str, str]` (role label → `constraint_id`). Both are read-only and
  digest-stable (ordered tuple for objectives; the config digest sorts the role map keys).
- **Console-script name** = `teax-study` (design D-component; `pyproject.toml [project.scripts]`).
- **`inspect` rendering** = JSON lines, one decoded `CaseView` per line (design D6 is Python-first;
  a formatted table is polish, not required by any `[HARD]` item). A `--json`/default choice, no
  table in scope.

## Implementation Strategy

**Phasing rationale.** The one real risk is B1 — that the YAML config reconstructs a
*byte-identical* `StudyDefinition` across processes, so resume binds instead of forking a lineage
(design "Potential Risks"). Everything else is a faithful adapter over certified code (B2/B3 are
low-risk interpretation). So the plan builds the fingerprint foundation, then drives the full
create→run→crash→resume round-trip against the **real** evaluator as early as possible (design
"De-risk first"). Policy correctness, the query join, and CLI polish follow once resume-identity is
proven.

**Critical path:** config schema + semantic fingerprint (Phase 1) → CLI create/run/resume + crash
wiring + minimal-but-real policy, proving INV-4 (Phase 2) → full four-disposition policy + failure
rule (Phase 3) → query + `decode_evidence` + catalog join (Phase 4) → `inspect` render + optional
budget/retention + final gates (Phase 5).

**First proof point:** Phase 1's `semantic_fingerprint()` unit test — the digest is stable across a
reload and shifts iff a definition-shaping field changes, holding steady when only `package.dir` /
spec path / store path move (D2). This is B1 in a fast unit test before the heavy subprocess test.

**Additive-compatibility check (orchestrator emphasis).** Phase 1 adds `objectives` and
`response_roles` to the frozen `StudyDefinition` dataclass with empty defaults. They must not break
Item 11's committed tests. `conftest.build_definition` (`tests/study/conftest.py:177`) constructs
`StudyDefinition` by keyword and passes neither field, so both must default and sit among the
trailing defaulted fields (after `study_definition_fingerprint`, beside `budget`/`retention`).
**Gotcha:** a frozen dataclass rejects a mutable default (`response_roles={}` raises at class
definition) — use `field(default_factory=dict)` and `objectives: tuple[ObjectiveSpec, ...] = ()`.
Every phase re-runs the study suite (29) to confirm no regression.

**Overall validation:** each phase writes tests first, then code, then runs its own tests plus the
regression suites in teax's venv. Final gate in Phase 5.

---

## Phase 0: Environment (prerequisite, not a contract)

### Goal
Confirm teax's own venv runs the **real** evaluator over the sealed fixture package — the Phase 2
end-to-end test needs it (spec "Implementation Prerequisites"; Items 10/11 did the same).

### Steps
- [ ] Confirm `.venv` exists and imports `simkit` and the sealed `wi014_s4` package (it exists on
  this branch; verify rather than re-provision). If broken, provision as Items 10/11 did.
- [ ] Confirm the existing suites run: study suite (29), evaluation suite (25), framework suite
  green except the 4 known failures. Record the baseline.

**What we know after this phase:** the real-evaluator path is runnable, so Phase 2's subprocess test
is not blocked by environment.

---

## Phase 1: Config schema + semantic fingerprint + additive definition fields

### Goal
Stand up `StudyConfig` (Pydantic, YAML) and its `semantic_fingerprint()` (D2), and make
`StudyDefinition` carry typed `objectives`/`response_roles` (D4) — the foundation the round-trip
rebuilds from. First because B1 is the whole risk and this is where it is cheapest to test.

### Assumption Under Test
B1 (partial): the semantic digest captures exactly the definition-shaping subset — reload-stable,
sensitive to every shaping field, insensitive to filesystem locations (D2).

### Test Stencil (Write This First)
```python
# tests/study/test_config.py
def test_semantic_fingerprint_stable_across_reload(tmp_path):
    cfg_path = write_grid_config(tmp_path)            # helper writes the illustrative YAML (design)
    fp1 = load_study_config(cfg_path).semantic_fingerprint()
    fp2 = load_study_config(cfg_path).semantic_fingerprint()
    assert fp1 == fp2

def test_fingerprint_ignores_filesystem_locations(tmp_path):
    base = load_study_config(write_grid_config(tmp_path)).semantic_fingerprint()
    moved = load_study_config(write_grid_config(tmp_path, package_dir="/elsewhere")).semantic_fingerprint()
    assert base == moved                              # D2: package.dir excluded

def test_fingerprint_shifts_on_each_shaping_field(tmp_path):
    base = load_study_config(write_grid_config(tmp_path)).semantic_fingerprint()
    for edit in ["study_id", "entry_model", "grid_order", "grid_domain", "fixed", "policy", "budget"]:
        assert load_study_config(write_grid_config(tmp_path, edit=edit)).semantic_fingerprint() != base
```

### Changes Required
**See design:** Component Overview (`study/config.py`, `study/definition.py`); D1, D2, D4; config
schema block; Architecture data-flow "create".

- [x] **`study/config.py`** (NEW): `StudyConfig` Pydantic model over the illustrative schema
  (package ref, `entry_channel`, `entry_model` name, ordered `grid` as `[param_id, domain]` pairs,
  `fixed`, `policy` block with `name`/`objectives`/`response_roles`, `budget`, `retention`);
  `load_study_config(path)` YAML loader (PyYAML is already a dependency); `semantic_fingerprint()`
  = `digest_of` (`study/identity.py:22`) over the ordered semantic subset only, **excluding**
  `package.dir`, spec path, store path (D2). Preserve grid order as a pair-list, never a dict, so
  `sort_keys` cannot reorder it (mirror `identity.py` docstring and `GridStrategy.config`).
- [x] **`study/policy.py`** (extend): add the `ObjectiveSpec` frozen dataclass (shape fixed above).
  Keep `DispositionPolicy` untouched.
- [x] **`study/definition.py`** (extend): add `objectives: tuple[ObjectiveSpec, ...] = ()` and
  `response_roles: Mapping[str, str] = field(default_factory=dict)` after
  `study_definition_fingerprint`. Import `ObjectiveSpec` from `.policy` (definition already imports
  `Policy` from there — no new cycle).

### Validation
**Automated:**
- [x] `test_config.py` passes.
- [x] **Compat check:** study suite (29) still green — `conftest.build_definition` compiles and runs
  unchanged with the new defaulted fields.
- [x] Ruff clean on changed files.

**What we know after this phase:** the config round-trips to a stable, correctly-scoped fingerprint
(B1's read side), and the additive definition fields didn't disturb Item 11.

---

## Phase 2: Acceptance round-trip — create → run → crash → resume (INV-4)

### Goal
The de-risk. Build the CLI lifecycle and drive a real grid study to a mid-run crash and a clean
resume, proving resume reproduces the uninterrupted ordered cases exactly (INV-4). This is the
single test that exercises the config round-trip (B1), the crash seam (D8), and idempotent resume
together (design "De-risk first", "Validation Approach").

### Assumption Under Test
B1 (full): the same YAML rebuilds a byte-identical definition in a **fresh process**, so the store's
eight-field compatibility binding accepts the resume; and the crash point is deterministic (D8), so
"some cases committed, one not" is not flaky.

### Test Stencil (Write This First)
```python
# tests/study/test_cli_end_to_end.py  (INV-4)
def test_resume_reproduces_uninterrupted_cases(tmp_path):
    cfg = write_grid_config(tmp_path, budgets=[1000., 4000., 6000.])   # cost=3000 → mixed verdicts
    mid = mint_candidate_id(cfg_study_id, 1)                            # crash on the 2nd point
    run_cli(["create", "--config", cfg, "--store", tmp_path/"a.db"])
    rc = run_cli(["run", "--config", cfg, "--store", tmp_path/"a.db",
                  "--crash-at", f"before_commit:{mid}"], subprocess=True)
    assert rc == 137
    run_cli(["resume", "--config", cfg, "--store", tmp_path/"a.db"])
    run_cli(["create", "--config", cfg, "--store", tmp_path/"b.db"])   # uninterrupted reference
    run_cli(["run", "--config", cfg, "--store", tmp_path/"b.db"])
    assert identity_cols(StudyStore(a.db)) == identity_cols(StudyStore(b.db))
    # identity_cols = [(candidate_id, state, evidence_digest, inputs_json) ordered by commit_order]
```

### Changes Required
**See design:** Architecture (both data flows); D3 (policy closes over config), D8 (crash via hidden
`--crash-at`); Implementation Notes (`entry_model` via `getattr`, synthesized validator, provisional
`model_contract_fingerprint` = catalog-bytes digest). `_study_child.py` is the crash-wiring template.

- [x] **`study/config.py`** (extend): `build_definition(config, evaluator)` — the create data flow.
  Load+seal package (`ProvisionalPackageLoader`) → `PreparedEvaluator` → resolve
  `entry_model = getattr(evaluator.package, config.entry_model)` (package-agnostic, **not**
  `evaluator.ToyPlantParams`) → `GridStrategy(config.grid)` → synthesize the proposal-validator
  (per-variable numeric-and-not-bool coerce to `float`, merge `fixed`, malformed/missing/wrong-type
  → `None`; non-finite is valid — mirror `conftest.validate_proposal` and design Implementation
  Notes) → build the policy from `POLICY_REGISTRY` → assemble `StudyDefinition` with all
  fingerprints (`study_definition_fingerprint = config.semantic_fingerprint()`;
  `model_contract_fingerprint` = digest of the catalog file bytes, labeled provisional until Item 9).
- [x] **`study/policy.py`** (extend): `POLICY_REGISTRY: dict[str, PolicyFactory]` mapping name →
  factory taking `(objectives, response_roles, config)`. Register one working objective policy
  (`objective/v1`) **sufficient to run the grid** — extract objectives, map headline → disposition.
  Full four-disposition mapping, the failure rule, and raw penalty are Phase 3; INV-4 asserts only
  ordered-case identity (`assessment_json` is not part of `evidence_digest`), so the disposition
  detail cannot affect this test and Phase 3 will not rework it.
- [x] **`study/cli.py`** (NEW): argparse `create | run | resume | inspect` (`inspect` stubbed until
  Phase 4). `create`: build definition, `StudyStore.create_or_open(store, compat)`, copy the config
  beside the store as a record. `run`/`resume`: rebuild the same definition, open the store, acquire
  lease, `StudyRunner(store, definition, evaluator, crash).run()`, release lease. Hidden `--crash-at
  PHASE:CANDIDATE` on `run`/`resume` wires a `CrashController` (D8, mirroring `_study_child.py`).
  Catch `IncompatibleStore` → actionable new-lineage message (Phase 4 hardens the wording). `main()`
  is the console entry point.
- [x] **`pyproject.toml`** (`teax-simkit`): add `[project.scripts]` `teax-study =
  "simkit.study.cli:main"`.

### Validation
**Automated:**
- [x] `test_cli_end_to_end.py` passes: resumed store's identity columns equal the uninterrupted
  reference's — case order, `state`, `evidence_digest`, `inputs_json` byte-identical. **Note:**
  compare identity columns, **not** `attempt_id`/`commit_order` — the crashed candidate resumes on
  attempt 2 (a "started" transition for attempt 1 was recorded before the `before_commit` crash), so
  its `attempt_id` legitimately differs; `commit_order` is a fresh autoincrement per store.
- [x] Study suite (29) still green; ruff clean.

**Manual:**
- [x] `teax-study create --config <cfg> --store /tmp/s.db` then `teax-study run …` → completes; a
  second `teax-study run …` is a no-op (idempotent by candidate).

**What we know after this phase:** the config-driven definition is byte-reproducible across
processes, the crash seam is deterministic, and resume is identity-exact — B1 and the whole
resume-safety premise are proven.

---

## Phase 3: Full policy — four dispositions, objective-extraction failure, raw penalty

### Goal
Complete `ObjectivePolicy` into the genuine interpretation: the four dispositions, the
objective-extraction failure rule (reachable, not the injected reject-set), and the raw penalty
value. Now, because the plumbing is proven and correctness is the remaining policy risk (B2).

### Assumption Under Test
B2: the four dispositions are computable from `outputs` + `responses` + configured objectives alone,
read-only, with no re-run or mutation.

### Test Stencil (Write This First)
```python
# tests/study/test_policy.py
def test_four_dispositions_from_crafted_evidence():
    assert assess(headline="violated").disposition == "reject"
    assert assess(headline="indeterminate").disposition == "keep-for-boundary"
    assert assess(headline="satisfied", within=True).disposition == "feed-strategy"
    assert assess(headline="satisfied", beyond_penalty=True).disposition == "penalize"

def test_assessment_failed_on_missing_objective_output():         # genuine, not injected
    with pytest.raises(AssessmentFailed):
        ObjectivePolicy(objectives=[ObjectiveSpec("no_such_output", "minimize")], ...).assess(ev, candidate_id="c")

def test_penalty_value_is_raw_not_normalized(): ...               # [INHERITED] raw modeled quantity
def test_evidence_digest_identical_across_dispositions(): ...     # INV-1 non-mutation
```

### Changes Required
**See design:** "The policy: dispositions and the failure rule" (the four steps and the record
shape); INV-1, INV-2; spec `[HARD]`/`[INHERITED]` policy items.

- [x] **`study/policy.py`** (complete `ObjectivePolicy`): objective extraction from
  `evidence.outputs`/`evidence.responses`; the failure rule → `AssessmentFailed` when a configured
  objective `output` ID is absent from `outputs` **or** a configured response role names a
  `constraint_id` absent from `responses` (a well-formed `indeterminate`/`violated`/`not_assessed`
  verdict and a non-finite objective value are **interpreted, not failures**); disposition mapping
  (`violated → reject`; `indeterminate | not_assessed → keep-for-boundary`; `satisfied` within →
  `feed-strategy`; `satisfied` beyond the configured penalty threshold → `penalize`); the assessment
  record `{"disposition", "headline", "objectives": {id: raw_value}, "penalty": raw_or_null}` with a
  **raw** (un-normalized) penalty. Signature unchanged (`assess(evidence, *, candidate_id)`, D3).

### Validation
**Automated:**
- [x] `test_policy.py` passes: four dispositions; disposition ⊥ state (INV-2 — a rejected point is a
  `completed` case whose `assessment_json.disposition == "reject"`, distinct from `assessment_failed`);
  genuine `AssessmentFailed` on a missing objective ID and on an unresolved response role; raw
  penalty; evidence digest identical across dispositions (INV-1).
- [x] Study suite (29) still green; ruff clean.

**What we know after this phase:** the policy is a real interpretation that never mutates evidence
and fails to `assessment_failed` only on a genuine extraction error.

---

## Phase 4: Query + `decode_evidence` + catalog join

### Goal
Build the read surface: `decode_evidence` (D5), `StudyQuery` joining case row + decoded evidence +
catalog, the typed `CaseView`/`CatalogView` records and filters, and the actionable new-lineage
message. Now, because it reads what Phases 2–3 produce.

### Assumption Under Test
B3: the fixture catalog's `concrete_entries`/`source_records` carry every static field the query
must surface (source form, membership kind, polarity, owner, display predicate) via the
`constraint_id → source_usage → source_record` join.

### Test Stencil (Write This First)
```python
# tests/study/test_evidence_io.py  (extend)  — INV-3
@pytest.mark.parametrize("v", [float("nan"), float("inf"), float("-inf")])
def test_decode_is_exact_inverse_of_encode(v): ...   # decode(encode(e)) restores v; no {"__nonfinite__"} leaks

# tests/study/test_query.py
def test_three_states_times_three_verdicts_filterable(built_store): ...   # both axes surfaced + filterable
def test_catalog_join_names_failing_instance(built_store, catalog):
    view = StudyQuery(store, catalog).cases(constraint="toy_plant__demo_plant__affordable")[0]
    assert view.catalog.source_form and view.catalog.membership_kind and view.catalog.owner_qn
def test_every_result_carries_executable_fingerprint(built_store): ...    # INV-5
def test_incompatible_store_yields_new_lineage_message(tmp_path): ...     # message, not traceback
```

### Changes Required
**See design:** Component Overview (`study/query.py`, `study/evidence_io.py`); D5, D6, D7; INV-3,
INV-5; Research Findings (catalog join key; sentinel shape).

- [x] **`study/evidence_io.py`** (extend): `decode_evidence` — the exact inverse of
  `_tag_nonfinite`, recursing identically: a one-key `{"__nonfinite__": "nan"|"inf"|"-inf"}` dict →
  the real float; every other dict/list recursed; genuine one-key dicts of any other key left
  unmolested. One inverse, beside its encoder (D5, INV-3).
- [x] **`study/query.py`** (NEW): `StudyQuery(store, catalog)` reading `cases` rows via
  `store.ordered_cases()`, loading+decoding each referenced artifact once, **memoized by
  `evidence_digest`** (D7). `CaseView` (state, inputs, decoded outputs, per-constraint verdicts,
  `assessment_json` incl. disposition, `executable_fingerprint` from evidence provenance) and
  `CatalogView` (source form, membership kind, polarity/`is_negated`, owner, display predicate)
  typed records. Join per-constraint verdicts to the catalog by `constraint_id → source_usage →
  source_record`. Filters by parameter, output, constraint ID, state, and disposition. Every result
  carries its `executable_fingerprint`; never merge across fingerprints (INV-5).
- [x] **`study/cli.py`** (extend): harden the `IncompatibleStore` catch into an actionable
  new-lineage message that names the differing binding and tells the user a new store path (or
  reverted config) is needed — never a bare traceback (design Implementation Notes).

### Validation
**Automated:**
- [x] `test_query.py` + extended `test_evidence_io.py` pass: three states × three verdict classes
  surfaced and filterable; sentinel round-trip over nan/inf/-inf in responses/outputs/report
  (INV-3); catalog join surfaces source form/membership kind/polarity/owner/display predicate by
  `constraint_id` (B3); every result carries `executable_fingerprint` (INV-5); `IncompatibleStore`
  → new-lineage message.
- [x] Study suite still green (now 29 + new); ruff clean.

**What we know after this phase:** results are readable and joinable, the sentinel never leaks as a
dict, both axes are distinct, and a changed fingerprint refuses cleanly.

---

## Phase 5: `inspect` render, optional budget/retention, final gates

### Goal
Wire `inspect` to render the query (JSON lines), optionally interpret budget/retention (D9,
droppable), and pass the full final gate.

### Assumption Under Test
None material — this is integration and polish. Budget/retention are low-stakes and not load-bearing
for acceptance (design D9, "Low-stakes / droppable").

### Test Stencil (Write This First)
```python
# tests/study/test_cli_inspect.py
def test_inspect_emits_one_json_line_per_case(built_store, capsys):
    run_cli(["inspect", "--config", cfg, "--store", db])
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines()]
    assert len(lines) == n_cases and all("state" in r and "executable_fingerprint" in r for r in lines)
```

### Changes Required
**See design:** D6 (CLI renders the query); D9 (budget/retention rule).

- [ ] **`study/cli.py`** (extend): `inspect` builds `StudyQuery`, applies filter flags, prints one
  JSON line per `CaseView`.
- [ ] **(Optional, D9) `study/bounded_strategy.py`** (NEW): `BoundedStrategy(inner, max_candidates)`
  additive strategy wrapper for `budget` (its `config_fingerprint` includes both inner config and
  the bound — a bounded study is a distinct lineage, correct by design). `retention: gc_after` calls
  the existing `store.gc()` after the lease releases; default `keep`. Ship if cheap; defer if it
  fights the schedule (design "Low-stakes / droppable") — leaving `budget`/`retention` inert is an
  acceptable fallback and does not affect any acceptance criterion.

### Validation (FINAL GATE)
**Automated:**
- [ ] `test_cli_inspect.py` passes (+ budget/retention tests if built).
- [ ] **New tests green** across Phases 1–5.
- [ ] **Study suite (29) still green**; **evaluation suite (25) still green**; **framework suite
  green except the 4 known failures** (baseline from Phase 0).
- [ ] **Ruff clean** across the whole diff.

**Manual:**
- [ ] `teax-study inspect --config <cfg> --store <db>` emits readable JSON-line records with both
  axes and `executable_fingerprint`.

**What we know after this phase:** the full define → run → interrupt → resume → inspect story works
from the console entry point, and no certified suite regressed.

---

## Environment Setup

See CLAUDE.md for test commands. All work runs in teax's own `.venv` (Phase 0). Run gates as
`pytest packages/teax-simkit/simkit/tests/study`, `.../tests/evaluation`, and the framework suite;
`ruff check` on the diff.

## Risk Management

**See `design.md#potential-risks`.** Phase-specific mitigations:
- **Phase 1/2 (B1 fingerprint drift):** the Phase 1 per-field digest test plus the Phase 2 INV-4
  round-trip fail loudly on any drift.
- **Phase 3 (genuine `assessment_failed` not hit by the happy grid):** a dedicated policy test
  configures an objective on a missing output ID to hit the rule genuinely; the end-to-end test need
  not itself fail assessment (spec lists the two as separate criteria).
- **Phase 1 (additive fields break Item 11):** `field(default_factory=dict)` / `= ()` defaults +
  study-suite regression gate on every phase.

## Implementation Notes

[TO BE FILLED DURING IMPLEMENTATION]

### Phase 0 Completion
**Completed:** 2026-07-12
**Changes Made:** none (environment already provisioned on this branch).
**Findings:** `.venv` imports `simkit` and the sealed `wi014_s4` fixture package. Baseline:
study suite 29/29 green, evaluation suite 25/25 green, framework suite green except the 4 known
`test_no_battery_deps.py` failures (unrelated `FileNotFoundError` from a stale absolute path in a
subprocess check, pre-existing).

### Phase 1 Completion
**Completed:** 2026-07-12
**Changes Made:**
- Created `study/config.py`: `StudyConfig`/`PackageRef`/`ObjectiveConfig`/`PolicyConfig` (Pydantic,
  extending `simkit.config.schema.StrictBaseModel` per repo convention), `load_study_config`,
  `semantic_fingerprint()`. The fingerprint excludes the whole `package` block (not just `dir`) —
  package identity is bound separately via `executable_fingerprint`, and no `store path` field
  exists in the config to begin with (it's a CLI arg, not config content).
- Extended `study/policy.py` with the `ObjectiveSpec` frozen dataclass (`output`, `role`,
  `penalty_threshold`) — `DispositionPolicy` untouched.
- Extended `study/definition.py`: `objectives: tuple[ObjectiveSpec, ...] = ()` and
  `response_roles: Mapping[str, str] = field(default_factory=dict)`, placed directly after
  `study_definition_fingerprint` and before `budget`/`retention` (trailing defaulted fields, frozen
  dataclass ordering respected).
- Added `write_grid_config` test helper + `COST_CH`/`GRID_VAR` constants to
  `tests/study/conftest.py` (shared by Phase 1's `test_config.py` and Phase 2's
  `test_cli_end_to_end.py`), and `tests/study/test_config.py` (3 tests: reload-stable,
  filesystem-location-insensitive, shifts on each of 7 shaping-field edits).
**Issues Encountered:** ruff/pip not on the project venv's PATH; used `uvx ruff check` instead
(no other change to tooling).
**Validation:** `test_config.py` 3/3 green; study suite 32/32 green (29 + 3 new); `uvx ruff check`
clean on all changed/new files.

### Phase 2 Completion
**Completed:** 2026-07-12
**Changes Made:**
- Extended `study/config.py`: `build_definition(config, evaluator)`, `_synthesize_validator`
  (mirrors `conftest.validate_proposal`, generalized to config's declared grid variables),
  `_model_contract_fingerprint` (sha256 of the catalog file bytes).
- Extended `study/policy.py`: `ObjectivePolicy` (extracts configured objectives/response roles,
  raises `AssessmentFailed` on a genuinely absent output/constraint, maps
  `violated→reject`, `indeterminate|not_assessed→keep-for-boundary`, `satisfied→feed-strategy` for
  now) and `POLICY_REGISTRY = {"objective/v1": ObjectivePolicy}`.
- Created `study/cli.py`: `create|run|resume|inspect` over argparse; `inspect` raises
  `NotImplementedError` until Phase 4/5. `_open_store` is the shared open-or-refuse-with-message
  helper; `create`/`run`/`resume` each build their own evaluator+definition (no hidden state stashed
  on the certified `StudyStore` instance — an earlier draft did this and was reworked into passing
  `definition`/`evaluator` explicitly).
- `pyproject.toml` (`teax-simkit`): `[project.scripts] teax-study = "simkit.study.cli:main"`
  (registers on next editable-install; not re-run this session — tests invoke `python -m
  simkit.study.cli` / `simkit.study.cli.main()` directly, which needs no reinstall).
- `tests/study/test_cli_end_to_end.py`: `test_resume_reproduces_uninterrupted_cases` (INV-4, the
  crash subprocess exits 137 at `before_commit:<2nd candidate>`; resumed vs. uninterrupted reference
  compared on `(candidate_id, state, evidence_digest, inputs_json)`, not `attempt_id`/
  `commit_order`) and `test_resumed_run_is_idempotent`.
**Issues Encountered:** none — the round-trip passed first run; no fingerprint drift found.
**Manual verification:** ran the built CLI directly (`python -m simkit.study.cli create|run`) against
a hand-written config outside the test tree; second `run` was a no-op; `assessment_json` showed
correct dispositions (`reject` for the violated point, `feed-strategy` for the two satisfied points).
**Validation:** `test_cli_end_to_end.py` 2/2 green; study suite 34/34 green (29 + 3 config + 2 cli);
`uvx ruff check` clean.

### Phase 3 Completion
**Completed:** 2026-07-12
**Changes Made:**
- Completed `study/policy.py`'s `ObjectivePolicy.assess`: non-`"satisfied"` headlines resolve
  directly via `_HEADLINE_DISPOSITION`; `"satisfied"` checks each objective against
  `_beyond_penalty_threshold` (direction flips on `role == "maximize"` vs. `minimize`/`penalty`; a
  non-finite objective value is never "beyond" — interpreted, not failed) and returns `penalize`
  with the first offending objective's **raw** value, else `feed-strategy`.
- `tests/study/test_policy.py` (10 tests): the four dispositions individually; penalty-direction
  respects `role`; raw (non-normalized) penalty value; two genuine `AssessmentFailed` triggers
  (missing objective output, unresolved response role); a well-formed `indeterminate` verdict +
  non-finite objective is not a failure; evidence-digest identical across two differently-configured
  policies assessing the same evidence object (INV-1, via `encode_evidence`); and one
  runner-integration test over the real evaluator (`run_study`/`prepared`) proving INV-2 — the
  violated PROPOSALS candidate lands as a `completed` case with `assessment_json.disposition ==
  "reject"`, not `assessment_failed`.
**Issues Encountered:** `ModelEvidence.report` is read via `.model_dump(mode="json")` inside
`encode_evidence`, so a plain dict report (as in an early draft) raised `AttributeError`; fixed by
giving the unit tests a minimal `_StubReport(BaseModel)` stand-in.
**Validation:** `test_policy.py` 10/10 green; study suite 44/44 green (34 + 10 new); `uvx ruff check`
clean.

### Phase 4 Completion
**Completed:** 2026-07-12
**Changes Made:**
- Extended `study/evidence_io.py`: `decode_evidence`/`_untag_nonfinite`, the mechanical inverse of
  `_tag_nonfinite`, beside the encoder.
- Created `study/query.py`: `StudyQuery(store, catalog_path)`, `CaseView`/`CatalogView` frozen
  dataclasses, `_Catalog` (indexes the fixture JSON by `usage_name`/`constraint_id` once). Query
  result shape (own to decide, per spec Open Questions "mechanism; defer"): `CaseView.verdicts` is a
  `dict[constraint_id, verdict]` and `CaseView.catalog` a `dict[constraint_id, CatalogView]` — a
  case view carries *every* constraint's verdict + catalog detail, not one row per (case,
  constraint) pair; `cases(constraint=X)` filters cases whose verdicts contain `X`, it does not
  flatten to per-verdict rows. `executable_fingerprint` reads from evidence provenance when
  evidence exists, else falls back to the store's bound compatibility fingerprint (execution_failed
  cases carry no evidence) — the two are equal by construction (INV-5), so either source is correct.
- Extended `study/cli.py`'s `_new_lineage_message` wording (already written in Phase 2; verified
  here against a real refused resume) — no further change needed to satisfy "actionable, never a
  bare traceback".
- `tests/study/test_evidence_io.py`: added `test_decode_is_exact_inverse_of_encode`
  (nan/inf/-inf, parametrized). Uses a typed `Dict[str, float]` report field, not a bare `dict` —
  Pydantic's `model_dump(mode="json")` silently coerces non-finite floats to `null` inside an
  untyped `dict` field (verified interactively), so an untyped poisoned-report stand-in would have
  failed before `_tag_nonfinite` ever saw the value; the real generated report's
  `observed: dict[str, float]` (constraint_types.py) is properly typed and unaffected.
- `tests/study/test_query.py` (5 tests): two fixtures — `built_store` (`DispositionPolicy` with an
  injected reject, for state/verdict diversity including a genuine `assessment_failed` case, mirrors
  `test_runner_matrix.py`) and `objective_store` (real `ObjectivePolicy`, for its own disposition
  vocabulary). Three states × four verdict classes surfaced/filterable; catalog join names the
  failing instance; every result's `executable_fingerprint` equals the store's bound one (INV-5);
  disposition/output filters; refused resume yields a lineage message with no traceback.
**Issues Encountered:** the `Dict[str, float]` vs. bare `dict` Pydantic serialization gap above —
test-only, not a defect in `encode_evidence` (real generated reports use typed float mappings).
**Validation:** `test_query.py` 5/5, extended `test_evidence_io.py` 5/5 green; study suite green;
`uvx ruff check` clean.

### Phase 5 Completion

---

**Status:** Draft → In Progress → Complete
</content>
</invoke>
