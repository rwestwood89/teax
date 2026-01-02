"""Rule-based hourly performance simulator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from ...config import battery_schema, defaults
from ..base import ModuleBase, ModuleResult


@dataclass(frozen=True)
class PerformanceInputs:
    battery: battery_schema.BatteryConfig
    load_profile: battery_schema.LoadProfile8760
    pv_profile: battery_schema.PVProfile8760 | None
    rate_info: battery_schema.RateInfo


class SimplePerformanceSimModule(
    ModuleBase[PerformanceInputs, battery_schema.BatteryTelemetry8760]
):
    name = "simple_performance_sim"
    version = "v0.1"

    def _coerce_battery(self, config: battery_schema.BatteryConfig | Dict[str, object]) -> battery_schema.BatteryConfig:
        if isinstance(config, battery_schema.BatteryConfig):
            return config
        return battery_schema.BatteryConfig(**config)

    def _coerce_load(self, load: battery_schema.LoadProfile8760 | Dict[str, object]) -> battery_schema.LoadProfile8760:
        if isinstance(load, battery_schema.LoadProfile8760):
            return load
        return battery_schema.LoadProfile8760(**load)

    def _coerce_pv(self, pv: battery_schema.PVProfile8760 | Dict[str, object] | None) -> battery_schema.PVProfile8760 | None:
        if pv is None:
            return None
        if isinstance(pv, battery_schema.PVProfile8760):
            return pv
        return battery_schema.PVProfile8760(**pv)

    def _coerce_rate(self, rate: battery_schema.RateInfo | Dict[str, object]) -> battery_schema.RateInfo:
        if isinstance(rate, battery_schema.RateInfo):
            return rate
        return battery_schema.RateInfo(**rate)

    def validate_and_fill_default(
        self,
        battery: battery_schema.BatteryConfig | Dict[str, object],
        load_profile: battery_schema.LoadProfile8760 | Dict[str, object],
        pv_profile: battery_schema.PVProfile8760 | Dict[str, object] | None,
        rate_info: battery_schema.RateInfo | Dict[str, object],
    ) -> PerformanceInputs:
        battery_config = self._coerce_battery(battery)
        load = self._coerce_load(load_profile)
        pv = self._coerce_pv(pv_profile)
        rate = self._coerce_rate(rate_info)

        if pv and load.time_index != pv.time_index:
            raise ValueError("PV profile time index must match load profile")
        if rate.energy_price_usd_per_kwh is None and rate.tou_mapping_hourly is None:
            raise ValueError("Rate info must contain hourly pricing or TOU mapping")
        if not (0.0 <= battery_config.soc_min < battery_config.soc_max <= 1.0):
            raise ValueError("Battery SOC bounds must satisfy 0 <= min < max <= 1")
        return PerformanceInputs(battery_config, load, pv, rate)

    def _hourly_prices(self, inputs: PerformanceInputs) -> np.ndarray:
        rate = inputs.rate_info
        if rate.energy_price_usd_per_kwh is not None:
            return np.array(rate.energy_price_usd_per_kwh)
        assert rate.tou_periods is not None and rate.tou_mapping_hourly is not None
        return np.array([rate.tou_periods[label] for label in rate.tou_mapping_hourly])

    def _simulate(self, inputs: PerformanceInputs) -> battery_schema.BatteryTelemetry8760:
        battery = inputs.battery
        load = np.array(inputs.load_profile.load_kwh)
        pv = (
            np.array(inputs.pv_profile.production_kwh)
            if inputs.pv_profile is not None
            else np.zeros_like(load)
        )
        net_load = np.clip(load - pv, a_min=0.0, a_max=None)
        prices = self._hourly_prices(inputs)

        charge_threshold = float(np.percentile(prices, 30))
        discharge_threshold = float(np.percentile(prices, 70))
        peak_net_load = float(np.percentile(net_load, 80))

        capacity = battery.capacity_kwh
        soc_min = capacity * battery.soc_min
        soc_max = capacity * battery.soc_max
        soc = capacity * (battery.soc_min + (battery.soc_max - battery.soc_min) / 2)
        charge_eff = discharge_eff = np.sqrt(battery.eta_roundtrip)

        charge_series = np.zeros(8760)
        discharge_series = np.zeros(8760)
        soc_series = np.zeros(8760)
        hits = {"soc_min": 0, "soc_max": 0}

        for hour in range(8760):
            price = prices[hour]
            demand = net_load[hour]

            # Prioritize discharging during high-price or net load peaks.
            should_discharge = price >= discharge_threshold or demand > peak_net_load
            should_charge = price <= charge_threshold and not should_discharge

            if should_discharge:
                available = soc - soc_min
                discharge_kw = min(available, battery.discharge_kw_max)
                discharge_kw = max(discharge_kw, 0.0)
                discharge_series[hour] = discharge_kw * discharge_eff
                soc = soc - discharge_kw
            elif should_charge:
                headroom = soc_max - soc
                charge_kw = min(headroom, battery.charge_kw_max)
                charge_kw = max(charge_kw, 0.0)
                charge_series[hour] = charge_kw
                soc = soc + charge_kw * charge_eff

            soc = min(max(soc, soc_min), soc_max)
            if np.isclose(soc, soc_min, atol=1e-3):
                hits["soc_min"] += 1
            if np.isclose(soc, soc_max, atol=1e-3):
                hits["soc_max"] += 1
            soc_series[hour] = soc

        return battery_schema.BatteryTelemetry8760(
            charge_in_kwh=charge_series.tolist(),
            discharge_out_kwh=discharge_series.tolist(),
            soc_kwh=soc_series.tolist(),
            constraints_hits=hits,
            method=defaults.DEFAULT_METHOD,
        )

    def run(
        self,
        battery: battery_schema.BatteryConfig | Dict[str, object],
        load_profile: battery_schema.LoadProfile8760 | Dict[str, object],
        pv_profile: battery_schema.PVProfile8760 | Dict[str, object] | None,
        rate_info: battery_schema.RateInfo | Dict[str, object],
    ) -> ModuleResult[battery_schema.BatteryTelemetry8760]:
        inputs = self.validate_and_fill_default(battery, load_profile, pv_profile, rate_info)
        telemetry = self._simulate(inputs)
        return ModuleResult(telemetry, notes="Generated heuristic telemetry")
