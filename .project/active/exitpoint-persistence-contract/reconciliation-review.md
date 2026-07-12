# Design Review: Reconciling the Two Primitive-Persistence Implementations

**Status:** Implemented — Option A executed on branch `primitive-persistence-unified` (off `main`/5d6496a), 2026-07-12
**Author:** [AGENT] (analysis); reconciliation direction [OWNER]-approved (Path A)
**Date:** 2026-07-12

## Implementation record (2026-07-12)

Path A executed as an additive change on top of `main` (`5d6496a`), not a merge of
the stale branch. Delta applied:

- `config/schema.py` — `PRIMITIVE_TYPES` as the single source of truth (config
  layer, so both io and core import it without an io→core cycle).
- `pipeline_executor.py` — `_PRIMITIVE_TYPES` now aliases `schema.PRIMITIVE_TYPES`
  (entry loaders / registry / resolver unchanged otherwise).
- `output_router.py` — 4 `RootModel[...]` wrapper handlers added (kept `main`'s
  `write_json_primitive` for bare); defaults-win guard in
  `create_output_router_with_json_schemas`.
- `pipeline_validator.py` — D3 exit cross-check (`_validate_exit_output_type`),
  composed with `main`'s entry-primitive resolution fallback.
- Tests — merged July's scalar/wrapper/guardrail/D3/e2e tests with `main`'s
  primitive-writer and entry-loader tests; kept both.
- Battery `demo_linear_alt.yaml` — corrected 5 exit bindings from bare to their
  real `RootModel[...]` producers (D3 caught the same mislabel here as on `main`).
- Docs — `rootmodel-and-primitives.md` persistence+loading section (symmetric,
  documents the strict entry-loader type check); `CLAUDE.md` error 4 split + error 5.

**Verification:** full suite 231 passed, 4 pre-existing `test_no_battery_deps.py`
env failures (hard-coded `/home/reid/teax`). fusion-tea workaround-free
reproduction: 13/13 anchors, artifacts byte-identical, manifests identical modulo
run id. `main`'s EntryPoint-loading tests remain green.
**Trigger:** `exitpoint-persistence-contract` (July, this branch) collides with
`exitpoint-primitive-types` (Feb, commit `5d6496a`, already on `main`). Both
solve overlapping problems. This clone was ~5 months behind `origin`, so the
July work was built on a base that never contained the Feb feature.

---

## Situation in one paragraph

You solved a version of this problem twice, five months apart, because a stale
clone hid the first solution from the second. The Feb work (`5d6496a`, now
`main`) added bare-scalar exit persistence **and** EntryPoint scalar loading, but
**no `RootModel[...]` wrapper handlers and no guardrails**. The July work (this
branch) added bare **and** wrapped exit handlers plus two guardrails, but **no
EntryPoint loading**. They are mostly complementary, not competing. The scary
part — that a merge might silently corrupt output — is largely defused: where the
two overlap (bare scalars), their on-disk bytes are identical (verified).

## What each version actually contains

| Capability | Feb `main` (5d6496a) | July branch |
|---|---|---|
| Bare `float/int/str/bool` exit | ✅ `write_json_primitive` | ✅ `write_json_payload` |
| `RootModel[float/int/str/bool]` exit | ❌ **none** | ✅ 4 wrapper handlers |
| EntryPoint scalar **loading** | ✅ strict type-exact | ❌ (explicit non-goal) |
| Defaults-win composition guard | ❌ | ✅ |
| Declared-vs-producer exit cross-check | ❌ | ✅ (D3) |
| Primitive source-of-truth constant | `_PRIMITIVE_TYPES` (executor) | `_DEFAULT_SCALAR_TYPE_NAMES` (router) |
| Cross-repo fusion-tea reproduction | not run | ✅ 13/13, byte-identical |

