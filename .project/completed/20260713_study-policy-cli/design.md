# Design: Study Policy, Query, and CLI Surface (Item 12)

**Status:** Draft
**Owner:** Reid W
**Created:** 2026-07-12
**Branch:** constraint-exec-epic
**Base commit:** 3a30b47

---

## Overview

Three thin user surfaces over the certified Item 10/11 machinery: a full **policy** that
interprets immutable evidence into one of four dispositions, a **query** that joins the case
row + evidence artifact + catalog and decodes the non-finite sentinel, and a **CLI** that
drives create → run → interrupt → resume → inspect over a declarative study-config file.

## Related Artifacts

- **Spec:** `.project/active/study-policy-cli/spec.md` (the `[HARD]` items below are fixed there).
- **Design brief:** `.project/active/study-policy-cli/briefs/` (orchestrator decisions D-CLI, D-track).
- **Epic:** `.project/reference/epic_constraint_execution.md` — Item 12.
- **Required Reading:** `.project/reference/constraint-execution-concept.md` — "Study Layer",
  "Run a Study", "Inspect and Resume", Vocabulary, Design Principle 1.
- **Consumed as-is (certified):** `simkit/study/` (store, runner, strategy, compatibility,
  evidence_io, definition, bridge, identity, crash), `simkit/evaluation/` (evaluator, evidence,
  projection, package_load).

## Research Findings

The certified code already fixes almost every seam this item plugs into. Key facts:

- **The runner never sees the definition source.** `StudyRunner.run` drives
  `definition.strategy.propose`, `definition.validate_proposal`, `definition.policy.assess`, and
  `bridge.build` (`study/runner.py:45–66`). It calls `policy.assess(evidence, candidate_id=…)`
  with no other context (`runner.py:132`). So a richer policy must close over its config at
  construction — the assess signature and the runner call site stay untouched.
- **Evidence is frozen and encoded independently of assessment.** `_assess_and_commit` encodes
  evidence to the artifact *before* calling the policy, and stages the true evidence even on
  `AssessmentFailed` (`runner.py:130–143`). Non-mutation and evidence-preservation are already
  structural; the full policy inherits them for free.
- **The store already distinguishes both axes.** `cases.state` holds
  `completed|execution_failed|assessment_failed`; the evidence `responses`/`report` hold the
  `satisfied|violated|indeterminate|not_assessed` verdicts (`store.py:62–71`,
  `evaluation/evidence.py:16`, `constraint_types.py`). The query reads, never re-derives them.
- **Compatibility is an eight-field frozen binding checked on every reopen** (`compatibility.py`;
  `store.py:_check_compatibility` raises `IncompatibleStore`). Resume correctness is *already*
  enforced by the store; the CLI only needs to rebuild the same `StudyDefinition` and render the
  refusal instead of a stack trace.
- **The evaluator hands back everything the CLI needs to assemble a definition:**
  `evaluator.package`, `evaluator.fingerprint`, `EVIDENCE_SCHEMA_VERSION`, and the entry-model
  type (`evaluator.py:77–107`; `package_load.py`). `conftest.build_definition` is the exact
  template (`tests/study/conftest.py:177`).
- **The sentinel is a pure recursive tag** (`evidence_io.py:_tag_nonfinite`) with a reserved
  one-key `{"__nonfinite__": …}` shape. Its inverse is mechanical and belongs beside it.
- **The catalog fixture** (`…/package_live/contracts/constraint_catalog.json`) has
  `concrete_entries` keyed by `constraint_id` (→ `source_usage`, `owner_instance`,
  `membership_kind`, `is_negated`) and `source_records` keyed by `usage_name` (→ `source_form`,
  `owner_qn`, `definition_qn`, `predicate_ir`). The join is `constraint_id → source_usage →
  source_record`.
- **Item 11 already ships a deterministic crash seam.** `CrashController` `os._exit(137)`s at a
  named `(phase, candidate_id)` (`study/crash.py`); `_study_child.py` wires it from a `--crash-at`
  argument. The CLI reuses this exact mechanism for the interrupt test — no timing races.

## Core Concept

This item is **plumbing, not machinery**. The certified runner/store already produce and persist
everything correctly; nobody can drive them and nobody can read the results back. So we add three
adapters and change no contract:

1. **Policy = interpretation, closed over its config.** A named policy from a small built-in
   registry reads immutable evidence (outputs, per-constraint verdicts, headline) and returns a
   separate assessment record naming one of four dispositions — reject, penalize,
   keep-for-boundary, feed-strategy. It fails to `assessment_failed` only when it genuinely cannot
   extract a required objective or response role. It never touches the artifact bytes; the runner
   already staged them.

