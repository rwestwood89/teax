"""Heuristic battery configuration module."""
from __future__ import annotations

from typing import Dict

import numpy as np

from simkit.config.schema import StrictBaseModel
from simkit.core.base import ModuleBase, ModuleResult

from ... import defaults, schemas


class BatteryConfigInputs(StrictBaseModel):
    load_profile: schemas.LoadProfile8760
    rate_info: schemas.RateInfo
    design_prefs: schemas.DesignPrefs


class ConfigureBatteryModule(ModuleBase[BatteryConfigInputs, schemas.BatteryConfig]):
    name = "configure_battery"
    version = "v0.1"

    def _coerce_load(self, load_profile: schemas.LoadProfile8760 | Dict[str, object]) -> schemas.LoadProfile8760:
        if isinstance(load_profile, schemas.LoadProfile8760):
            return load_profile
        return schemas.LoadProfile8760(**load_profile)

    def _coerce_rate(self, rate_info: schemas.RateInfo | Dict[str, object]) -> schemas.RateInfo:
        if isinstance(rate_info, schemas.RateInfo):
            return rate_info
        return schemas.RateInfo(**rate_info)

    def _coerce_prefs(self, prefs: schemas.DesignPrefs | Dict[str, object] | None) -> schemas.DesignPrefs:
        if prefs is None:
            return defaults.default_design_prefs()
        if isinstance(prefs, schemas.DesignPrefs):
            return prefs
        return schemas.DesignPrefs(**prefs)

    def validate_and_fill_default(
        self,
        load_profile: schemas.LoadProfile8760 | Dict[str, object],
        rate_info: schemas.RateInfo | Dict[str, object],
        design_prefs: schemas.DesignPrefs | Dict[str, object] | None = None,
    ) -> BatteryConfigInputs:
        load = self._coerce_load(load_profile)
        rate = self._coerce_rate(rate_info)
        prefs = self._coerce_prefs(design_prefs)

        if load.unit.lower() != "kwh":
            raise ValueError("Load profile must specify unit in kWh")
        if rate.energy_price_usd_per_kwh is None and rate.tou_periods is None:
            raise ValueError("Rate info must contain energy pricing")
        if prefs.min_soc is not None and prefs.max_soc is not None and prefs.min_soc >= prefs.max_soc:
            raise ValueError("Design prefs min_soc must be less than max_soc")

        return BatteryConfigInputs(load_profile=load, rate_info=rate, design_prefs=prefs)

    def _sizing_heuristic(self, inputs: BatteryConfigInputs) -> schemas.BatteryConfig:
        prefs = inputs.design_prefs
        load_array = np.array(inputs.load_profile.load_kwh)

        target_hours = prefs.target_peak_shaving_hours or 4.0
        representative_peak = float(np.percentile(load_array, 95))
        capacity_kwh = representative_peak * target_hours

        max_c_rate = prefs.max_c_rate or 0.5
        power_kw = min(capacity_kwh * max_c_rate, representative_peak)
        power_kw = max(power_kw, representative_peak * 0.6)

        charge_kw_max = power_kw
        discharge_kw_max = power_kw

        eta_roundtrip = prefs.eta_roundtrip or defaults.DEFAULT_ROUNDTRIP_EFFICIENCY
        soc_min = prefs.min_soc if prefs.min_soc is not None else defaults.DEFAULT_SOC_MIN
        soc_max = prefs.max_soc if prefs.max_soc is not None else defaults.DEFAULT_SOC_MAX

        return schemas.BatteryConfig(
            capacity_kwh=round(capacity_kwh, 2),
            power_kw=round(power_kw, 2),
            charge_kw_max=round(charge_kw_max, 2),
            discharge_kw_max=round(discharge_kw_max, 2),
            eta_roundtrip=round(eta_roundtrip, 4),
            soc_min=round(soc_min, 3),
            soc_max=round(soc_max, 3),
            lifecycle_warranty_cycles=4000,
            lifecycle_warranty_years=10,
            notes=defaults.DEFAULT_BATTERY_NOTES,
            rationale="Sized to cover high-price evening hours using heuristic percentile load",
        )

    def run(
        self,
        load_profile: schemas.LoadProfile8760 | Dict[str, object],
        rate_info: schemas.RateInfo | Dict[str, object],
        design_prefs: schemas.DesignPrefs | Dict[str, object] | None = None,
    ) -> ModuleResult[schemas.BatteryConfig]:
        inputs = self.validate_and_fill_default(load_profile, rate_info, design_prefs)
        config = self._sizing_heuristic(inputs)
        return ModuleResult(config, notes="Heuristic battery sizing complete")
