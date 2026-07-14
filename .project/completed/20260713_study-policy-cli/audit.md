# Audit: Study Policy, Query, and CLI Surface (Item 12)

**Verdict:** Certify-with-notes
**Audited:** 2026-07-12
**Branch:** constraint-exec-epic
**Commit:** 3b9a79b (audited tree: through 6dbac82, Item 12 Phase 5)

---

## Summary

The three surfaces the spec calls for — full policy, query, and CLI — are all present, and the
implementation is a faithful, additive adapter over the certified Item 10/11 machinery. Every
`[HARD]` contract I could check by reading holds structurally: the runner encodes evidence *before*
assess runs, so non-mutation and evidence-preserving `assessment_failed` are guaranteed by
construction; the catalog join, sentinel decode, four dispositions, and new-lineage refusal are all
implemented and backed by well-constructed tests. No certified code drifted — `evaluation/` and the
store/runner/crash-safety files carry zero Item 12 commits; `study/definition.py` gained only the
two named additive fields.

The one real limitation of this pass: **I could not execute any suite.** Python/pytest is gated
behind an approval prompt with no human to answer it (non-interactive orchestration session). So the
"suite green / Ruff clean" criterion and the observed *pass* of the acceptance test are delegated to
the orchestrator as live probes. I verified those tests *exist and are correctly constructed*, not
that they pass on this machine. The implement notes report them green.

Despite the terse implement report, I found **no unrecorded deviations** — the code matches the plan
phase-by-phase, and the two small interpretation choices below are defensible supersets, not cuts.

## Findings

### Plan completion

All five phases verified as implemented against the code:

- **Phase 1** — `study/config.py` (`StudyConfig`, `load_study_config`, `semantic_fingerprint()`
  excluding the `package` block, `config.py:60-71,79-84`); `ObjectiveSpec` frozen dataclass
  (`policy.py:19-29`); additive `objectives`/`response_roles` on `StudyDefinition`
  (`definition.py:44-47`, `field(default_factory=dict)` per the frozen-dataclass gotcha). ✔
- **Phase 2** — `build_definition` (`config.py:108-143`), package-agnostic `entry_model` via
  `getattr(evaluator.package, config.entry_model)` (`config.py:113`), synthesized validator
  mirroring `conftest.validate_proposal` (`config.py:87-105`), catalog-bytes
  `_model_contract_fingerprint` (`config.py:79-84`), CLI `create|run|resume|inspect`
  (`cli.py`), `[project.scripts] teax-study` (see note below). ✔
- **Phase 3** — full `ObjectivePolicy` with all four dispositions, the objective-extraction failure
  rule, and raw penalty (`policy.py:87-139`). ✔
- **Phase 4** — `decode_evidence`/`_untag_nonfinite` beside the encoder (`evidence_io.py:54-71`);
  `StudyQuery`, `CaseView`, `CatalogView`, memoized-by-digest decode, catalog join
  (`query.py`). ✔
- **Phase 5** — `cmd_inspect` JSON-lines + filter flags (`cli.py:93-110,134-146`);
  `BoundedStrategy` for `budget`; `store.gc()` on `retention: gc_after` (`cli.py:86-87`). ✔

No placeholder code, TODOs, or partial implementations found. `inspect`'s Phase-2 `NotImplementedError`
stub was genuinely replaced in Phase 4/5.

### Spec conformance

Success criteria (evidence per item; execution-dependent confirmations flagged):

1. **Grid study end-to-end from CLI (define→run→interrupt→resume→query), resumed identical to
   uninterrupted.** Test present and correctly built (`test_cli_end_to_end.py:36-56`). The interrupt
   is a **real crash**: a subprocess `python -m simkit.study.cli run --crash-at
   before_commit:<2nd candidate>` that `os._exit(137)`s (`crash.py:33`, asserted `rc == 137`) at the
   `before_commit` seam where the artifact is durable but the case row is *not yet committed*
   (`store.py:396`). The comparison covers the identity columns `(candidate_id, state,
   evidence_digest, inputs_json)` in `commit_order` (`ordered_cases()`, `store.py:415-417`), correctly
   excluding `attempt_id`/`commit_order`. Resume genuinely skips committed cases via
   `store.has_case` (`runner.py:62`), covered by the idempotence test
   (`test_cli_end_to_end.py:59-67`). **Not executed this session** — pass delegated to live probe.