2. **Query = a read-only join with the sentinel decoded.** One `StudyQuery` reads the `cases`
   rows, loads and decodes each referenced evidence artifact once, and joins per-constraint
   verdicts to the catalog by `constraint_id`. It surfaces both axes (three case states, three
   verdict classes), carries each result's `executable_fingerprint` as the correlation boundary
   marker, and filters by parameter, output, constraint, status, state, and disposition.

3. **CLI = a lifecycle over a declarative config file.** A study-config file (YAML) *is* the
   persistent, re-readable definition. `create` builds a `StudyDefinition` from it and binds the
   store; `run`/`resume` rebuild the same definition and drive the runner (the store's
   compatibility check enforces they match); `inspect` renders the query. The config's semantic
   digest is the `study_definition_fingerprint`, so an edited config is a new lineage by
   construction.

The key insight: **the config file replaces the hand-assembled `StudyDefinition`, and the store's
existing compatibility binding — not new CLI logic — is what makes resume safe.** Everything else
is a faithful adapter over certified code.

## Key Bets

- **B1. The declarative config carries enough to reconstruct a byte-identical `StudyDefinition`
  across processes.** Package ref + entry channel/model name + ordered grid + fixed fields + policy
  block + budget/retention fully determine the definition; nothing definition-shaping lives only in
  Python. *If false → resume rebuilds a subtly different definition, the fingerprint diverges, and
  either a valid resume is refused or (worse) identity silently shifts.*
- **B2. A policy can be a genuine interpretation while reading evidence strictly read-only.** The
  four dispositions are computable from `outputs` + `responses` + configured objectives alone,
  with no need to re-run or mutate anything. *If false → the policy needs to recompute or amend
  evidence, breaking the non-mutation invariant and the whole "compute/judge/decide are separate"
  premise.*
- **B3. The fixture catalog shape is a sufficient stand-in for the future `ModelContract`.** Its
  `concrete_entries`/`source_records` carry every static field the query must surface (source form,
  membership kind, polarity, owner, display predicate). *If false → the query cannot name failing
  instances and the catalog-join success criterion is unmet until Item 9.*

## Key Decisions

- **D1. Config format = YAML, with a Pydantic config schema.** *Rejected: JSON (the repo already
  drives pipelines from YAML; a hand-edited study file wants comments and readability); an ad-hoc
  dict loaded without validation (loses fail-fast on a malformed study).* 
- **D2. `study_definition_fingerprint` = digest of the config's *semantic* subset, excluding
  filesystem locations.** Digest `study_id`, entry channel/model name, ordered grid, fixed fields,
  policy block, budget, retention — not `package.dir`, spec path, or store path. Package identity is
  separately bound via `executable_fingerprint` (the seal). *Rejected: digesting the whole config
  file (a moved package dir or renamed store would spuriously start a new lineage); a hand-authored
  fingerprint field (drifts from content).*
- **D3. The policy closes over its config; the assess signature and runner call site are
  unchanged.** The CLI builds the concrete policy from the definition's `objectives`/`response_roles`
  and hands it in. *Rejected: extending `Policy.assess` to receive objective context (edits the
  certified runner call at `runner.py:132` for no behavioral gain).*
- **D4. Objectives and response roles are typed fields on `StudyDefinition` (additive, defaulting
  empty).** They populate from the config and feed the policy factory; the config digest (D2) puts
  them in the fingerprint. *Rejected: carrying them only inside policy config (the `[INHERITED]`
  requirement is that `StudyDefinition` carries them; empty defaults keep `conftest` compiling).*
