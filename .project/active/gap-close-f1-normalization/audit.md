# Audit: GAP-CLOSE F1 TEAx Normalization

**Verdict:** Certify
**Audited:** 2026-07-18
**Branch:** constraint-exec-epic
**Commit:** 927a9e1

---

## Summary

The implementation satisfies the reviewed Revision 3 contract. The executor records the exact
normal-module invocation key without replacing the raised exception, and both evaluator backends
use one normalizer to produce identical terminal failure records with the original arithmetic
exception as the direct cause. Independent focused, evaluation, framework, and full-repository
test runs passed, and a fresh locked regeneration was byte-identical to the committed sealed
fixture.

## Findings

### Plan completion

All five phases are verified complete.

- Phase 1: the context marker is reset at run entry and assigned only in the catch around normal
  module dispatch; the catch uses a bare re-raise
  (`packages/teax-simkit/simkit/core/pipeline_executor.py:118-146`). The focused probe verifies
  exception identity, traceback retention, exact key, same-context reset, and separate-context
  isolation (`packages/teax-simkit/simkit/tests/core/test_pipeline_executor_failure_context.py:91`).
- Phase 2: one helper constructs and raises the complete normalized record, and both evaluators
  call it (`packages/teax-simkit/simkit/evaluation/evaluator.py:56-66,125-139,193-210`). Real
  EntryPoint, ExitPoint, and router failures remain unlabeled
  (`packages/teax-simkit/simkit/tests/evaluation/test_failure_normalization.py:114-166`).
- Phase 3: the fixture producer enforces the pinned source, lock, interpreter, tool, dependency,
  and clean-worktree preconditions, then uses production graph/render/seal APIs
  (`packages/teax-simkit/simkit/tests/evaluation/fixtures/f1_arithmetic/generate_fixture.py:48-123,166-295`).
  The kept fixture test verifies package name, catalog order, YAML order, actual TEAx topological
  order, executable fingerprint, seal, and exact file coverage
  (`packages/teax-simkit/simkit/tests/evaluation/test_f1_arithmetic_fixture.py:29-79`).
- Phase 4: all four arithmetic shapes run through both public evaluator routes with complete equal
  failure records, exact native causes and traceback paths, three changing failed keys, absent
  candidate output trees, and precisely bounded scratch changes
  (`packages/teax-simkit/simkit/tests/evaluation/test_f1_arithmetic_normalization.py:31-179`).
  Direct later-failure runs assert actual topological order, earlier real evaluation channels, and
  absence of the failed and aggregate channels (`test_f1_arithmetic_normalization.py:182-215`).
- Phase 5: safe satisfied, violated, and already-produced non-finite inputs return equivalent
  evidence through both backends (`test_f1_arithmetic_normalization.py:218-231`). Existing ToyPlant
  finite and NaN parity tests remain unchanged and green.

No unfinished production implementation, TODO, broad fallback, compatibility shim, or
`NotImplementedError` exists in the scoped runtime changes. The sealed package's generated
`IMPLEMENTATION_BACKLOG.md` and zero-calculation self-test are deterministic generator artifacts,
are covered by the package seal, and contain no runtime implementation stub.

### Spec conformance

- Success criterion 1: verified. Prepared and file-backed failures have equal immutable records
  with `MODULE_EXECUTION`, the exact failed generated module key, exact rendered cause, terminal
  retry, and no partial artifacts (`evaluator.py:56-66`; `test_f1_arithmetic_normalization.py:138-159`).
- Success criterion 2: verified. Neither API exposes the arithmetic exception at top level;
  explicit chaining retains the original class, message, object, and predicate/module traceback
  (`evaluator.py:60-66`; `test_f1_arithmetic_normalization.py:160-169`; core transport probe above).
- Success criterion 3: verified. Failure cannot reach projection or return `ModelEvidence`; the
  later-failure probes show earlier constraint channels remain internal, no aggregate channel is
  produced, and the file-backed candidate output root remains exactly absent
  (`evaluator.py:125-139,193-210`; `test_f1_arithmetic_normalization.py:171-215`).
- Success criterion 4: verified. Division by zero, zero to a negative power, exponent overflow,
  and division below a nested Boolean `and` are covered. The expected failed keys span
  `f1_division_check`, `f2_power_check`, and `f3_nested_check`
  (`test_f1_arithmetic_normalization.py:31-56,138-169`).
- Success criterion 5: verified. Finite satisfied/violated arithmetic remains evidence, and a
  produced NaN reaches comparison as indeterminate evidence rather than failure
  (`test_f1_arithmetic_normalization.py:58-86,218-231`). The existing generated-package NaN-output
  and NaN-budget parity cases also pass.
- Success criterion 6: verified. Successful prepared/file-backed parity remains green for both the
  existing fixture and the new safe/non-finite cases; exceptional arithmetic has equal normalized
  semantics across both backends.

All tagged requirements are met. The change adds no arithmetic guards or exception-to-value
conversion, does not change admitted expressions, verdict vocabulary, public failure taxonomy,
retry policy, projection, or persistence timing, and does not modify sysml-codegen. The exact
module key is transported from the invocation that raised rather than reconstructed from a
constraint ID or output channel (`pipeline_executor.py:128-146`). All non-goals are respected.

### Design conformance

Implementation follows Revision 3 decisions D1-D6 and invariants I1-I8. The context seam is
policy-free, normalization remains in the evaluation layer, the diagnostic is reset per run,
non-module boundaries retain no stale key, and persistence remains after successful traversal
(`pipeline_executor.py:118-168`). The fixture is additive and truthfully recorded as
production-equivalent. No undocumented architecture or validation deviation was found.

Fresh regeneration used the retained locked CPython 3.12.11 environment after recreating clean
detached worktrees at sysml-codegen `512786c7...` and agentic-mbse `4ed2a072...`. `diff -qr` found
no difference between the fresh output and committed `package_live/`; the producer,
environment, and executable fingerprints matched `GENERATION.md`. Both source worktrees remained
clean and were removed after verification.

### Code integrity

No issues found. The production change is one narrow context field and catch plus one shared
normalizer. It introduces no implicit modes, parameter sprawl, policy-bearing utility fallback,
broad swallowed exception, optional-data escape hatch, deep nesting, copy-paste sibling logic, or
backwards-compatibility shim. The generated fixture contains no `__pycache__`, `.pyc`, or `.pyo`
artifact, and `git diff --check` passes.

---

## Certification

- Revalidated all checked plan phases and all six checked spec success criteria; no checkbox state
  needed correction.
- Independent focused run: 19 tests passed.
- Independent evaluation suite: 43 tests passed.
- Independent teax-simkit framework suite: 277 tests passed.
- Independent full repository suite: 346 tests passed.
- Reverified exact package-contract coverage and successful strict loader seal verification.
- Reproduced the sealed output from the locked producer environment and confirmed byte-for-byte
  equality with the committed package.
- Confirmed scoped status/diff hygiene and absence of transient bytecode in the sealed fixture.

**Not checked:** Concurrent reuse of one execution context, concurrent calls on one file-backed
evaluator, live licensed SysIDE extraction, output-write phase redesign, sysml-codegen changes, and
other GAP-CLOSE items are outside this item's stated support boundary and non-goals. No in-scope
claim remains unchecked.
