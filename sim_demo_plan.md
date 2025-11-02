# Async Simulation Demo Plan (v0.1)

> Purpose: Stand up **only the asynchronous** pipeline (no in-the-loop physics), proving the module pattern, data models, validation, and tests. Designed to be prompt-ready and implementation-agnostic (no code here).

---

## 1) Repository layout (skeleton)

```
simkit/
  core/
    rate_data/            # RateData module
    battery_config/       # ConfigureBattery module
    cost_calc/            # CostCalculator module
    perf_sim_simple/      # SimplePerformanceSim module
    project_analyzer/     # ProjectAnalyzer module
    pipeline.py           # Orchestrates the async demo flow
  io/
    readers.py            # CSV/Parquet/JSON loaders for fixtures
    writers.py            # Persist outputs to JSON/Parquet
    adapters/             # (optional) external data sources stubs
  config/
    schema.py             # Pydantic data models (types only)
    defaults.py           # Centralized defaults & units
    flags.py              # Feature flags (minimal for demo)
  tests/
    test_rate_data.py
    test_battery_config.py
    test_cost_calc.py
    test_perf_sim_simple.py
    test_project_analyzer.py
    fixtures/             # Small JSON/YAML fixtures for inputs
  README.md
```

---

## 2) Modules (contracts & behavior)

### 2.1 RateData

**Goal:** Normalize and return electricity rate info for a **geography**.

* **Inputs:** `Geography` (country, region/state, utility, timezone, currency).
* **Outputs:** `RateInfo` with:

  * energy price schedule (hourly array aligned to an 8760 template, or TOU bands with mapping)
  * optional demand charges (kW), fixed monthly fees, holidays/calendar
  * metadata: source, vintage/year, currency, escalation rules
* **Methods:**

  * `validate_and_fill_default(Geography) -> Geography` (confirm supported region; fill timezone/currency)
  * `run(Geography) -> RateInfo`
* **Assumptions:** Demo can use static, synthetic TOU; real integrations later via `io.adapters.*`.

### 2.2 ConfigureBattery

**Goal:** Propose a battery config from load and rate context.

* **Inputs:** `LoadProfile8760`, `RateInfo`, optional design constraints (`DesignPrefs`).
* **Outputs:** `BatteryConfig` (capacity\_kwh, power\_kw, charge/discharge limits, roundtrip efficiency, min/max SOC, warranty life).
* **Methods:**

  * `validate_and_fill_default(LoadProfile8760, RateInfo, DesignPrefs?)`
  * `run(...) -> BatteryConfig`
* **Behavior:** Heuristic sizing (demo): size to cover X hours of evening peak or a percentile of daily peak; enforce constraints; attach rationale in metadata.

### 2.3 CostCalculator

**Goal:** Turn a battery config into line-item CAPEX/OPEX and total cost.

* **Inputs:** `BatteryConfig`, `Geography`.
* **Outputs:** `CostBreakdown` (equipment, BOS, installation, labor, permitting, interconnect, contingency; annual O\&M; price year/currency), plus `CapexTotal`.
* **Methods:**

  * `validate_and_fill_default(BatteryConfig, Geography)`
  * `run(...) -> CostBreakdown`
* **Behavior:** Demo uses regional multipliers and learning-curve placeholders; no vendor specifics.

### 2.4 SimplePerformanceSim

**Goal:** Produce **synthetic** telemetry (no physics loop) to enable TEA.

* **Inputs:** `BatteryConfig`, `LoadProfile8760`, optional `PVProfile8760`, `RateInfo` (for TOU-aware charging logic if desired).
* **Outputs:** `BatteryTelemetry8760` (arrays: `charge_in_kwh`, `discharge_out_kwh`, `soc_kwh`).
* **Methods:**

  * `validate_and_fill_default(BatteryConfig, LoadProfile8760, PVProfile8760?)`
  * `run(...) -> BatteryTelemetry8760`
* **Behavior:** Deterministic rule-based profile (e.g., charge in low-price hours up to limits; discharge to shave peak/cover load). Clear limits and unit handling.

