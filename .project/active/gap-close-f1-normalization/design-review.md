# Design Review: GAP-CLOSE F1 TEAx Normalization

**Design:** `.project/active/gap-close-f1-normalization/design.md`
**Spec:** `.project/active/gap-close-f1-normalization/spec.md`
**Review File:** `.project/active/gap-close-f1-normalization/design-review.md`
**Date:** 2026-07-18

## Review History

- **Revision 1 independent review:** **Revise.** Preserved below in full.
- **Revision 2 independent rerun:** **Revise.** All boundary, concurrency, ordering,
  registry-isolation, seal-layout, and filesystem-manifest findings are resolved. The fixture
  workflow still depends on an ambient, unlocked virtualenv, so the prior reproducibility major is
  only partially resolved.

---

## Fundamental Assessment

**Concerns, but sound.** The overall mechanism is the narrowest practical one under the direct-cause
contract. The executor is the only layer that has the authoritative pipeline module key, while the
evaluator must remain the layer that chooses `EvaluationFailure`. A failure-only field on the
already per-run `PipelineExecutionContext`, reset at `run()` entry and populated only by the catch
around `_execute_module`, transports that key without wrapping or mutating the original exception
(`design.md:78-91,110-130`; `pipeline_executor.py:107-162,181-231`). A wrapper exception would add a
transport object to the causal path, and executor-instance state would be unsafe because both
evaluators reuse an executor. The proposed context field earns its existence.

The catch boundary is also correctly placed for the existing definition of `module_execution`.
`_execute_module` includes module construction, input resolution, `module.run()`, result
decomposition, channel writes, and version recording. The completed evaluator contract already
classifies those operations as one module-execution phase. EntryPoint handling, ExitPoint
collection, and router persistence remain outside the proposed identity catch
(`design.md:43-62,160-174,215-229`; `pipeline_executor.py:122-155`). Those failures can therefore
retain `module_or_channel=None` rather than inheriting the last successful module. The design is
transparent that the file-backed evaluator's broader run catch still assigns its pre-existing
phase to persistence errors; correcting that taxonomy is outside this revised spec
(`design.md:160-162,206-213`; `spec.md:129-139`).

The design should be revised before planning because its validation strategy does not yet guard
all of those boundaries, its concurrency claim is broader than the current evaluator behavior,
and the sealed multi-constraint fixture is not reproducible or isolated precisely enough.

---

## Dimensional Review

### 1. Spec Compliance
**Assessment:** Concerns

The public record, exact failed key, cause rendering, terminal/no-partial defaults, direct explicit
cause, no-return/no-persist outcome, four arithmetic shapes, multiple failing keys, and successful
finite/non-finite preservation all have corresponding design elements
(`design.md:164-181,260-315`; `spec.md:27-55`). The normalizer raising
`EvaluationFailed` directly `from` the caught original, combined with the executor's bare re-raise,
preserves direct exception identity and the original causal traceback without a transport wrapper
(`design.md:80-90,166-170,217-226`).

Two compliance risks remain:

- I4 requires EntryPoint, ExitPoint, and persistence failures not to receive a module key, but the
  validation plan contains no negative-path test for any of those three boundaries
  (`design.md:173-174,275-315`). Structural inspection says the proposed catch is correct; a later
  widening of the catch or an active-key implementation would silently violate I4. Add focused
  failures on both sides of `_execute_module`, especially EntryPoint loading and router
  persistence, and assert `module_or_channel is None`. Add an ExitPoint-side probe if it can be
  induced without creating a test-only production branch.
- The later-module criterion depends on actual execution order, but the three predicates are
  described as independently controllable rather than dependency-ordered. The current graph uses
  `TopologicalSorter` over generated dependencies (`pipeline_graph.py:29-84`). Do not treat YAML
  declaration order as the contract. The kept test must assert the generated graph's actual order
  and prove an earlier real constraint result exists before the selected later failure.

Capture fidelity is otherwise good. The design carries the owner-originated value-versus-raise and
no-partial-report policies without hardening them into arithmetic guards. It preserves the exact
inherited public record. The multiple-key and no-persist-after-earlier-completion requirements are
agent-grade (`[INFERRED]`) in the revised spec, and the design uses them as adversarial tests rather
than presenting them as owner-settled policy. The spec contains no owner-marked `[EXAMPLE]` or
`[REFERENT]` payload for the design to preserve.

### 2. Pattern Consistency
**Assessment:** Pass

