# Spec Review: Model Evaluator and Typed Entry (Item 10)

**Spec:** `.project/active/model-evaluator/spec.md`
**Contract:** `claude-pack/commands/_my_spec.md`
**Review File:** `.project/active/model-evaluator/spec-review.md`
**Date:** 2026-07-12
**Reviewer posture:** adversarial; verified against Item 0 findings, S5 findings, `real_evaluator.py`, the concept, the epic, and current teax runtime code (`pipeline_executor.py`, `pipeline_validator.py`).

---

## Reality Check

**Sound.** The spec is about the right work item — it productionizes exactly the seam Item 0 exercised, and its scope boundary against Item 9 (contract/seal) and Item 11 (study store/runner) is drawn where the epic draws it. Seven of the eight Item 0 mismatches are dispositioned to the right item, the reserved gate is genuinely reserved in intent, and the [HARD]/[INHERITED] grades are mostly honest. The must-fixes below are not "wrong work item" problems; they are places where a success criterion rests on something the spec left ambiguous or under-pinned, and where design would be misled by taking the spec's phase/parity/isolation language at face value. No Stage 0 fail — proceed to the full audit.

---

## Audit

### Lens 1 — Faithfulness

**L1-1 · Direct claim (headline normalization vs opaque report — the two [HARD]/[INHERITED] statements are in tension):** The `ModelEvidence` section holds the generated report "as an opaque model artifact" and projects only per-constraint verdicts onto "generic response keys" — and per Item 0 mismatch 5, the per-constraint statuses (`violation`, `indeterminate`) *already match* the policy vocabulary and need no normalization. The only value that needs normalization is the *report headline* (`all_satisfied`→`all-satisfied`, `not_assessed`→`not-assessed`), which lives inside the report the spec says is held opaque. So the [HARD] "Headline vocabulary is normalized in the projection layer" either (a) contradicts the opaque-report model by pulling the headline out and normalizing it, or (b) is not actually needed by Item 10 at all, because a truly opaque report keeps its underscore headline until Item 11's policy reads it. The spike normalized the headline (`HEADLINE_TO_POLICY`, `real_evaluator.py:189`) because S6's `Evidence.report` carried a projected dict — but production `ModelEvidence` holds the report opaque, which is a different shape. **The spec needs to say plainly whether the normalized headline is a projected field of the evidence (and therefore Item 10's job) or stays inside the opaque report (and therefore Item 11's job when policy reads it).** As written, the two statements can't both be literally true.

**L1-2 · Question to the user (does Success Criterion 2 secretly need the canonical vocabulary pinned *in this item*?):** SC2 requires that evaluating a package "returns `ModelEvidence` whose constraint verdicts are projected onto generic response keys" — stated as a closable criterion for Item 10. But the [HARD] headline requirement says "the single canonical headline vocabulary is pinned jointly with Item 9," and Item 9 has not landed. If SC2's "generic response keys" means only the per-constraint statuses, it is testable now (they already match) and the headline deferral is clean. If it includes the normalized headline, SC2 cannot be fully closed until Item 9 fixes the canonical set — the projection would be normalizing to a target that isn't pinned. **Which is it? Either narrow SC2 to per-constraint statuses (and move headline normalization out of Item 10's closable scope), or state that Item 10 pins a *provisional* canonical vocabulary that Item 9 must conform to.** Right now the spec marks the normalization [HARD] (do it now) *and* says the target is pinned elsewhere later (can't fix it now); per capture-fidelity Law 4 that premise conflict should be surfaced, not left for design to trip over.

**L1-3 · Rewrite request (venv provisioning is a process/ops instruction mislabeled as a Known Requirement):** "Provision teax's own venv as the first implementation step" is tagged `[INHERITED]` and sits in "Known Requirements." It is a real and important prerequisite (epic risk table), but it is an implementation-sequencing instruction, not a contract obligation of the evaluator API being specified — nothing about `MappingEntrySource`, `ModelEvidence`, or the failure outcome depends on it. Per Lens 3 hygiene and the spec conventions, this belongs in an "Implementation prerequisites / notes" area, not among the API requirements the design contracts against. Keep it; reclassify it so it isn't read as a functional requirement of the artifact.

