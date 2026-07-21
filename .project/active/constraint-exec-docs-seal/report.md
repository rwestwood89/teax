# S-TEAX report — CONSTRAINT-EXEC Item 14 Appendix B (W3c / W5b / W5c)

**Status:** Complete. Commit `245f687` on `constraint-exec-epic`.

## W5b — teax loader seal-verification wiring (precondition of S-FUSION's W4)

`packages/teax-simkit/simkit/evaluation/package_load.py`'s `ProvisionalPackageLoader`
no longer hashes files itself. It now delegates to the canonical protocol from
sysml-codegen's Item 9 — `contracts.verify.verify_package(package_dir, package_name,
runtime_version, strict)` — imported from the generated package's own bundled
`contracts/verify.py` (loaded by file path via `importlib.util.spec_from_file_location`,
registered in `sys.modules` so its dataclasses resolve, never `import sysml_codegen`).
This is the load-by-declared-name + runtime marker + strict wiring the design called for:
`package_name` is the caller-supplied declared name, the runtime marker is a new
`RUNTIME_CONTRACT_VERSION = "1.0.0"` constant owned by teax (mirrors sysml-codegen's own
pinned constant at seal time), and `strict` defaults to `True` on the loader.

A non-ok `VerificationResult` raises `SealVerificationError` naming every diagnostic
(`TAMPER`, `MISSING`, `EXTRA`, `NAME_MISMATCH`, `RUNTIME_MISMATCH`) — confirmed by
`packages/teax-simkit/simkit/tests/evaluation/test_package_load.py`, three new tests:
a clean sealed load, a tampered artifact (`TAMPER`), and an unhashed extra file (`EXTRA`).

**Fixture change required to exercise this for real:** the shared sealed-package fixture
(`simkit/tests/evaluation/fixtures/sealed_package/package_live/`) predated Item 9's real
`PackageContract` schema — its `contracts/package_contract.json` had only
`artifact_hashes`/`executable_fingerprint`/`generator`, missing `package_name`,
`coverage_policy`, `generator_version`, `runtime_contract_version`. Re-sealed it to the
real schema (hand-replicated `seal_package`'s hashing algorithm in stdlib, since
importing `sysml_codegen` directly pulls in `agentic_mbse` and isn't installed here) and
added the fixture's own `contracts/verify.py`, copied verbatim from sysml-codegen's
`src/sysml_codegen/contracts/verify.py` (INV-8: every generated package carries this
file). This is exactly the "sealed IFE package loads through teax" shape S-FUSION's W4
will exercise for real.

**Symlink-under-declared-name import mechanism is unchanged** — only seal verification
was rewired; that part of the loader was never provisional in the sense Item 9 targeted.

**Validation:** `packages/teax-simkit` suite green (`uv run pytest` equivalent —
`.venv/bin/python -m pytest`) except the 4 pre-existing `test_no_battery_deps` failures
(environment-only, unrelated: `subprocess` can't find `/home/reid/teax`, not
`/home/reid/1cfe/teax`); `ruff check` clean on every file this session touched.

## W3c — teax evaluator + study-layer docs

No teax doc described the evaluator or study layers before this session (`CLAUDE.md` and
`AGENTS.md` had zero mentions of `simkit/evaluation/` or `simkit/study/`; there was
nothing describing the retired constraint-manifest/report behavior either — a clean
slate, not a flip). Added `docs/evaluation-and-study.md`: package seal verification and
the symlink import mechanism, the two evaluator backends (`PreparedEvaluator` /
`FileBackedEvaluator`) and their shared `project(...)`, the four-phase failure taxonomy
(`EvaluationPhase`) and why `indeterminate` is evidence rather than failure, the
`ModelEvidence` envelope, and the study layer (`StudyDefinition`, `StudyRunner`'s fixed
order and failure routing, `StudyStore`'s crash-safety contract, `StudyQuery`'s catalog
join, the `teax-study` CLI). Pointed to it from a new `CLAUDE.md` section and added the
two missing module bullets to `AGENTS.md`'s (pre-existing, stale) structure list.

## W5c — tracking-key correlation note

No occurrence of `tracking_key` existed anywhere in `packages/` — this was a documentation
gap, not a wiring gap. `docs/evaluation-and-study.md`'s "Tracking keys correlate by name,
never by identity" section records that a `constraint_id` (what `StudyQuery` joins on,
what `ModelEvidence.responses` is keyed by) is scoped to one executable fingerprint; a
`tracking_key` is a separate, optional, author-controlled name for comparing a logical
constraint's results across two different sealed packages (two fingerprints), and no code
in this layer performs that cross-fingerprint join automatically — a caller doing that
comparison has to do it by name and show the fingerprint boundary itself crossed. Matches
concept Vocabulary line 209 verbatim in substance.

## Files touched

- `packages/teax-simkit/simkit/evaluation/package_load.py` — wired to `verify_package`.
- `packages/teax-simkit/simkit/tests/evaluation/test_package_load.py` — new.
- `packages/teax-simkit/simkit/tests/evaluation/fixtures/sealed_package/package_live/contracts/package_contract.json` — re-sealed to the real schema.
- `packages/teax-simkit/simkit/tests/evaluation/fixtures/sealed_package/package_live/contracts/verify.py` — new (INV-8 copy).
- `docs/evaluation-and-study.md` — new.
- `CLAUDE.md`, `AGENTS.md` — pointers/structure updates.

## For the Phase-6 reconcile

W5b is landed and precedes S-FUSION's W4 as required. Evidence: commit `245f687`,
`test_package_load.py`'s three cases, full-suite run above.