The executor already receives mutable per-run state through `PipelineExecutionContext`, and both
evaluators already create a context for every call (`pipeline_executor.py:33-54`;
`evaluator.py:112-123,185-199`). Adding one optional diagnostic field follows that pattern. A
private normalizer in `evaluation/evaluator.py` is practical: the two duplicated catches and all
required failure types already live there, so no new module or public abstraction is needed
(`design.md:122-130,183-204`).

The proposed change also preserves the prepared specialization: `_MappingExecutor` continues to
replace only EntryPoint loading, while the base serial loop owns identity capture
(`evaluator.py:56-68`). This avoids parallel executor subclasses or evaluator-specific private-hook
overrides.

### 3. Abstraction Quality
**Assessment:** Concerns

The mechanism itself is appropriately small: one optional string of run state, one narrow catch,
and one evaluator helper. A failure-only marker is safer than an active-module marker because
successful modules leave no label for ExitPoint or persistence failures to inherit
(`design.md:110-130`). It is also narrower than a public contextual exception hierarchy.

B3 overstates what the mechanism establishes. Fresh contexts make concurrent prepared calls
independent with respect to this marker, but `FileBackedEvaluator` writes every call to the same
scratch entry path before starting the run (`evaluator.py:182-190`). Concurrent calls on one
file-backed evaluator can therefore race independently of the new field. Reusing the same mutable
context concurrently is already unsupported because channels and module versions are shared
(`pipeline_executor.py:40-43`). Revise B3 into an explicit support boundary:

- sequential `run()` reuse of one context resets the diagnostic field;
- separate contexts do not share the field;
- concurrent reuse of one context is unsupported;
- this item does not make `FileBackedEvaluator.evaluate()` thread-safe.

The focused core test should cover sequential reuse directly. Repeating calls through one
`PreparedEvaluator` does not test reset or stale state because every call constructs a new context
(`design.md:238-239`; `evaluator.py:112-116`). It is useful for multi-key identity, but it cannot be
cited as the stale-marker regression.

### 4. Duplication Avoidance
**Assessment:** Pass

One helper that both evaluator catches call is the correct consolidation point. Keeping the helper
responsible for both record construction and `raise ... from original` prevents either route from
drifting on fields or suppressing explicit chaining (`design.md:122-126,225-226`). Moving policy
into the executor or keeping two local helpers would recreate the split this item is fixing.

### 5. Data Structure Clarity
**Assessment:** Pass

An optional exact pipeline key is sufficient data. The design explicitly forbids reconstruction
from constraint IDs, module types, channels, constants, or prior state
(`design.md:166-174,221-224`). No broader error-context object is justified. Leaving the exact
private field and helper names to the plan does not weaken the type or lifetime contract.

### 6. Route Safety
**Assessment:** Concerns

There are no HTTP routes. For the relevant execution routes, prepared and file-backed evaluation
share the same serial-loop capture and the same normalizer, which is the safest way to keep their
public records equal. The identity catch excludes EntryPoint, ExitPoint, and persistence work.

The missing boundary-negative tests are the concern. The design should demonstrate that only an
exception escaping `_execute_module(module_key, ...)` gains that key. In particular, a router
exception after a final successful module must still have an empty identity. This review does not
ask the item to repair the pre-existing `OUTPUT_WRITE` phase mismatch; the design correctly records
that as deferred. It does ask the tests to prove this change does not make that existing behavior
more misleading by attaching a module key.

### 7. Bets & Decisions Integrity
**Assessment:** Concerns

B1 and B2 are genuine, evidence-backed bets with clear failure consequences. Upstream tests pin
the original arithmetic raises through the generated wrapper, and current executor/router ordering
supports no persistence before successful traversal (`design.md:93-101`; upstream
`test_predicate_compiler.py:116-167`, `test_constraint_execution.py:444-498`). D1-D5 identify real
alternatives and explain why the chosen mechanisms are smaller.

B3 should not remain a bet in its current form. Part of it is directly observed fresh-context
behavior, part is an unsupported concurrency implication, and part is a support-policy decision.
State that policy directly as recommended under Abstraction Quality.

The hidden bet is fixture ordering and reproducibility. The design says to build a
"production-generated" sealed package with three ordered constraints, but it defers the generator
source and regeneration command and does not name a unique declared package name
(`design.md:193-200,243-245,260-266,316-320`). The current upstream evidence generates only a
single-constraint arithmetic package. Before implementation, identify a real source model or
snapshot/graph producer that emits all three independently controlled constraints in the required
order, the exact generator revision and command, and the resulting unique package name. Otherwise
the fixture can become a hand-assembled approximation that tests TEAx against behavior the
production generator did not produce.