2. **Four dispositions; never mutates evidence; policy-reject = completed case with evidence vs
   assessment_failed.** All four dispositions implemented (`policy.py:72-76,122-139`) and unit-tested
   individually (`test_policy.py:40-77`). Non-mutation is **structural, not incidental**: the runner
   computes `evidence_json = encode_evidence(evidence)` at `runner.py:130` *before* calling
   `policy.assess` at `runner.py:132`, and `ModelEvidence` is a frozen `StrictBaseModel`; the policy
   returns a separate dict. INV-2 (disposition ⊥ state) is proven through the **real runner**: a
   violated point lands `completed` with `assessment_json.disposition == "reject"`, not
   `assessment_failed` (`test_policy.py:125-138`). ✔

3. **Policy failure → `assessment_failed` with evidence intact, via a real extraction failure.**
   `ObjectivePolicy` raises `AssessmentFailed` on a genuinely absent objective output or an
   unresolved response-role constraint (`policy.py:107-119`), unit-tested for both
   (`test_policy.py:80-91`), distinct from Item 11's injected `reject_candidate_ids`. On the raise,
   the runner still stages the true `evidence_json` and commits `assessment_failed`
   (`runner.py:133-143`, certified). *Note:* no single test drives a genuine `ObjectivePolicy`
   extraction failure all the way to an `assessment_failed` case row — the runner-level
   `assessment_failed` diversity in `test_query.py` uses the injected `DispositionPolicy`. The path is
   covered by composition (genuine raise + certified runner handling), not one integration test. Minor.

4. **Query distinguishes both axes and filters by parameter/output/constraint/status/assessment.**
   Three case states surfaced and filterable (`test_query.py:41-53`); verdict classes surfaced from
   evidence responses (`query.py:90-95`). Filters: `parameter`/`output`/`constraint` (key-presence),
   `state`, `disposition` (`query.py:118-143`). *Note (defensible superset):* the query surfaces
   **four** verdict classes including `not_assessed`, where the spec names three
   (`satisfied|violated|indeterminate`); this is more complete, not a cut. "status"→`state` and
   "assessment"→`disposition` are reasonable mappings of the spec's filter words. ✔

5. **Read path decodes the non-finite sentinel.** `decode_evidence` is the exact recursive inverse of
   `_tag_nonfinite` (`evidence_io.py:54-71`); `StudyQuery` runs it on the on-disk artifact bytes
   (`query.py:77-82`). Round-trip tested over nan/inf/-inf in outputs and report
   (`test_evidence_io.py:45-67`), asserting no `__nonfinite__` leaks. *Note:* the brief's stricter
   reading — a NaN round-tripping specifically through **store→StudyQuery** — is covered by composition
   (`encode` output is the artifact bytes; JSON-round-trip stability asserted at
   `test_evidence_io.py:29-32`; `StudyQuery` calls the same `decode_evidence`) but not by one
   end-to-end test that writes a NaN artifact and reads it back through `StudyQuery`. Minor. ✔

6. **Resume refuses a changed fingerprint with a new-lineage message; catalog join by
   `constraint_id`.** `_open_store` catches `IncompatibleStore` and prints an actionable message
   naming the store and remedy (`cli.py:40-59`); tested for `rc==1`, "lineage" present, no "Traceback"
   (`test_query.py:81-92`). The catalog join `constraint_id → source_usage → source_record`
   (`query.py:52-65`) was verified against the **sealed fixture's actual catalog**: the keys
   `usage_name`/`source_form`/`owner_qn`/`definition_qn`/`predicate_ir`/`membership_kind`/`is_negated`
   all exist, and `toy_plant__demo_plant__affordable → source_usage "affordable" → usage_name
   "affordable"` resolves (`test_query.py:56-62`). ✔

7. **teax suite green; Ruff clean.** **Not executed this session (gated).** Requested live probes.

Tagged requirements: the `[HARD]` items (non-mutation, evidence-preserving `assessment_failed`, three
stores joined, sentinel decode, catalog is the fixture's, three states × verdict classes, resume
refuses changed fingerprint, resume idempotent by candidate, phase-distinct failures) are all met per
the above. The `[INHERITED]` "penalize carries a raw value" is met (`policy.py:133`,
`test_policy.py:64-69`). Non-goals respected — no plotting, no adaptive-strategy wiring (`observe`
stays inert, `strategy.py:69`), no contract authoring, no evaluator/store changes.

### Design conformance

Implementation follows the design. Spot-checks:

- **D2** semantic digest excludes filesystem locations — the whole `package` block is excluded, not
  just `dir` (`config.py:60-71`); tested by moving `package_dir` to `/elsewhere`
  (`test_config.py:16-21`) and by per-field shift over 7 shaping fields (`test_config.py:24-28`). ✔
- **D3** policy closes over config; `assess(evidence, *, candidate_id)` signature and the
  `runner.py:132` call site are untouched. ✔
