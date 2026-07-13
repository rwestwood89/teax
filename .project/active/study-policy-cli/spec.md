# Spec: Study Policy, Query, and CLI Surface (Item 12)

**Status:** Draft
**Owner:** Reid W
**Created:** 2026-07-12
**Complexity:** MEDIUM
**Branch:** constraint-exec-epic

---

## Problem

Items 10 and 11 built the study machine but left no way for a person to drive it. The
evaluator (Item 10) turns typed inputs into immutable `ModelEvidence`; the store, runner, and
strategies (Item 11) run a list or grid of candidates crash-safely and commit one case per
candidate. All of that is reachable today only from Python test code: a study is a
hand-assembled `StudyDefinition`, the policy is a stub (`DispositionPolicy`) whose only real
job is to exercise the `assessment_failed` path, and reading results back means writing raw
SQL against the store and hand-decoding the non-finite sentinel in staged artifacts.

Three gaps remain, and they are the whole point of the study layer for a user:

- **Policy is a stub.** `DispositionPolicy` maps a headline to a disposition string and fails
  assessment only for an injected set of candidate IDs (`study/policy.py:31`). The concept's
  policy — the user-selected *interpretation* of evidence, which decides whether a verdict
  means reject the point, penalize it, keep it for a boundary plot, or feed it back to a
  strategy — does not exist yet.
- **There is no query surface.** Results live across three places (the `cases` row's inputs
  and state, the content-addressed evidence artifact, the catalog), and nothing joins them.
  A user cannot ask "which points violated constraint X" or "show me the boundary" without
  raw SQL and manual sentinel decoding.
- **There is no CLI.** The repo has no console entry point at all. The concept's define → run
  → interrupt → resume → inspect story has no surface a user can invoke.

This item builds those three surfaces on top of the certified code, changing nothing in the
evaluator or the crash-safe store/runner contracts.

## Success Criteria

- [ ] **Grid study runs end-to-end from the CLI:** define → run → interrupt → resume → query,
  over the sealed fixture package, with the resumed store's ordered cases identical to an
  uninterrupted run (byte-identical case order, states, and committed evidence digests).
- [x] **The full policy protocol interprets evidence into the four dispositions** (reject,
  penalize, keep-for-boundary, feed-strategy) and **never mutates stored evidence**; a
  policy-*rejected* point is a `completed` case that still carries its outputs and violation
  verdicts (a boundary-plot point), distinct from an `assessment_failed` case.
- [x] **Policy failure yields `assessment_failed` with evidence intact** — reachable through a
  real objective/policy extraction failure, not only the test-only injected reject set.
- [x] **The query distinguishes both axes:** the three case states
  (`completed | execution_failed | assessment_failed`) and the three verdict classes
  (`satisfied | violated | indeterminate`), and can filter cases by parameter, output,
  constraint ID, status, and assessment.
- [x] **The query read path decodes the non-finite sentinel:** a NaN or infinite output or
  observed operand in a staged artifact reads back as a real non-finite float (or an explicit
  non-finite marker), never as the raw `{"__nonfinite__": …}` dict.
- [x] **Resume refuses a changed fingerprint with a new-lineage message** instead of mixing
  datasets, and the query can join static source detail (source form, membership kind,
  polarity, owner) through the catalog keyed by `constraint_id`.
- [ ] teax suite green; Ruff clean.

## Known Requirements

Grading: behaviors forced by the certified Item 10/11 code or the fixture are `[HARD]`;
intents carried from the owner-ratified concept/epic are `[INHERITED]` with source cited;
`[INFERRED]` marks a reading not stated verbatim. See `capture-fidelity.md`.

### Policy — interpretation over immutable evidence

- **[INHERITED]** **The policy is the user-selected interpretation of one evaluation's
  evidence, producing one of four dispositions: reject, penalize, keep-for-boundary,
  feed-strategy.** Compute/judge/decide are separate: the policy is the only place a verdict
  becomes a decision about the exploration. (concept Design Principle 1, "Study Layer", Vocabulary
  `study policy`; epic Item 12 §1.)
