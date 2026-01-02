"""Rule-based hourly performance simulator."""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from simkit.config.schema import StrictBaseModel
from simkit.core.base import ModuleBase, ModuleResult

from ... import defaults, schemas


class PerformanceInputs(StrictBaseModel):
    battery: schemas.BatteryConfig
    load_profile: schemas.LoadProfile8760
    pv_profile: Optional[schemas.PVProfile8760] = None
    rate_info: schemas.RateInfo


class SimplePerformanceSimModule(
    ModuleBase[PerformanceInputs, schemas.BatteryTelemetry8760]
):
    name = "simple_performance_sim"
    version = "v0.1"

    def _coerce_battery(self, config: schemas.BatteryConfig | Dict[str, object]) -> schemas.BatteryConfig:
        if isinstance(config, schemas.BatteryConfig):
            return config
        return schemas.BatteryConfig(**config)

    def _coerce_load(self, load: schemas.LoadProfile8760 | Dict[str, object]) -> schemas.LoadProfile8760:
        if isinstance(load, schemas.LoadProfile8760):
            return load
        return schemas.LoadProfile8760(**load)

    def _coerce_pv(self, pv: schemas.PVProfile8760 | Dict[str, object] | None) -> schemas.PVProfile8760 | None:
        if pv is None:
            return None
        if isinstance(pv, schemas.PVProfile8760):
            return pv
        return schemas.PVProfile8760(**pv)

    def _coerce_rate(self, rate: schemas.RateInfo | Dict[str, object]) -> schemas.RateInfo:
        if isinstance(rate, schemas.RateInfo):
            return rate
        return schemas.RateInfo(**rate)

    def validate_and_fill_default(
        self,
        battery: schemas.BatteryConfig | Dict[str, object],
        load_profile: schemas.LoadProfile8760 | Dict[str, object],
        pv_profile: schemas.PVProfile8760 | Dict[str, object] | None,
        rate_info: schemas.RateInfo | Dict[str, object],
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
        return PerformanceInputs(battery=battery_config, load_profile=load, pv_profile=pv, rate_info=rate)

    def _hourly_prices(self, inputs: PerformanceInputs) -> np.ndarray:
        rate = inputs.rate_info
        if rate.energy_price_usd_per_kwh is not None:
            return np.array(rate.energy_price_usd_per_kwh)
        assert rate.tou_periods is not None and rate.tou_mapping_hourly is not None
        return np.array([rate.tou_periods[label] for label in rate.tou_mapping_hourly])

    def _simulate(self, inputs: PerformanceInputs) -> schemas.BatteryTelemetry8760:
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

        return schemas.BatteryTelemetry8760(
            charge_in_kwh=charge_series.tolist(),
            discharge_out_kwh=discharge_series.tolist(),
            soc_kwh=soc_series.tolist(),
            constraints_hits=hits,
            method=defaults.DEFAULT_METHOD,
        )

    def run(
        self,
        battery: schemas.BatteryConfig | Dict[str, object],
        load_profile: schemas.LoadProfile8760 | Dict[str, object],
        pv_profile: schemas.PVProfile8760 | Dict[str, object] | None,
        rate_info: schemas.RateInfo | Dict[str, object],
    ) -> ModuleResult[schemas.BatteryTelemetry8760]:
        inputs = self.validate_and_fill_default(battery, load_profile, pv_profile, rate_info)
        telemetry = self._simulate(inputs)
        return ModuleResult(telemetry, notes="Generated heuristic telemetry")