### 8. Reader Comprehension
**Assessment:** Pass

The design gives the reader the model before the details: capture authoritative identity in the
executor, preserve the original exception, normalize once at the evaluator boundary. The diagram,
invariants, and generated-case matrix make the intended flow easy to verify. The two misleading
sentences are substantive rather than stylistic: B3 implies broader concurrency safety, and the
stale-key mitigation credits repeated prepared calls for a reset they cannot exercise. The
recommended revisions remove those ambiguities.

---

## Issues by Severity

### Critical

- None.

### Major

- **The validation plan does not prove the identity catch excludes EntryPoint, ExitPoint, and
  persistence failures.** Add boundary-negative tests asserting `module_or_channel is None` for
  non-module failures, without expanding this item into phase-taxonomy repair. — Spec Compliance,
  Route Safety
- **B3 conflates fresh contexts, sequential context reuse, and concurrency.** Define the support
  boundary explicitly and keep file-backed thread safety out of scope; its shared scratch entry
  path already races. — Abstraction Quality, Bets & Decisions Integrity
- **The sealed arithmetic fixture is not yet reproducibly specified.** Record the multi-constraint
  generator source, exact revision/command, actual generated order, and a unique declared package
  name before planning. — Spec Compliance, Bets & Decisions Integrity
- **The proposed completion spy can contaminate shared registries and test altered behavior.** The
  current evaluation fixtures are session-scoped, and the design proposes replacing private
  registry factories in both evaluators (`design.md:294-299`; existing
  `tests/evaluation/conftest.py:29-46`). Prefer a fresh direct executor/context run against the real
  sealed package, catch the later failure, and inspect the earlier constraint channel in that
  context. Then test the two evaluator boundaries separately for no returned evidence and no
  persisted output. If a spy is unavoidable, use fresh evaluator instances/private registry
  copies per test and restore exact descriptors in `finally`; never mutate package files or a
  session-shared registry. — Pattern Consistency, Route Safety

### Minor

- **Repeated prepared calls do not test marker reset.** Keep them for multiple-key and fresh-context
  coverage, but make the same-context core test the only stale-marker proof. — Reader Comprehension
- **Keep case JSON and regeneration notes outside the sealed package root unless they are generated
  and included before sealing.** The loader rejects unhashed extras, and the file-backed evaluator
  already copies external case bytes into its scratch tree. — Pattern Consistency
- **State the no-persistence assertion as an exact before/after output-tree manifest.** Distinguish
  the expected scratch `inputs/toy_plant_params.json` write from forbidden candidate output run
  directories/files. — Data Structure Clarity

---

## Recommendations

1. Keep the `PipelineExecutionContext` failure-only marker and bare re-raise. Specify sequential
   reset and unsupported concurrency boundaries precisely.
2. Add negative-path tests around the identity catch so entry, exit, and router failures retain an
   empty `module_or_channel`.
3. Turn the sealed arithmetic fixture into a reproducible artifact contract: unique package name,
   committed generator input, revision, command, seal verification, and asserted actual graph
   order.
4. Prove earlier completion with a fresh real executor/context when possible. Avoid mutation of
   session-scoped evaluator registries.
5. Keep the shared normalizer private in `evaluator.py` and responsible for the explicit chained
   raise, then compare complete `EvaluationFailure` values across both backends.

---

## Resolutions

No resolutions recorded in this independent orchestration-stage review.

---

**Overall:** Revise
**Next Steps:** Return this review to the design agent. Once the findings are resolved, re-run
`my-design` (or resume the design-agent session) and point it at this review to incorporate. The
reviewer does not edit `design.md`.

---

# Revision 2 Independent Rerun

**Revision reviewed:** `design.md`, status “Ready for Design Review (Revision 2)”
**Rerun date:** 2026-07-18
**Prior verdict preserved above:** Revise

## Fundamental Assessment

**Sound.** Revision 2 keeps the narrow context-marker architecture from the first design. One
failure-only string on the existing per-run execution context is still the smallest mechanism that
can transport the executor's authoritative module key while leaving the original exception object
and traceback unchanged. One private evaluator normalizer remains the correct policy boundary.
No new production abstraction, phase, public type, or arithmetic behavior was introduced
(`design.md:94-107,127-147,193-241`).