- **D5** `decode_evidence` lives beside `encode_evidence`, one home. ✔
- **D8** interrupt via the certified `CrashController` through a hidden `--crash-at` (`cli.py:129-131`,
  `argparse.SUPPRESS`), not a `SIGKILL`. ✔
- **D9** `BoundedStrategy.config_fingerprint` folds in inner config + bound (`bounded_strategy.py:19-22`)
  and `identity` appends `+bounded/v1`, so a bounded study is a distinct lineage; the compatibility
  binding does carry `strategy_identity`/`strategy_config` (`definition.py:60-61`,
  `compatibility.py:20-21`). ✔
- **INV-5** every result carries `executable_fingerprint`, from evidence provenance when present else
  the store's bound value — equal by construction (`query.py:88-95`, `test_query.py:65-70`). ✔

### Code integrity

No slop or failure-honesty problems found.

- `ObjectivePolicy.assess` reads as one operation; the failure rule raises loudly rather than
  returning a safe default (`policy.py:107-119`) — correct honesty for an invariant boundary.
- `decode_evidence`/`_untag_nonfinite` mirror the encoder's recursion exactly and touch no non-sentinel
  one-key dict (`evidence_io.py:54-61`).
- `POLICY_REGISTRY` factory carries an unused `config` param (`policy.py:99`, `142-149`), explicitly
  documented as reserved for future per-name config — an honest, labeled seam, not silent sprawl.
- `cmd_inspect` fails loudly with the path named when the store is missing (`cli.py:94-96`) rather than
  letting `StudyStore` raise a bare error — a genuine caller-error boundary.
- One observation, not a defect: `run` and `resume` share `_cmd_run_or_resume` verbatim
  (`cli.py:126-132`) — they are behaviorally identical (resume is just run over an existing store,
  idempotent by candidate). The two names are a UX affordance; no hidden mode.

---

## Certification

**Certify-with-notes.** Verified by static analysis against spec, design (D1–D9, INV-1–5), and plan:
all three surfaces present and additive; four dispositions; structural non-mutation and
evidence-preserving `assessment_failed`; genuine `AssessmentFailed` extraction rule; catalog join
confirmed against the real sealed-fixture catalog; sentinel decode as exact inverse; resume-refusal
message; no certified-code drift (`evaluation/` and store/runner/crash/compatibility/strategy/identity
carry zero Item 12 commits; `definition.py` gained only the two named additive fields).

Two minor notes (neither blocks certification; both are supersets/composition-covered, not cuts):
- The genuine `ObjectivePolicy` extraction failure is unit-tested but not driven end-to-end to an
  `assessment_failed` case row (the runner-level diversity uses the injected `DispositionPolicy`).
- The NaN sentinel round-trip is tested through `encode/decode` and JSON stability, not through one
  explicit store→`StudyQuery` integration test.

**Checkboxes marked:** spec success criteria 2, 3, 4, 5, 6 marked met (statically verified). Criterion
1 (end-to-end resume identity) and 7 (suite green / Ruff clean) left **unmarked** — their confirmation
requires *observing a run*, which was blocked (see below). Plan phase boxes were already `[x]` from
the implement session; I did not alter them.

**Not checked (requires the orchestrator's live probes — execution was gated in this non-interactive
session, `python`/`pytest` returned "requires approval"):**
- **Requested live probes:** `pytest .../tests/study` (implement notes: 57 green = 29 + 28 new),
  `pytest .../tests/evaluation` (25), the framework suite (green except the 4 known
  `test_no_battery_deps.py` failures), and `ruff check` on the diff.
- **Requested live probe:** actually *running* `test_cli_end_to_end.py` to observe the resume-identity
  assertion pass (the test is present and correctly constructed; I did not see it pass).
- I did not re-install the editable package, so the `teax-study` console script registration
  (`pyproject.toml [project.scripts]`) was not exercised as an installed entry point — tests invoke
  `simkit.study.cli.main` directly, which needs no reinstall.
- I read the fixture catalog's keys and the one `affordable` join by grep, not by loading and
  executing the join in Python.

If the four suite probes come back green and `test_cli_end_to_end.py` passes, this upgrades cleanly to
**Certify** — nothing in the static review is waiting on a code change.

---

## Addendum: probes executed by orchestrator (2026-07-12)

- Study suite: **57 passed** (incl. the CLI end-to-end acceptance test, observed passing: crash → resume → identity-column comparison green). Evaluation: **25 passed**. Framework: exactly the 4 known pre-existing failures. Ruff on `simkit/study`: clean.

**Final verdict: Certify** (upgraded from Certify-with-notes; suites executed).