Locations: Feb — `write_json_primitive` in `writers.py`; 4 bare handlers in
`output_router.py:273-276`; `_PRIMITIVE_TYPES` + `_load_json_primitive` +
`_resolve_schema_type` in `pipeline_executor.py`; validator fallback in
`_build_channel_type_map`. July — 8 handlers in `output_router.py:283-309`;
defaults-win at `output_router.py:381-383`; D3 in `pipeline_validator.py:348-385`.

## The blocker: what fusion-tea actually needs

fusion-tea's generated `ife_hif.yaml` exit block is **7 channels: 5 ×
`RootModel[float]` + 2 × bare `float`** (`ife_hif.yaml:99-107`). All 4 EntryPoint
inputs are named Pydantic models — **no bare primitive is loaded**
(`ife_hif.yaml:12-18`). Its current workaround registers exactly two handler
shapes: `RootModel[float]` and bare `float` (`run_anchors.py:100-113`).

The verdict follows directly:

- **Feb `main` does NOT unblock fusion-tea.** It handles the 2 bare channels but
  none of the 5 wrapped ones. fusion-tea would still need its workaround for
  every `RootModel[float]` exit.
- **The July design DOES unblock it** — it provides exactly the bare + wrapped
  set the workaround registers. Spike-proven and re-verified 2026-07-12:
  workaround deleted, 13/13 anchors pass, artifacts byte-identical.
- **Feb's unique capability (EntryPoint loading) is unused by fusion-tea.** Real,
  but not on the critical path for this blocker.

So for the thing you're actually blocked on, the July mechanism is necessary and
sufficient; the Feb mechanism is insufficient. That is almost certainly why this
felt like unfinished business rather than a duplicate — the Feb pass solved the
bare half and left the wrapped half, which is the half fusion-tea leans on.

## Two latent bugs in `main` that the July guardrails fix

1. **Silent handler clobber.** On `main`,
   `create_output_router_with_json_schemas(["float"])` unconditionally overwrites
   the built-in bare-`float` handler with `write_json_model`, which then crashes
   at write time on a real bare float (`.model_dump()` `AttributeError`). July's
   defaults-win guard prevents this.
2. **False manifest on a mislabeled binding.** `main`'s validator has no
   declared-vs-producer cross-check, so an exit binding declaring `float` for a
   channel that actually carries a model (or a bare/wrapped mix-up) passes
   validation and records a `type_name` the artifact doesn't match. July's D3
   catches it pre-run. This exact bug was live in the battery demo fixture and D3
   caught it.

Neither risk was considered in the Feb design (its risk table covers other
cases). These aren't reasons to disparage the Feb work — they're the specific
hardening the July design contributes.

## Overlap is byte-safe (verified, not assumed)

For every scalar case including falsy (`0.0`, `0`, `""`, `False`), Feb's
`write_json_primitive` (`json.dump(indent=2)`), July's `write_json_payload`, and
July's `write_json_model` (via `RootModel[T].model_dump`) produce **identical
bytes** — `sort_keys`/`indent` don't matter with no container. So whichever bare
writer wins, nothing on disk changes. This is the fact that makes reconciliation
low-risk rather than a guessing game.

## One genuine deviation to carry forward, documented