The revised validation design is materially stronger. It exercises the real EntryPoint, ExitPoint,
module, and router boundaries; uses fresh evaluator/executor/context state for ordering evidence;
avoids shared registry mutation; and separates scratch-input changes from forbidden candidate
outputs (`design.md:302-390`). Those additions are test work around the existing seams, not an
expansion into phase-taxonomy repair, evaluator thread safety, or partial-evidence recovery.

One prior major remains only partially resolved. The fixture is now truthfully described as
production-equivalent, its source APIs and revisions are pinned, and its sealed layout is precise.
However, the reproduction command executes with `../agentic-mbse/.venv/bin/python`
(`design.md:441-451`). That virtualenv's Python and dependency versions are ambient. The pinned
sysml-codegen revision declares open-ended Jinja, Pydantic, and PyYAML requirements and carries a
lockfile, but Appendix A neither uses that lock nor records the environment versions. Clean source
worktrees alone therefore do not make regeneration reproducible.

## Dimensional Review

### 1. Spec Compliance
**Assessment:** Pass

Every success criterion remains addressable. The design fixes the exact public record and direct
cause, covers all four arithmetic raises through both evaluator routes, forces at least three
distinct failed keys across the matrix, preserves finite and already-produced non-finite verdicts,
and proves no returned report/evidence or persisted candidate output
(`design.md:219-241,304-390`; `spec.md:27-55`).

The earlier-completion proof now relies on actual generated and TEAx topological order, then inspects
channels on the same fresh context after catching the native later failure. It does not infer order
from YAML declaration and does not use a completion spy (`design.md:306-310,333-339`). This matches
the serial executor, which dispatches `graph.topological_order`, stops on the raised normal-module
call, collects ExitPoint values only later, and persists only after that
(`pipeline_executor.py:125-155`).

Capture fidelity remains intact. Owner-originated arithmetic and no-partial-report policies retain
their force. The agent-grade multiple-key and no-persist-after-earlier-completion requirements remain
adversarial validation, not owner-settled policy. The spec has no owner-marked example or referent
payload to preserve.

### 2. Pattern Consistency
**Assessment:** Pass

The production change still follows existing per-run context and evaluator patterns. Revision 2
removes the proposed registry-factory replacement entirely. The white-box completion proof creates a
fresh evaluator, registry, executor context, and scratch tree, then invokes the real serial executor
without altering descriptors or package files (`design.md:333-339`). This avoids the session-scoped
registry contamination identified in the first review.

### 3. Abstraction Quality
**Assessment:** Pass

The support language is now exact. Sequential same-context reuse is supported and reset at run
entry; separate contexts isolate all mutable run state; concurrent same-context reuse is unsupported;
and file-backed evaluator thread safety remains out of scope because its scratch entry path is
shared (`design.md:118-123,188-199,385-389`; `evaluator.py:182-188`). Repeated prepared calls are
correctly limited to separate-context evidence and are no longer presented as reset proof.

### 4. Duplication Avoidance
**Assessment:** Pass

One private normalizer still constructs the public failure and performs the explicit chained raise
for both evaluators. One base-executor catch captures identity. The expanded tests do not introduce
parallel production paths (`design.md:127-147,226-241`).

### 5. Data Structure Clarity
**Assessment:** Pass

The optional exact module key remains sufficient. The filesystem contract now defines a complete
typed manifest for absent roots, directories, files plus byte hashes, and symlinks plus targets.
It separately defines the one permitted scratch mutation and requires the candidate output root to
remain exactly absent (`design.md:362-374`). This resolves the prior ambiguity between evaluator
scratch input and persisted candidate output.

### 6. Route Safety
**Assessment:** Pass

All requested identity-negative boundaries are feasible against current code and stay within phase
scope:

- malformed JSON reaches the real file EntryPoint loader before any normal module;
- a context sentinel raised during real ExitPoint channel collection sits after all normal module
  calls and outside the identity catch; and
- an existing regular file used as the output base fails in the real router's run-directory setup,
  after traversal (`design.md:341-360`; `pipeline_executor.py:125-155`;
  `output_router.py:78-80,239-246`).

Each test asserts only that `module_or_channel` stays empty and that the existing phase/cause remains
unchanged. The design explicitly declines to rename the router failure phase or add a production
test branch. The ExitPoint test's test-only context is a normal substitutable execution context,
not a production hook.

### 7. Bets & Decisions Integrity
**Assessment:** Concerns

B1 and B2 remain genuine, evidence-backed bets. B3 is now explicitly a support boundary rather than
a concurrency claim. D5 is truthful about fixture provenance: no pinned upstream live model or
snapshot produces the required independently controlled shape, so the fixture is called
production-equivalent and uses a synthetic graph only at the source-fact seam
(`design.md:78-92,109-123,148-164,409-437`).