- **D5. `decode_evidence` lives next to `encode_evidence` in `study/evidence_io.py`; the query
  imports it.** One inverse, one home. *Rejected: a decode in `query.py` (duplicates the sentinel
  contract across two files — the exact drift the encode module's INV-H docstring warns against).*
- **D6. Query is Python-first (`StudyQuery` returning typed records); the CLI `inspect` renders
  it.** *Rejected: CLI-only string output (the join is the testable unit and a future notebook/plot
  consumer needs the records, per concept "Inspect and Resume").*
- **D7. Query decodes eagerly, memoized by digest.** Each referenced artifact is read+decoded once,
  cached by `evidence_digest`. *Rejected: lazy per-field loading (a real abstraction cost for
  fixture-scale grids that fit in memory); re-reading per case (duplicate reads for replicate
  digests).*
- **D8. Interrupt = the certified `CrashController` wired through a hidden, test-only `--crash-at`
  argument.** Mirrors `_study_child.py`. *Rejected: `SIGKILL` on the subprocess (nondeterministic
  crash point makes "some cases committed, one not" flaky).*
- **D9. Budget/retention get a thin, optional interpretation.** `budget` (int) caps candidates via
  an additive `BoundedStrategy` wrapper; `retention: gc_after` calls the existing `store.gc()` after
  the lease releases (default `keep`). *Rejected: leaving them inert (spec asks design to state the
  rule); wiring budget into the runner (certified). Both are low-stakes and not load-bearing for the
  acceptance test — see Handoff.*

## Architecture

```
study-config.yaml ──► StudyConfig (Pydantic)          [study/config.py]
        │                    │
        │        ┌───────────┼──────────────┬───────────────────┐
        ▼        ▼           ▼              ▼                   ▼
  ProvisionalPackageLoader  GridStrategy  synthesized-validator  POLICY_REGISTRY[name]
        │                                                        (objectives, roles)
        ▼                                                        │
  PreparedEvaluator ──► entry_model, fingerprint, schema ver     ▼
        └──────────────────────────► StudyDefinition ◄───── ObjectivePolicy
                                          │  (+objectives, response_roles: D4)
                                          ▼
   create ─► StudyStore.create_or_open(compat)         [certified]
   run/resume ─► open → acquire_lease → StudyRunner.run(crash) → release  [certified]
                                          │
                                          ▼  reads
   inspect ─► StudyQuery(store, catalog) ─┼─► cases rows (state, inputs, assessment)
                                          ├─► evidence artifact via digest → decode_evidence
                                          └─► catalog join by constraint_id
                                              → CaseView[] (both axes, fingerprint, catalog detail)
```

**Data flow, create:** load config → load+seal package → build `PreparedEvaluator` → resolve
`entry_model` = `getattr(evaluator.package, config.entry_model)` → build `GridStrategy` from the
ordered variable list → synthesize the proposal-validator (coerce numeric, merge fixed fields) →
build the policy from the registry → assemble `StudyDefinition` (all fingerprints; D2 semantic
digest) → `StudyStore.create_or_open` binds compatibility → copy the config beside the store as a
record.

**Data flow, resume:** rebuild the definition from the *same* config → `create_or_open` on the
existing store → `_check_compatibility` raises `IncompatibleStore` on any changed fingerprint → CLI
catches it and prints the new-lineage message. Otherwise acquire lease and run; the runner's
`has_case` skip makes it idempotent by candidate.

**Failure routing** is unchanged — the runner already keeps `execution_failed` /
`assessment_failed` / feasible-but-`indeterminate` distinct; the surfaces only read them.

## Required Invariants

- **INV-1. Assessment never mutates evidence.** The policy receives frozen `ModelEvidence` and
  returns a new dict; the artifact bytes are produced by `encode_evidence` before assess runs. (Test:
  artifact digest identical whether the policy rejects, penalizes, or fails.)
- **INV-2. Disposition ⊥ case state.** A policy-*rejected* point is a `completed` case whose
  `assessment_json.disposition == "reject"`; an `assessment_failed` case means the policy itself
  broke. The query filters the two independently.
- **INV-3. `decode_evidence` is the exact inverse of `encode_evidence`.** For any evidence,
  `decode(encode(e))` restores every non-finite float and leaves no `{"__nonfinite__": …}` dict in
  the caller-visible payload. (Test: round-trip over nan/inf/-inf in responses, outputs, report.)
- **INV-4. Resume reproduces the uninterrupted ordered cases exactly.** After a mid-run crash,
  `resume` yields byte-identical case order, states, and `evidence_digest`s vs. an uninterrupted run
  over the same config. (The acceptance test.)
- **INV-5. Every query result carries its `executable_fingerprint`.** Read from evidence provenance
  (and equal to the store's bound fingerprint); the query never merges across fingerprints.

## Component Overview

- **`study/config.py`** — `StudyConfig` Pydantic schema (package ref, entry channel/model, ordered
  grid, fixed fields, policy block, budget, retention), a YAML loader, and `semantic_fingerprint()`
  (D2). Synthesizes the grid proposal-validator.
- **`study/policy.py`** (extend) — add `ObjectivePolicy` implementing the four-disposition
  interpretation and the objective-extraction failure rule (below). Keep `DispositionPolicy` (tests
  use it). Add `POLICY_REGISTRY: dict[str, PolicyFactory]` mapping name → factory taking
  `(objectives, response_roles, config)`.
- **`study/definition.py`** (extend) — add `objectives: tuple[ObjectiveSpec, …] = ()` and
  `response_roles: Mapping[str, str] = {}` (D4).
- **`study/evidence_io.py`** (extend) — add `decode_evidence` (D5).
- **`study/query.py`** — `StudyQuery` over a store + catalog; `CaseView` and `CatalogView` typed
  records; filters. Uses `decode_evidence`; joins the catalog by `constraint_id`.
- **`study/cli.py`** — argparse `create|run|resume|inspect`; wires the evaluator/store/runner/query;
  catches `IncompatibleStore`; hidden `--crash-at` (D8). `main()` is the console entry point.
- **`study/bounded_strategy.py`** (optional, D9) — `BoundedStrategy(inner, max_candidates)`, an
  additive strategy wrapper for `budget`.
- **`pyproject.toml`** — `[project.scripts] teax-study = "simkit.study.cli:main"`.

### The policy: dispositions and the failure rule

`ObjectivePolicy.assess(evidence, *, candidate_id)` (signature unchanged):

1. **Extract objectives.** For each configured objective (an `output` ID + a `role` such as
   `minimize`/`maximize`/`penalty`), read `evidence.outputs[output]`. Extract response-role verdicts
   by resolving each configured role to a `constraint_id` in `evidence.responses`.
2. **Objective-extraction failure rule** → raise `AssessmentFailed` (spec asked design to state it):
   a configured objective `output` ID is **absent** from `evidence.outputs`, **or** a configured
   response role names a constraint **absent** from `evidence.responses`. A well-formed
   `indeterminate`/`violated`/`not_assessed` verdict, and a non-finite objective value, are **not**
   failures — they are interpreted, not rejected. This is genuinely reachable (configure an objective
   on an output the evidence lacks), distinct from Item 11's injected `reject_candidate_ids`.
3. **Map to a disposition** from the headline verdict and objective thresholds:
   `violated → reject`; `indeterminate | not_assessed → keep-for-boundary`;
   `satisfied` within threshold `→ feed-strategy`; `satisfied` beyond a configured penalty threshold
   `→ penalize`.
4. **Return the assessment record** (a plain dict, stored in `cases.assessment_json`):
   `{"disposition", "headline", "objectives": {id: raw_value}, "penalty": raw_or_null}`. Penalize
   carries the **raw** objective/penalty value — never a normalized scale (spec `[INHERITED]`).

### Config schema (illustrative, ~schema not code)

```yaml
study_id: toy-grid-demo
package: { dir: <package_live>, name: wi014_s4, spec: pipelines/pipeline.yaml }
entry_channel: toy_plant_params
entry_model: ToyPlantParams            # attribute on the loaded package module
grid:                                  # ordered [param_id, domain] pairs (D8 order = identity)
  - [toy_plant__Toy_Plant__plant_budget, [1000.0, 3000.0, 6000.0]]
fixed: { toy_plant__Toy_Plant__plant_length: 4.0, ...unit_cost: 250.0, ...width: 3.0 }
policy:
  name: objective/v1
  objectives: [ { output: cost, role: minimize } ]
  response_roles: {}
budget: null                           # optional int cap (D9)
retention: keep                        # keep | gc_after (D9)
```

## Non-Goals

- Visualization/plotting; optimizer configuration and adaptive-strategy feedback (`feed-strategy`
  is classified, not wired).
- Contract authoring/sealing; the query consumes the fixture catalog and the `ModelContract` seam is
  named, not bridged.
- True cross-fingerprint (multi-store) tracking-key correlation; the query only surfaces each
  result's `executable_fingerprint` boundary (orchestrator D-track; note for Item 14 docs).
- Any change to the evaluator or the store/runner crash-safety contracts. All changes are additive.
- A Python-entrypoint `create` shape (orchestrator picked lean Option A; can be added later without
  breaking A).

## Implementation Notes

- **Provision teax's own venv first** (spec prerequisite; Items 10/11 did the same). The end-to-end
  test runs the real evaluator over the sealed package.
- **`entry_model` resolution:** use `getattr(evaluator.package, config.entry_model)`, not the
  fixture-specific `evaluator.ToyPlantParams` attribute — keep the CLI package-agnostic.
- **Synthesized validator** must mirror `conftest.validate_proposal`: numeric-and-not-bool coercion
  to `float`, then merge `fixed` fields into the canonical map. Non-finite is valid (it evaluates to
  `indeterminate`), malformed/missing/wrong-type returns `None`.
- **Grid + fixed:** the strategy proposes only variable fields; the validator injects `fixed`.
  Fields in neither fall to the entry model's own defaults (bridge behavior, `bridge.py:18`).
- **Provisional `model_contract_fingerprint`:** derive from a digest of the catalog file bytes and
  label it a provisional stand-in until Item 9 (`conftest` uses a literal; a catalog digest is
  more honest and still stable). Do not invent a `ModelContract`.
- **New-lineage message** must be actionable: name the differing binding and tell the user a new
  store path (or reverted config) is needed — never a bare `IncompatibleStore` traceback.
- **`decode_evidence`** must reject nothing the encoder produced and must leave genuine one-key
  dicts unmolested only if they are the sentinel shape; mirror `_tag_nonfinite`'s recursion exactly.

## Potential Risks

- **Fingerprint drift on resume (B1).** If any definition-shaping input is omitted from the
  semantic digest (D2), resume mis-binds. *Mitigation:* the acceptance test (INV-4) is a
  create→run→crash→resume round-trip that fails loudly on any drift; unit-test the digest over a
  config edited in each field.
- **Genuine `assessment_failed` not exercised by the happy grid.** `cost` is present for every real
  grid point, so the natural grid never fails extraction. *Mitigation:* a dedicated policy test
  configures an objective on a missing output ID to hit the rule genuinely; the end-to-end test
  need not itself fail assessment (spec lists the two as separate criteria).
- **Config path portability.** Absolute `package.dir` in the config is environment-specific.
  *Mitigation:* excluded from the fingerprint (D2); resume still works if the package moved, as long
  as its sealed bytes (→ `executable_fingerprint`) are unchanged.
- **Budget wrapper changes strategy identity.** A `BoundedStrategy` alters `strategy_config`.
  *Mitigation:* correct by design (a bounded study is a distinct lineage); its `config_fingerprint`
  includes both the inner config and the bound. Budget is optional (D9).

## Integration Strategy

Purely additive over certified code. The CLI is a new console entry point in `teax-simkit`; the
policy/definition/evidence_io extensions default to the current behavior so all Item 10/11 tests keep
passing. Nothing in `evaluation/` or the store/runner crash-safety path changes. The catalog read is
the named seam to Item 9's `ModelContract`.

## Validation Approach

- **Acceptance (INV-4), `test_cli_end_to_end.py`:** write a grid config; `create`; `run --crash-at
  before_commit:<mid candidate>` in a subprocess (exits 137); `resume`; then a reference
  uninterrupted `create`+`run` over the same config. Assert the resumed store's `ordered_cases()`
  equals the reference's — case order, states, and `evidence_digest`s byte-identical.
- **Policy unit tests:** all four dispositions produced from crafted evidence; disposition ⊥ state
  (INV-2); genuine `AssessmentFailed` on a missing objective ID and on an unresolved response role;
  raw (un-normalized) penalty value; evidence-digest identical across dispositions (INV-1).
- **Query unit tests:** three states × three verdict classes surfaced and filterable; sentinel
  round-trip (INV-3) over nan/inf/-inf in responses/outputs/report; catalog join surfaces source
  form/membership kind/polarity/owner/display predicate by `constraint_id`; every result carries
  `executable_fingerprint` (INV-5); `IncompatibleStore` → new-lineage message (not a traceback).
- **Suite green + Ruff clean** (spec success criterion).

## Next-Stage Handoff

- **Fixed** (do not relitigate): CLI Option A declarative config (orchestrator D-CLI); tracking-key
  scoped to surfacing the fingerprint boundary (D-track); `[HARD]` non-mutation, evidence-preserving
  `assessment_failed`, sentinel decode, resume-refuses-changed-fingerprint, three-states-×-three-
  verdicts; `decode_evidence` lives beside `encode_evidence` (D5); policy closes over config, runner
  call site untouched (D3).
- **Open (plan decides mechanism):** exact `ObjectiveSpec`/`response_roles` field shapes and the
  penalty-threshold config; the console-script name (`teax-study` proposed); `inspect` output
  rendering (table vs. JSON lines).
- **De-risk first:** INV-4, the create→run→crash→resume→query round-trip. It exercises the config
  round-trip (B1), the crash seam (D8), and the query join in one test. Build the config schema +
  the semantic fingerprint (D2) before anything else, then stand up the end-to-end skeleton against
  the real evaluator so the resume-identity property is proven early.
- **Low-stakes / droppable:** budget/retention interpretation (D9) — not load-bearing for
  acceptance; ship if cheap, defer if it fights the schedule.

---

**Next Step:** After approval → `/_my_plan`. No `design_review` warranted — the surfaces are forced
by the certified seams and the spec's `[HARD]` items; the only judgment calls (disposition mapping,
budget/retention) are low-stakes and reversible.