- **[HARD]** **Assessment never mutates stored evidence.** `ModelEvidence` is a frozen
  `StrictBaseModel` (`evaluation/evidence.py:45`); the runner serializes evidence to the
  artifact independently of the assessment (`study/runner.py:_assess_and_commit`). The full
  policy receives evidence read-only and returns a separate assessment record; the artifact
  bytes are unchanged by it. (concept Required Invariant "policy assessment never mutates
  stored evidence".)
- **[HARD]** **`assessment_failed` preserves the real evidence.** When the policy raises
  `AssessmentFailed`, the runner still stages the true `evidence_json` and commits an
  `assessment_failed` case beside it (`study/runner.py:133–143`) — never a stub. The full
  protocol keeps this contract. (concept Edge Cases "Objective extraction or policy fails:
  evidence is preserved in an assessment-failed record, never relabeled model failure".)
- **[INFERRED]** **`assessment_failed` becomes reachable through a genuine extraction/policy
  error, not only the injected `reject_candidate_ids` set.** That set is a documented test
  affordance the deterministic fixture needs (`study/conftest.py`); the production protocol
  fails when, for example, an objective it must extract is absent or non-numeric — matching
  the concept's "objective extraction or policy fails". The injected-set affordance may remain
  for tests but is not the only path.
- **[INFERRED]** **A policy *disposition* is orthogonal to the case *state*.** "Reject" is a
  policy verdict recorded in the assessment of a `completed` case, not the `assessment_failed`
  case state (which means the policy itself broke). This distinction must be explicit so a
  boundary-plot query can find policy-rejected points among `completed` cases.
- **[INHERITED]** **"Penalize" carries a raw objective/penalty value, never a normalized
  one.** Penalties and objectives are extracted as modeled quantities; inventing a normalized
  penalty scale is a non-goal. (concept Non-Goals "Invent … normalized penalties".)
- **[INHERITED]** **The study selects objectives by output ID and response roles; the policy
  cannot redefine a predicate.** `StudyDefinition` was specified to carry objectives and
  response roles (Item 11 `spec.md#studydefinition`), though the dataclass carries only
  `budget`/`retention` as uninterpreted `Any` today (`study/definition.py:44`). Item 12 gives
  objectives/response roles their interpretation for the policy to consume. (concept "Study
  Layer"; epic Item 12 §1.)

### Query — results joined through the catalog

- **[INHERITED]** **Results query by parameter, output, constraint ID, status, and
  assessment.** (concept "Inspect and Resume".)
- **[HARD]** **The query reads three stores and joins them:** the `cases` row
  (`inputs_json` = parameters, `state`, `assessment_json`), the content-addressed evidence
  artifact reached via `evidence_digest` (selected `outputs`, per-constraint `responses`, the
  opaque `report`), and the catalog. (`study/store.py` schema; `study/evidence_io.py`
  payload shape.)
- **[HARD]** **The read path decodes the non-finite sentinel.** `encode_evidence` tags every
  non-finite float as `{"__nonfinite__": "nan"|"inf"|"-inf"}` recursively across responses,
  outputs, provenance, and report (`study/evidence_io.py:20`). The query's decode is the exact
  inverse: a tagged value reads back as the corresponding real float (or an explicit
  non-finite marker), and a nested one-key `{"__nonfinite__": …}` never leaks to the caller as
  a dict. This is the read half of Item 11's D3 write path. (brief Notes; `study/evidence_io.py`.)
- **[INHERITED]** **Static source detail joins through the catalog, keyed by `constraint_id`.**
  A per-constraint verdict in a case (e.g. `toy_plant__demo_plant__affordable → violated`)
  joins to the catalog's concrete entry and its source record to surface source form,
  membership kind, polarity, owner, and display predicate — so a query can group failures by
  modeled constraint while naming the failing instance. (concept "Catalog, Evaluation, and
  Report"; fixture `contracts/constraint_catalog.json`.)
- **[HARD]** **The catalog available to this item is the sealed fixture's
  `constraint_catalog.json`** — `source_records` (keyed by `usage_name`) and
  `concrete_entries` (keyed by `constraint_id`, referencing `source_usage`). Item 9's
  `ModelContract` is not yet built; the query consumes the fixture's catalog shape and the seam
  to `ModelContract` is named, not bridged. (brief Notes; epic Item 9 lands later in
  sysml-codegen.)
- **[INHERITED]** **The query distinguishes the three case states and three verdict classes.**
  States (`completed | execution_failed | assessment_failed`) come from the `cases.state`
  column; verdict classes (`satisfied | violated | indeterminate`) come from the evidence
  `responses`/report. Both axes are filterable and reported. (epic Item 12 success criteria;
  `study/store.py`, `evaluation/evidence.py:16`.)
- **[INHERITED]** **Tracking-key correlation shows fingerprint boundaries — names correlate,
  never equate.** A `tracking_key` names a logical constraint across model versions; correlated
  results whose evidence spans different executable fingerprints must be shown *as* spanning a
  boundary, never merged into one constraint. (concept "Concrete Lowering" `tracking_key`
  paragraph; epic Item 12 §2.)
- **[INFERRED]** **For this item, tracking-key correlation is scoped to surfacing the boundary,
  not spanning stores.** One `StudyStore` binds exactly one `executable_fingerprint`
  (`study/compatibility.py`), and the fixture catalog carries no `tracking_key`. The realizable
  deliverable is: every query result carries its `executable_fingerprint`, and the correlation
  contract marks the boundary — so a consumer that later correlates across fingerprints cannot
  silently equate them. True cross-fingerprint correlation needs `tracking_key` in the catalog
  (Item 5/9) plus multi-store data; that mechanism is deferred (see Open Questions). *(Surfaced
  per capture-fidelity Law 4 rather than silently narrowed.)*

### CLI — create / run / resume / inspect

- **[INHERITED]** **The CLI provides create, run, resume, and inspect contracts** over one
  study, and a grid study runs end-to-end through them over the sealed fixture package. (epic
  Item 12 §3 + success criterion; concept "Run a Study", "Inspect and Resume".)
- **[HARD]** **Resume refuses a changed fingerprint and starts a new lineage.** Reopening a
  store whose bound compatibility differs raises `IncompatibleStore`
  (`study/store.py:_check_compatibility`); the CLI must catch it and render a new-lineage
  message rather than a stack trace. The compatibility binding is the eight fields in
  `study/compatibility.py` (executable, model-contract, study-definition fingerprints; schema
  versions; strategy identity and order-sensitive config). (concept Required Invariant "Resume
  joins on study lineage … never on constraint IDs alone"; epic Item 12 §3.)
- **[HARD]** **Resume requires the study definition to be persistent and reconstructable.** The
  store binds only the *compatibility fingerprints*, not the live `StudyDefinition` (its
  strategy object, `entry_model` type, validator, and policy) — and the runner needs a live
  definition to propose and evaluate (`study/runner.py:45`). So resume must rebuild the same
  definition from a re-readable source and hand it to the runner; the store then checks
  compatibility. (`study/definition.py`, `study/store.py`.)
- **[HARD]** **Resume is idempotent by candidate.** The runner skips any candidate whose case
  already exists (`store.has_case`, `study/runner.py:62`), so a resumed run reproduces the
  uninterrupted run's ordered cases exactly — the property the end-to-end test asserts. (Item 11
  Required Invariant; `study/runner.py`.)
- **[INHERITED]** **A rejected point retains its outputs and violations for boundary plots.**
  A policy-rejected point is a `completed` case with full evidence staged; the CLI/query
  exposes those outputs and violation verdicts. (concept "Run a Study"; epic Item 12 §3.)

### Cross-cutting

- **[HARD]** **Model, assessment, and persistence failures stay phase-distinct end to end.**
  The CLI/query must not collapse an `execution_failed` case, an `assessment_failed` case, and
  a feasible-but-`indeterminate` verdict into one bucket — the runner already keeps them
  distinct (`study/runner.py`); the surfaces preserve that. (concept "Run a Study"; Required
  Invariant "Proposal records and the three case states never merge".)

## Implementation Prerequisites (not API requirements)

- **Provision teax's own venv as the first implementation step**, as Items 10 and 11 did —
  teax's own environment is broken for real-simkit runs and the spikes borrowed the
  fusion-tea/agentic-mbse venv with a `PYTHONPATH` graft. This is a sequencing prerequisite,
  not a contract of the policy/query/CLI surface. (epic Risks "teax environment provisioning".)

## Non-Goals

- **Visualization and plotting.** The query retains the data a boundary plot needs; it draws
  nothing. (epic Item 12 Out of Scope.)
- **Optimizer configuration and adaptive strategies.** Only prepared lists and grids exist;
  `observe()` is inert. The policy may *classify* a feed-strategy disposition, but wiring that
  feedback into an adaptive strategy is deferred with S7. (epic Item 12 Out of Scope; concept
  "Study Layer"; `study/strategy.py`.)
- **Contract authoring or sealing.** `ModelContract`/`PackageContract` derivation is Item 9;
  this item *consumes* the fixture's catalog and package.
- **True cross-fingerprint (multi-store) tracking-key correlation.** Deferred; needs
  `tracking_key` in the catalog and multi-store data (see Query requirements and Open
  Questions).
- **Changing the evaluator or the store/runner crash-safety contracts.** Item 12 is additive
  over certified code.

## Open Questions / Deferred to design

- **CLI study-definition source — the shape of "create" (owner decision at design).** `create`
  must produce a persistent, re-readable definition that `resume` can reconstruct (a `[HARD]`
  requirement above). Two mechanisms, both meeting it:
  - *(A) Declarative study-config file* (e.g. YAML/JSON) naming the sealed package, grid
    variables/domains by parameter ID, the strategy, a policy (by name/config), and
    budget/retention. The CLI resolves `entry_model` from the loaded package and synthesizes
    the grid proposal-validator. Most CLI-native; most build.
  - *(B) Python-entrypoint reference* — `create` points at an importable module that returns a
    `StudyDefinition`; the CLI owns the run/resume/inspect/query lifecycle around it. Thinner;
    "define" stays in Python.
  *Recommendation:* a lean (A) sufficient for the grid case (package ref + variables/domains +
  a built-in disposition/objective policy + synthesized validator), with the policy selectable
  from a small registry. This is what makes the end-to-end grid test real inside the 1-day
  budget. Reserve the final call for the owner at design, as Item 10 reserved its entry-source
  shape.
- **Where objectives and response roles live** — extend the `StudyDefinition` dataclass
  (currently `budget`/`retention` as `Any`) with typed objective/response-role fields, versus
  carrying them in the policy's own config. Interacts with the study-definition fingerprint.
- **The objective-extraction failure rule** — exactly which conditions (missing output ID,
  non-numeric objective, unresolved response role) raise `AssessmentFailed`. Design should
  state the rule rather than leave it implicit.
- **Query result shape and how much reads eagerly** — whether the query returns typed records
  or dicts, and whether it decodes/join-loads every evidence artifact eagerly or lazily.
  Mechanism; defer.
- **Tracking-key correlation scope confirmation** — whether design commits only to surfacing
  `executable_fingerprint` per result (the inferred single-store scope above) or reaches for a
  cross-store correlation contract now. Flagged so it is decided deliberately, not by default.
- **CLI packaging** — the console-script entry name and whether it ships in `teax-simkit`'s
  `pyproject.toml`. Mechanism; defer.
- **Budget and retention interpretation** — how `budget` bounds a run and how `retention`
  interacts with the store's GC. Carried uninterpreted by Item 11; design decides the rule.

---

## Related Artifacts

- **Epic:** `.project/reference/epic_constraint_execution.md` — Item 12 (canonical:
  sysml-codegen `.project/backlog/epic_constraint_execution.md`).
- **Required Reading (from the epic):**
  - `.project/reference/constraint-execution-concept.md` — "Study Layer"; "How It Works" (Run a
    Study; Inspect and Resume); Vocabulary; Design Principle 1; Required Invariants (Study
    Execution); Edge Cases.
- **Depends on (certified on this branch):**
  - Item 11 — `.project/active/study-store-runner/` (store DDL, runner, strategies,
    `DispositionPolicy` stub, sentinel encoding, compatibility binding, lease).
  - Item 10 — `.project/active/model-evaluator/` (`ModelEvidence`, failure taxonomy,
    projection vocabulary).
- **Code specced against:** `simkit/study/` (policy, store, runner, definition, strategy,
  evidence_io, compatibility, bridge, identity, failures); `simkit/evaluation/` (evidence,
  projection, failure, evaluator); fixture
  `simkit/tests/evaluation/fixtures/sealed_package/package_live/contracts/constraint_catalog.json`.
- **Design:** `.project/active/study-policy-cli/design.md` (to be created).

---

**Next Steps:** After approval, proceed to `/_my_spec_review` (fresh session), then
`/_my_design`. Design must resolve the reserved CLI study-definition shape with the owner.