The pinned APIs support the proposed producer. At the recorded revisions, agentic-mbse exposes the
expression node algebra and canonical serializer; sysml-codegen accepts ordered
`ConcreteConstraint` records, extends the graph through `extend_graph_with_constraints`, assembles
the real catalog, renders modules/YAML/registry/entries through the CLI generation functions, and
seals last through `_seal_package`. The generated graph preserves the supplied constraint order and
appends the report aggregator. TEAx then derives its actual order from graph dependencies rather
than trusting declaration order.

The unresolved concern is the ambient generation environment. D6 says regeneration does not rely
on the developer's dirty environment, but the command selects the existing agentic-mbse virtualenv
without pinning or recording its interpreter and dependency set (`design.md:158-164,441-451`).
Because the generator imports Jinja, Pydantic, and PyYAML under open-ended constraints, the same two
Git SHAs and producer hash do not fully identify the code that renders and serializes the fixture.

### 8. Reader Comprehension
**Assessment:** Pass

Revision 2 clearly distinguishes source provenance, generated-package production equivalence,
execution order, scratch writes, candidate outputs, same-context reset, separate-context isolation,
and unsupported concurrency. The mental model remains easy to follow. No wording hides a scope
change or contradiction.

## Prior Finding Resolution Audit

### Prior Major Findings

- **Boundary-negative coverage:** **Resolved.** EntryPoint, ExitPoint, and router tests use real
  boundaries and preserve the current phases (`design.md:341-360`).
- **Concurrency/support boundary:** **Resolved.** Same-context sequential reuse, separate contexts,
  unsupported concurrent reuse, and file-backed thread safety are stated separately
  (`design.md:118-123,188-199`).
- **Fixture provenance and reproducibility:** **Partially resolved.** Provenance terminology,
  producer/source pins, package identity, generation steps, order assertions, seal placement, and
  external-case layout are resolved. The executable environment remains unlocked
  (`design.md:409-463`).
- **Completion spy/shared-registry contamination:** **Resolved.** The proof uses a fresh real
  evaluator/executor/context and no registry mutation (`design.md:333-339`).

### Prior Minor Findings

- **Prepared calls used as reset proof:** **Resolved.** Same-context reset has its own core test;
  prepared calls prove only separate-context isolation (`design.md:329-331,385-389`).
- **Cases and regeneration notes inside the seal:** **Resolved.** Both remain outside
  `package_live/`, and the production seal is created last (`design.md:419-437,454-463`).
- **Output-tree assertion ambiguity:** **Resolved.** Candidate output and scratch manifests have
  distinct exact contracts (`design.md:362-374`).

## Issues by Severity

### Critical

- None.

### Major

- **The fixture reproduction command still uses an ambient, unlocked virtualenv.** Pin the
  generation environment as well as the two source revisions. Prefer a clean environment created
  from the pinned sysml-codegen lockfile with the pinned agentic-mbse worktree substituted, or record
  and verify the exact Python and generation-dependency versions/hashes before generation. Update
  `GENERATION.md` to carry that environment identity. This closes the remaining part of the prior
  fixture-provenance major without changing fixture scope. — Bets & Decisions Integrity

### Minor

- None.

## Recommendations

1. Keep all Revision 2 architecture and validation changes unchanged.
2. Replace the ambient-venv regeneration command with a locked clean-environment command, and make
   the producer reject an environment that does not match that lock or recorded identity.
3. Preserve both source SHAs, producer hash, graph/YAML/TEAx order assertions, seal verification,
   and executable fingerprint in `GENERATION.md`.

## Resolutions

- **Revision 1 boundary-negative major:** Resolved by Revision 2's real EntryPoint, ExitPoint, and
  router boundary tests. No phase-taxonomy work was added.
- **Revision 1 concurrency major:** Resolved by Revision 2's explicit support boundary and focused
  same-context reset test.
- **Revision 1 fixture-provenance major:** Partially resolved by the production-equivalent producer,
  pinned source revisions, external case layout, order checks, and final production seal. The
  generation environment remains to be pinned.
- **Revision 1 shared-registry major:** Resolved by the fresh direct executor/context proof with no
  registry mutation.
- **All three Revision 1 minor findings:** Resolved as recorded in the audit above.

**Overall:** Revise
**Next Steps:** Return the remaining generation-environment finding to the design agent. After the
reproduction command is locked, rerun `my-design-review`; the implementation architecture and test
scope need no further revision.