**L1-4 · Direct claim (accurate, recorded for the human — the checked-facts that hold):** I verified the load-bearing code claims and they are true: the validator demands an ExitPoint write handler per output type unconditionally (`pipeline_validator.py:326`, `has_handler` check with no persist guard) — the [HARD] "validator requires ExitPoint write handlers even in no-persist mode" is correct; validation runs once at `build_graph`→`validate` (`pipeline_executor.py:104`) and `run` executes modules per case with no re-validation (`pipeline_executor.py:126–140`) — the prepare-once/fresh-context split is real; the spike's `evaluate` ignores `attempt_number` (`real_evaluator.py:236`) — the [HARD] "protocol carries no `attempt_number`" is faithful; and `ToyPlantParams` is a non-strict float model, so non-finite passes construction — the [HARD] non-finite requirement is grounded. No false code claims found.

### Lens 2 — Problem & Approach

**L2-1 · Direct claim (the failure taxonomy does not map onto teax's real phases — "different phase" is misleading for two of the three cases):** SC3 and the normalized-failure section say a module exception and a schema/validation failure are "distinguishable by phase/cause." Walk teax's real per-case failure paths in a *prepared in-memory* backend:
  - **Pre-execution:** the entry source rejects missing/extra/wrong-type keys before any module runs (`MappingEntrySource.validate`). This is a genuinely distinct phase.
  - **Prepare-time (once, not per case):** `PipelineValidator` failures — missing write handler, producer/declaration type mismatch (`pipeline_validator.py:326,362`). A whole study hits these once at prepare, never per case.
  - **Module execution:** everything raised inside `module.run()` — an arbitrary module exception, a Pydantic `ValidationError` (generated modules validate inside `run()`), the aggregator's exact-schema rejecting a missing result, a `MultiOutput` missing field (`pipeline_executor.py:205`), a field-extraction failure (`:397`). The spike lumps *all* of these into one `ExecutionFailed` with the type name in the message string (`real_evaluator.py:245`).

  The problem: a "module exception" and an in-`run()` "schema/validation failure" are the **same executor phase**; they differ only by *cause* (exception type), not phase. And the concept itself buckets "missing inputs, schema failures, thrown predicate code, or a missing aggregator field" all as *execution failures* (concept Graph-and-Evaluation invariant) — one phase. So SC3's "three distinguishable places... different phase/cause" is only clean if "schema failure" means the *pre-execution entry rejection* (a real separate phase), not the *in-execution* aggregator schema failure. **The spec must enumerate teax's actual phase set (pre-execution entry validation; prepare-time topology validation; module execution; output write) and map each real failure to exactly one — and say explicitly whether "schema/validation failure" in SC3 is the pre-execution one or the in-`run()` one.** As written, design could build a taxonomy that claims a phase distinction teax doesn't provide, and the kept test for SC3 would be ambiguous about which "schema failure" it exercises.

**L2-2 · If-then tradeoff (the parity equivalence class is not stated precisely, and non-finite values break naive comparison):** SC "Both backends agree" and the [INHERITED] parity requirement say the two backends return "equivalent selected outputs and constraint results," but never define the equivalence class: which outputs are "selected," and what is *excluded* (provenance, timestamps, input digests, artifact paths, the opaque report's on-disk encoding). This matters concretely because of non-finite values: the file-backed path round-trips a NaN margin through JSON (the spike tags it `{"__nonfinite__": "nan"}`, `real_evaluator.py:200`), while the in-memory path keeps a real `float('nan')` — and `NaN != NaN`, so a naive field compare fails on exactly the indeterminate case the whole architecture exists to preserve. **The parity test's equivalence class needs to be pinned: which fields are compared, which are excluded, and how non-finite operands compare across a JSON-round-tripped backend and an in-memory one.** If left to design as-is, two engineers would write materially different parity tests, and the obvious one would spuriously fail on indeterminate cases.

**L2-3 · Question to the user (is `runtime-types-never-import-generated-classes` stated as a *test*, or only as a property?):** SC2 asserts "no generated class imported by any runtime type," and the [INHERITED] requirement restates it as a property ("depend only on generic/runtime types... never imported"). Unlike SC1, which explicitly says "kept teax tests," SC2 gives no mechanism that would *catch a regression*. The natural enforcement is an importability/isolation check — e.g., import the runtime evidence/evaluator module in an environment where the generated package is absent from the path and assert it loads, or an AST/import-graph assertion that no runtime module names a generated symbol. **Should this be an explicit kept isolation test (recommended — it's the only thing that keeps the concept's central "runtime never depends on generated classes" bet from silently rotting), or is the property-level statement intentionally left to design?** As written it reads aspirational, not testable.

### Lens 3 — Pipeline Risk

**L3-1 · Question to the user (reserved-gate leak: the kept-test meaning of "wrong-type rejection" shifts with the reserved choice, and the Known Requirements lean Shape B):** The [HARD] "entry source rejects missing, extra, and wrong-type inputs before execution" and SC1's "pre-execution rejection of... wrong-type entry inputs" attribute wrong-type rejection to *the entry source*. But the reserved section says under **Shape A** the wrong-type diagnostic "fires at bridge construction, not inside the entry source" (the bridge is Item 11) — under Shape A the source only refuses a wrong *channel-model instance*, not a wrong *field value type*. So "wrong-type rejection" means channel-model granularity under A and field-value granularity under B, and the kept test SC1 promises changes shape with the owner's choice. S5's probe (and `real_evaluator.py:119`) is Shape A — its "wrong-type" test is a channel-model isinstance check. **This is a soft leak: the Known Requirements and SC1 are written as if the source does field-level type rejection (Shape B behavior), which quietly disadvantages Shape A.** The fix is to phrase the [HARD] rejection and SC1 at the granularity that holds under *both* shapes (the source rejects a wrong channel-model; field-level type correctness is guaranteed either in the source (B) or at the bridge (A)), so the owner's choice stays real. **Confirm that's the intent.**

**L3-2 · Direct claim (a Shape-B consequence the reserved section omits — Shape B interacts with the no-generated-import rule):** Shape B "validates raw mappings into the declared entry channel model." The declared entry channel model is a *generated* class (`ToyPlantParams`), obtained dynamically from the loaded package. So under Shape B the entry source must reference a generated model shape at runtime to validate into it — which brushes against the [INHERITED] "runtime types never import generated classes" rule (it's a dynamic dependency, not a static import, so arguably the letter is met, but the spirit is strained). Under Shape A the caller builds the model and the source never touches a generated class. **The reserved section lists Shape B's consequences but omits this one; design needs it to weigh the choice honestly.** Add it as a Shape B consequence.

**L3-3 · Nice-to-have (provisional package-load before Item 9 lands is unstated):** The [HARD] "sealed package loads under its declared package name" correctly defers the canonical protocol to Item 9 and forbids hard-coding a directory name. But Item 9 hasn't landed, and Item 10 must load Item 0's package *now* to run any test — via the symlink-under-declared-name approach the spike uses (`real_evaluator.py:73`). The spec should note that Item 10 uses that provisional loader pending Item 9, so an implementer doesn't read "Item 9 owns it" as "Item 10 can't load anything yet."

### Lens 4 — Hygiene

**L4-1 · (nothing material).** Grades are cited, sources are traceable, Non-Goals are decision-records not prohibitions, and the reserved gate is marked correctly. No hygiene finding rises to the bar.

### Lens 5 — Reader Comprehension

**L5-1 · Rewrite request (the failure-taxonomy prose is the one place a tired reader can't tell what's being claimed):** The normalized-failure section runs "only missing inputs, schema failures, thrown predicate code, or a missing aggregator field are failures. A module exception and a schema/validation failure are both failures but distinguishable by phase/cause" as dense block text that mixes concept-level buckets with teax-level phases. A reader can't tell, on one pass, which failures are pre-execution vs in-execution, or what "phase" concretely ranges over. This is the same defect as L2-1, seen from the reader's side: once the phase set is enumerated (L2-1), rewrite this passage to lead with the concrete phase list and place each failure under exactly one, rather than listing failures and asserting they're "distinguishable."

---

## Engagement Summary

**Overall take:** The spec points at the right work and gets most of the Item 0 dispositions right, but three success criteria (headline projection, the three-way failure split, backend parity) rest on things the spec left ambiguous or unpinned, and design would be misled by taking its phase/parity/isolation language literally. This is a solid spec that needs targeted edits before it's a safe contract — not a rework.

**Here's what I need you to weigh in on:**

1. **[L1-1, L1-2]** The headline-normalization tension. Is the normalized headline a *projected field* of `ModelEvidence` (Item 10's job, needs a canonical target now) or does it stay inside the *opaque report* (Item 11 reads it later)? These can't both be true as written, and the answer decides whether SC2 is closable in Item 10 before Item 9 lands.
2. **[L2-1]** The failure taxonomy doesn't map to teax's real phases. In teax, a module exception and an in-`run()` schema failure are the *same* phase (both raised from `module.run()`); the concept itself buckets them together as "execution failures." "Distinguishable by phase" is only true if "schema failure" means the *pre-execution entry rejection*. The spec needs to enumerate teax's actual phases and say which "schema failure" SC3 means.
3. **[L2-2]** The parity equivalence class is undefined, and the obvious parity test spuriously fails on indeterminate cases (NaN ≠ NaN across a JSON-round-tripped backend vs an in-memory one). Pin which fields are compared/excluded and how non-finite values compare.
4. **[L3-1]** Reserved-gate hygiene: "the entry source rejects wrong-type inputs" is written at Shape B's granularity and quietly disadvantages Shape A (where field-type rejection is the Item 11 bridge's job). Rephrase so the kept test SC1 holds identically under both shapes, keeping the owner's choice real.
5. **[L2-3]** `runtime-types-never-import-generated-classes` is stated as a property, not a test. Make it an explicit importability/isolation check, or confirm you want it left to design — it's the only guard on the concept's central no-generated-dependency bet.
6. **[L3-2]** Shape B has an unlisted consequence: it makes the entry source depend on the generated channel model at runtime, brushing the no-generated-import rule. Add it so the reserved choice is weighed honestly.

---

## Resolutions

*(To be filled in as the owner engages, keyed by finding ID. The spec agent reads this section to incorporate the review; the reviewer does not edit the spec.)*

---

## Verdict

**Approved-with-must-fixes.** (Command-vocabulary equivalent: **Revise**.) The work item is right and the dispositions are sound; the spec is not safe as a design contract until the must-fixes land.

**Must-fix (each with why):**

- **L1-1 / L1-2 — headline normalization vs opaque report + the Item 9 pin.** *Why:* two requirements can't both be literally true, and SC2's closability in Item 10 depends on resolving it; leaving it silent violates capture-fidelity Law 4 (surface the premise conflict).
- **L2-1 — failure taxonomy mapped to teax's real phases.** *Why:* SC3's "distinguishable by phase" is false for module-exception vs in-`run()`-schema-failure (same phase in teax); design would build a phase distinction the runtime doesn't provide, and the kept test would be ambiguous.
- **L2-2 — parity equivalence class + non-finite comparison.** *Why:* without it the kept parity test is under-specified and the naive implementation fails on exactly the indeterminate case the architecture exists to preserve.
- **L3-1 — reserved-gate wrong-type granularity.** *Why:* the current wording leans Shape B and makes the owner's reserved choice partly fake; SC1's kept-test meaning must not shift with the choice.

**Nice-to-haves:**

- **L2-3** — make the no-generated-import rule an explicit isolation test (strongly recommended, but framed as a question since it may be a deliberate design deferral).
- **L1-3** — reclassify the venv-provisioning line from Known Requirement to implementation prerequisite.
- **L3-2** — add Shape B's runtime-generated-dependency consequence to the reserved section.
- **L3-3** — note the provisional package loader Item 10 uses pending Item 9.
- **L5-1** — rewrite the failure-taxonomy prose around the enumerated phase list (follows from L2-1).

**Next Steps:** Once resolutions are recorded here, re-run `/_my_spec` (or return to the spec-agent session) and point it at this review to incorporate. The reviewer does not edit the spec. Design must still resolve the reserved `MappingEntrySource` shape with the owner — the must-fixes above keep that choice genuinely open.
