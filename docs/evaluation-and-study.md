# Evaluation and Study Layers

Two layers sit on top of the core pipeline framework to turn a sealed, generated
package (produced by sysml-codegen and holding a lowered constraint model) into
constraint verdicts, and then into a searched grid of those verdicts:

- **Evaluation** (`simkit/evaluation/`) loads one sealed package and runs one
  case through it, producing an immutable evidence record.
- **Study** (`simkit/study/`) drives many cases through an evaluator — proposing
  candidates, assessing their evidence, and persisting the results crash-safely.

Neither layer imports a generated model class or introspects a generated report
beyond a few duck-typed attributes (`report.headline`, `report.results`,
`constraint_result.constraint_id`, `.status`). That isolation is deliberate: this
code has to work against whatever a future generated package looks like, not just
today's fixture.

## Evaluation layer

### Loading a sealed package

`package_load.ProvisionalPackageLoader` loads a sysml-codegen-generated package
tree under its declared import name. Loading has two independent jobs:

1. **Seal verification** — delegates to the canonical protocol from
   sysml-codegen's Item 9, `contracts.verify.verify_package`. Every generated
   package carries its own copy of that stdlib-only module at
   `contracts/verify.py`; the loader imports *that* copy (by file path, not by
   package name) rather than depending on sysml-codegen being installed. A
   teax environment can therefore verify a package it loaded with nothing but
   the package itself. Verification checks the package's declared name, the
   content hash of every covered file, and (if given a `runtime_version`) the
   recorded `runtime_contract_version` — a hash mismatch, a missing file, an
   unhashed extra file, or a declared-name mismatch is always fatal; a
   runtime-version mismatch is advisory unless the loader is constructed with
   `strict=True` (the default). A failed verification raises
   `SealVerificationError` naming every diagnostic kind (`TAMPER`, `MISSING`,
   `EXTRA`, `NAME_MISMATCH`, `RUNTIME_MISMATCH`).
2. **Import mechanism** — the package's own internal imports are absolute to
   its declared name (`from wi014_s4...`), so the on-disk directory is exposed
   under that name via a symlink placed in a caller-supplied `link_root`. This
   half is unrelated to seal verification and unchanged by which verifier is wired.

### Running a case

`evaluator.PreparedEvaluator` and `evaluator.FileBackedEvaluator` both load a
package once via a `PackageLoader`, build the module graph once, and then run
individual cases against that fixed graph:

- `PreparedEvaluator` is the fast, in-memory path: entry values are supplied as
  already-typed Pydantic models, outputs are captured in memory, and every
  `evaluate()` call gets a fresh execution context (no channel bleed between
  cases).
- `FileBackedEvaluator` is the audit backend: entry values come from a JSON
  file, outputs persist to disk, and every case leaves an on-disk trail. It
  never writes into the sealed, seal-checked package tree itself — it copies
  the package's `pipelines/pipeline.yaml` into a scratch work directory it owns.

A parity test asserts both backends agree, which is what licenses using the
fast path day-to-day and falling back to the audit path only when a file trail
is wanted.

Both evaluators route a run's outcome through `failure.EvaluationPhase`, a
four-phase taxonomy (`entry_validation`, `preparation`, `module_execution`,
`output_write`). A phase failure raises `EvaluationFailed`; an `indeterminate`
constraint verdict is never one of these phases — it is evidence, not failure,
because a well-formed candidate that a model can't finitely evaluate is still a
valid result to record and search over.

### Evidence

`evidence.ModelEvidence` is the immutable output of one evaluation: `responses`
(constraint ID → `satisfied | violated | indeterminate`, plus the reserved key
`"headline"` for the aggregate verdict, which can additionally be
`not_assessed`), `outputs` (selected numeric
outputs), `provenance` (the evaluator's own identity stamp — executable
fingerprint, schema versions, input digest), and the generated `report` itself,
held opaque. `projection.project()` builds a `ModelEvidence` from a raw pipeline
result and report by reading only those few duck-typed attributes.