### 2.5 ProjectAnalyzer

**Goal:** Convert telemetry and rate info into a financial model snapshot.

* **Inputs:** `RateInfo`, `BatteryTelemetry8760`, optional `FinancialParams`.
* **Outputs:** `FinancialResults` (annual savings, revenue components, cashflow array, NPV, IRR, payback, LCOx; with a **ledger** of line items tied to assumptions).
* **Methods:**

  * `validate_and_fill_default(RateInfo, BatteryTelemetry8760, FinancialParams?)`
  * `run(...) -> FinancialResults`
* **Behavior:** Demo supports energy charge savings and fixed fees; demand charge logic can be stubbed or simplified. Currency/year explicit.

### 2.6 Pipeline (async demo)

**Flow:** Geography → RateData → ConfigureBattery → CostCalculator → SimplePerformanceSim → ProjectAnalyzer → artifacts persisted via `io.writers`.

* **Inputs:** `ScenarioDemo` (geography id, load path, base year/currency, defaults).
* **Outputs:** consolidated JSON: `rate_info`, `battery_config`, `cost_breakdown`, `telemetry`, `financial_results`, plus `provenance` (versions, hashes, flags used).
* **Validation:** Each stage invokes its own `validate_and_fill_default` prior to `run` and short-circuits on error.

**Entry artifacts:**
- Pipeline execution loads the project `.env` before resolving entry bindings so `PYRONDO_INPUT_DIR` and other environment overrides are available.
- Artifact lookup first evaluates the literal path (absolute or relative to the spec file). If that fails, the system prefixes the declared path with `PYRONDO_INPUT_DIR`.
- When `PYRONDO_INPUT_DIR` is unset, it defaults to `<repo>/run_data/inputs`; both attempted paths are reported when resolution ultimately fails.

---

## 3) Data Models (concise spec)

### 3.1 Core

* **Geography**: `country`, `region`, `utility` (str), `timezone` (IANA), `currency` (ISO 4217).
* **LoadProfile8760**: `time_index` (tz-aware), `load_kwh` (float\[8760]), `source`, `unit='kWh'`.
* **RateInfo**:

  * `energy_price_usd_per_kwh` (float\[8760]) **or** `tou_periods` + `mapping[hour->period]`
  * `demand_charge_usd_per_kw` (optional, monthly or seasonal), `fixed_monthly_fee_usd` (optional)
  * `price_year`, `currency`, `vintage`, `source`.
* **DesignPrefs** (optional): `target_peak_shaving_hours`, `max_c_rate`, `min_soc`, `max_soc`, `eta_roundtrip`, `safety_margins`.
* **BatteryConfig**: `capacity_kwh`, `power_kw`, `charge_kw_max`, `discharge_kw_max`, `eta_roundtrip`, `soc_min`, `soc_max`, `lifecycle_warranty` (cycles/years), `notes`.
* **CostBreakdown**:

  * `line_items: [{name, basis, unit_cost, qty, cost, currency}]`
  * `capex_total`, `annual_om_usd`, `price_year`, `assumptions`.
* **BatteryTelemetry8760**: arrays `charge_in_kwh`, `discharge_out_kwh`, `soc_kwh` (length 8760), `constraints_hits` (counts), `method='rule_based_v0'`.
* **FinancialParams**: `discount_rate`, `analysis_years`, `depreciation_method`, `tax_rate`, `escalation_energy`, `escalation_om`.
* **FinancialResults**: `annual_savings`, `cashflow[year]`, `NPV`, `IRR`, `payback_years`, `LCOE/LCOB`, `ledger` (transparent line items), `currency`, `price_year`.
* **ScenarioDemo**: references to `Geography`, `LoadProfile8760`, base year/currency, and toggles.

**Rules:**

* Units explicit and consistent. Arrays aligned to the same time index. Missing optionals filled from `config.defaults`.

---

## 4) Tests (behavioral, no external services)

For **each module**, create two test groups: `validate_and_fill_default` and `run`.

### 4.1 `validate_and_fill_default` tests