Feb's EntryPoint loader uses exact type identity (`type(value) is not
expected_type`), stricter than its own design's `isinstance` — deliberate, so a
JSON `true` is rejected by an `int` loader (test-locked:
`test_primitive_entry_loader_rejects_bool_as_int`). It works, but the deviation
is undocumented. If EntryPoint loading survives reconciliation, document it.

## Options

**A. Additive-over-main unified contract (recommended).** Rebuild the July delta
on top of current `main`. Keep everything `main` has (bare handlers, EntryPoint
loading, its tests). Add the three things `main` lacks: the 4 `RootModel[...]`
wrapper handlers, the D3 exit cross-check, the defaults-win guard. Unify the
primitive constant into one source of truth. Union the two test suites.
*Cost:* real reconciliation work — one focused session, plus re-verification.
*Payoff:* loses no capability, fixes both latent bugs, unblocks fusion-tea,
leaves `main` history intact (additive, not a revert).

**B. July supersedes Feb wholesale.** Replace `main`'s writer + registration with
July's, then re-add EntryPoint loading on top. *Cost:* churns a shipped,
byte-identical mechanism for no on-disk benefit, and risks dropping Feb's
EntryPoint loading if the re-add is sloppy. *Payoff:* none over A. Not
recommended.

**C. Ship July's exit contract, defer EntryPoint reconciliation.** Land wrappers
+ guardrails over `main` now (unblocks fusion-tea fastest); leave `main`'s entry
loading as-is and reconcile the constant later. *Cost:* two primitive constants
coexist briefly (`_PRIMITIVE_TYPES` + the router's names) — mild debt.
*Payoff:* smallest change that unblocks you; A's cleanup can follow.

## Recommendation

**Option A**, executed as an additive change on top of current `main` — not a
merge of this branch. If you need fusion-tea unblocked before the full cleanup,
do **C now, converge to A next** (C is a strict subset of A).

Rationale: the two implementations are complementary; the overlap is byte-safe;
and the July guardrails are exactly the bug-catchers that make combining them
safe. "Build the delta over main, deliberately, with tests" beats "merge the
branch and hope" — which is the specific outcome you were right to refuse.

## Safe execution path (addresses "zero confidence we aren't adding bugs")

Each step is independently verifiable; nothing relies on trust.

1. Branch from current `main` (`5d6496a`). Not from this branch.
2. Add the 4 `RootModel[...]` wrapper handler names → `write_json_model`. Keep
   `main`'s `write_json_primitive` for the bare names (shipped, byte-identical).
3. Add the defaults-win guard to `create_output_router_with_json_schemas`.
4. Add the D3 exit cross-check to `_validate_exit_module`. It composes with
   `main`'s entry-primitive validator fallback (different method, no conflict).
5. Unify the primitive names into one constant feeding registry, entry loaders,
   and exit handler names — keeping the `io`→`executor` layering clean (the
   name tuple lives where the router can read it without importing the executor).
6. Port July's tests for the added behaviors; keep all of `main`'s tests.
7. Document the strict entry-loader type check (the undocumented deviation).

**Re-verification bar (all must pass before this lands):**
- July's spec success criteria (`spec.md`) — the acceptance contract already written.
- The fusion-tea reproduction: workaround deleted → 13/13 anchors, artifacts
  byte-identical, manifests identical modulo run id.
- Full `pytest` green (the 4 `test_no_battery_deps.py` env failures excepted).
- `main`'s EntryPoint-loading tests still green (proves nothing regressed).

## Risks to watch during reconciliation

- **D3 against `main`'s codebase.** July tested the bare/wrapped accept-reject
  matrix, so it ports directly — but re-run that matrix on the merged tree, since
  `main`'s `_build_channel_type_map` differs slightly (the primitive fallback).
- **Constant layering.** Don't make `output_router.py` import from
  `pipeline_executor.py` to share the constant — that inverts the I/O→core
  dependency. Put the name tuple where I/O can own it.
- **Process root cause.** The real defect was a clone 5 months stale with nobody
  fetching before new work. Add a pre-work guard that hard-stops if `origin/main`
  is behind, so this cannot recur. Out of scope for the code change; worth a
  ticket.

---

## Provenance notes

- fusion-tea exit/entry shapes, workaround contents, `CUSTOM_SCHEMA_TYPES`:
  investigated against the live fusion-tea tree (`ife_hif.yaml`,
  `run_anchors.py`, `generated/__init__.py`, `generated/primitives.py`).
- Feb implementation details: read from git objects at `5d6496a` (writer, router,
  executor loaders, validator, its `spec/design/plan`, its tests).
- Byte-identity: verified empirically across all 8 scalar cases incl. falsy.
- The reconciliation **direction** is an [OWNER] decision; this doc records an
  [AGENT] recommendation and the evidence behind it.
