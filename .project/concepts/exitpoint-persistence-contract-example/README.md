# heater_tea — toy end-state for the ExitPoint persistence contract

Companion to `../exitpoint-persistence-contract.md`. A minimal but complete
picture of a sysml-codegen-generated package running on TEAx *after* the
contract change. Layout and idioms mirror the real generated package at
`fusion-tea/exploration/ife_e2e/generated/` (module wrapper shape,
`MultiOutput` containers, `primitives.py`, registry `__init__.py`, YAML
conventions). Elided as noise: `__init__.py` stubs, handwritten impls, tests.

## Layout

```
run.py                                  # consumer harness  ★ THE payoff
heater_tea/                             # "generated" package
├── __init__.py                         # registry + CUSTOM_SCHEMA_TYPES  ★ shorter
├── primitives.py                       # Float/Int/String/Bool aliases  ★ demoted
├── schemas/
│   ├── heater_params.py                # entry param group        (unchanged)
│   ├── cost_breakdown.py               # domain-named schema      (unchanged)
│   └── cost_calc_output.py             # MultiOutput container    (unchanged)
└── modules/
    ├── efficiency_calc.py              # single-output RootModel[float] (unchanged)
    └── cost_calc.py                    # multi-output, bare-scalar fields (unchanged)
inputs/heater_params.json               # EntryPoint artifact      (unchanged)
pipelines/heater.yaml                   # wiring + ExitPoint  ★ now valid as-is
outputs/heater_tea_results-3f2a9c1b/    # example persisted run  ★ previously impossible
```

## The one flow to trace

`CostCalcModule.run()` returns natural Python (`lcoe_usd_mwh=157.5`,
`viable=True`, ...) inside a `CostCalcOutput`. The executor decomposes it:
four channels carry **bare scalars**, one carries a `CostBreakdown`. The
single-output `EfficiencyCalcModule` puts a whole `Float` (=
`RootModel[float]`) on its channel. At the ExitPoint, all six persist through
TEAx's default router — five via the new JSON-native handlers, `CostBreakdown`
via `CUSTOM_SCHEMA_TYPES` exactly as today.

Note the artifacts: `efficiency.json` contains `0.87` and `lcoe_usd_mwh.json`
contains `157.5` — identical representation whether the channel was wrapped
or bare. Files never leak internal plumbing (contract Principle 4).

## What is different from today (★), file by file

| File | Change |
|---|---|
| `run.py` | **The deleted boilerplate.** Today every harness hand-builds a router and a `"float"` lambda handler (the old block is quoted in a comment). Now: `execute_pipeline(spec, registry=..., custom_schema_types=...)` — persistence is zero lines. |
| `pipelines/heater.yaml` | **Not a changed file — a newly *valid* one.** Codegen already emits these exact types; today the five scalar exit lines fail pre-run validation (T-1) and, forced past, crash `write_json_model` (T-2). The exit block comments mark which lines the default router now covers. |
| `heater_tea/__init__.py` | `CUSTOM_SCHEMA_TYPES = [HeaterParams, CostBreakdown]` — **domain schemas only**. Today codegen appends `Float` here purely to feed the exit router; the bare `float` channels couldn't be expressed here at all. |
| `heater_tea/primitives.py` | **Kept as a typing convenience, demoted from load-bearing.** Modules still type against `Float`, but the wrappers no longer ride `CUSTOM_SCHEMA_TYPES`; codegen's `_collect_exit_point_primitive_types()` becomes removable (follow-up ticket). |
| `outputs/.../` | **The previously-impossible artifacts.** `lcoe_usd_mwh.json` (`157.5`), `unit_count.json` (`2`), `cost_class.json` (`"moderate"`), `viable.json` (`true`) are bare-scalar channels persisted by default handlers. `manifest.json` records their type names (`float`, `int`, `str`, `bool`, `RootModel[float]`) — the eight names the default router now knows. |
| everything else | **Byte-for-byte what codegen emits today.** Schemas, modules, containers, input JSON: untouched. The module author's Python stays natural — no wrappers on fields, no new boilerplate. The entire change lands in TEAx's `create_default_router()`. |

## What TEAx changed to make this run (for reference)

Eight default handler names in `create_default_router()`: `float`, `int`,
`str`, `bool` → `write_json_payload`; `RootModel[float]`, `RootModel[int]`,
`RootModel[str]`, `RootModel[bool]` → `write_json_model`. Nothing else — no
validator changes, no new writers, no executor changes. Unknown types (e.g. a
`bytes` field) still fail fast pre-run.