## Study layer

A study is a declarative search over an evaluator: `study/definition.py`'s
`StudyDefinition` binds together a candidate-proposing `strategy`
(`study/strategy.py`'s `GridStrategy` — a row-major Cartesian product over an
ordered `[name, domain]` list, never a dict, because the order is part of the
strategy's own identity — or `PreparedListStrategy`; optionally capped by
`study/bounded_strategy.py`'s `BoundedStrategy`, which folds its
`max_candidates` bound into the config fingerprint so a bounded study is a
distinct lineage from the unbounded one), a `validate_proposal` function, an
assessment `policy` (`study/policy.py`), and the compatibility
fingerprints — executable fingerprint, model-contract fingerprint,
study-definition fingerprint, schema versions, strategy identity/config — that
pin one study to one lineage. `study/compatibility.py`'s `Compatibility` is
bound once when a store is created; opening the same store later with a
different value raises `IncompatibleStore` rather than silently mixing datasets
from two different model or study definitions.

`study/runner.py`'s `StudyRunner` drives the fixed order for every candidate:
validate/canonicalize the proposal, bridge it into a typed entry model
(`study/bridge.py`), evaluate, assess, stage durably, atomically commit, advance
the strategy's feedback. Each of the evaluator's four failure phases routes
differently: `entry_validation` is a bridge defect and is raised loudly, never
recorded as a case; `preparation` is a startup fault and is re-raised (it can't
happen per-case once a `PreparedEvaluator` has already built its graph);
`module_execution` (today) or `output_write` (a future persisting backend) is
terminal and lands as an `execution_failed` case. A policy that raises
`AssessmentFailed` lands as an `assessment_failed` case instead — evidence was
produced, but this study's policy couldn't interpret it. A case that completes
both evaluation and assessment lands as `completed`, carrying the policy's
`disposition` (`reject | penalize | keep-for-boundary | feed-strategy`).

`study/store.py`'s `StudyStore` is a crash-safe SQLite store (`WAL` +
`synchronous=FULL`, asserted on every open): content-addressed staging, a
fenced lease so only one runner drives a study at a time, and GC of orphaned
staged artifacts. It survives a killed process; it does not claim power-loss
safety. `study/crash.py`'s `CrashController` is test-only fault injection at
named store seams, always a no-op in production.

`study/query.py`'s `StudyQuery` is the read-only join a `teax-study inspect`
renders: it decodes each case's evidence once (memoized by digest) and joins
per-constraint verdicts to the fixture's constraint catalog by
`constraint_id -> source_usage -> source_record`. Every result carries its own
`executable_fingerprint`, and results are never merged across fingerprints —
a study's results are scoped to the one package lineage that produced them.

### Tracking keys correlate by name, never by identity

A constraint's `constraint_id` (what `StudyQuery` joins on, and what
`ModelEvidence.responses` is keyed by) is scoped to one executable fingerprint —
it is not a stable identifier across model versions. Comparing a constraint's
results across two different sealed packages (two lineages, two fingerprints)
is a separate, optional, author-controlled concern: a `tracking_key` names a
logical constraint so its results can be correlated across versions. A name
correlates a comparison a caller wants to make — it does not equate the two
verdicts as if they were the same constraint. A named constraint whose
predicate changed between versions remains the same tracking subject, but its
evidence spans different executable fingerprints, and nothing in this layer
performs that cross-fingerprint join automatically. Any tool that wants it has
to do the correlation itself, by name, and show the fingerprint boundary it
crossed.

## Console entry point

`teax-study` (`study/cli.py`) exposes `create | run | resume | inspect` over a
declarative YAML study config (`study/config.py`). The config is the
persistent, re-readable study definition: `create` binds a fresh store to it;
`run`/`resume` rebuild the same definition and drive `StudyRunner`, relying on
the store's compatibility check to refuse a changed config rather than mixing
datasets. `inspect` opens an existing store read-only and prints one JSON line
per case via `StudyQuery`, filterable by parameter, output, constraint, state,
or disposition.