* **Invalid input → error**

  * e.g., RateData: unsupported `country`/`utility`; LoadProfile length != 8760; invalid timezone.
  * Expect a typed validation error with clear field paths.
* **Complete & valid input → unchanged**

  * Provide fully-specified objects; assert deep-equality (or equality on fields) post-validation.
* **Incomplete but valid (missing optionals) → completed**

  * Omit `currency` or `timezone` in Geography; defaults filled from `config.defaults`.
  * Omit `eta_roundtrip` or `soc_min/max` in BatteryConfig prefs; verify defaulted and within bounds.

### 4.2 `run()` tests

* **Invalid OR incomplete input → error**

  * Skip the validation call intentionally; `run()` must re-check and raise (defensive programming).
* **Valid & complete input → correct type + basic invariants**

  * RateData: output type `RateInfo`; length 8760; currency/year set.
  * ConfigureBattery: power/energy within constraints; derived fields consistent (e.g., `charge_kw_max <= power_kw`).
  * CostCalculator: totals equal sum of line items; currency and price year consistent.
  * SimplePerformanceSim: telemetry lengths 8760; SOC within \[min,max]; **no energy creation** (discharge limited by previous SOC and efficiency).
  * ProjectAnalyzer: outputs present; NPV/IRR finite; ledger totals reconcile to summary.

**Fixtures:** Small deterministic inputs in `tests/fixtures/`:

* `geography_us_ca_pge.json`
* `load_profile_flat_8760.parquet` and `load_profile_toy_8760.parquet`
* `rateinfo_tou_synthetic.json` (if not generated)
* `financial_params_demo.json`

**Golden outputs (optional, later):** Freeze minimal end-to-end results to catch regressions.

---

## 5) Acceptance Criteria (Demo complete)

**Two usage modes demonstrated and validated:**

**A. Pipeline‑driven mode (DAG config)**

* A YAML (or JSON) scenario + pipeline config is parsed by `pipeline.py`.
* An **Entry Point** validator confirms all required inputs, schemas, rates, and fixtures exist to satisfy the DAG; missing/invalid data causes a fail‑fast error with field paths.
* The pipeline executes the full flow: Geography → RateData → ConfigureBattery → CostCalculator → SimplePerformanceSim → ProjectAnalyzer.
* An **Exit Point** composer aggregates module outputs into a single consolidated JSON with **all** artifacts and **provenance** (versions, hashes, flags).
* All module tests pass; telemetry obeys constraints/units; financial ledger reconciles totals.

**B. Manual / notebook mode**

* A Jupyter notebook executes the same sequence **step by step**, but replaces **exactly one** module with a manually defined artifact (e.g., hand‑specified `RateInfo`), while all other modules are invoked via their `validate_and_fill_default` + `run`.
* Notebook shows that the pipeline is modular: the manually provided artifact plugs into downstream steps without code changes.
* The notebook includes basic assertions on types/shapes/units and produces the same Exit Point consolidated JSON (with provenance noting the manual override).

**General**

* `pipeline.py` (pipeline mode) and the notebook (manual mode) both complete without errors using provided fixtures.
* Reproducibility: outputs include run metadata (config hash, flags JSON, dependency versions).
* CI runs unit tests for all five modules plus an end‑to‑end pipeline test.

---

## 6) Implementation Guidance (brief)

* Centralize defaults and unit constants in `config.defaults`.
* Keep all modules **pure**: `run()` returns data, no I/O (persistence via `io.writers`).
* Each module declares its **schema\_version**; persist provenance (versions, flags, hashes) alongside outputs.
* Keep feature flags minimal for demo (e.g., choose between `flat_rate` vs `tou_synth` in RateData; `heuristic_v1` vs `heuristic_v2` in ConfigureBattery) to prove the registry pattern.

---

## 7) Roadmap after demo

* Introduce real tariff adapters (OpenEI, utility PDFs -> parser).
* Add demand charge modeling and more realistic SimplePerformanceSim controls.
* Plug in TEA depreciation/tax variants; surface to flags.
* Layer the synchronous core loop next (Simulink/FMUs), keeping this async pipeline unchanged.
