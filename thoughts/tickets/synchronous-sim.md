# Ticket: Add coverage for default-filling validation paths

**Created:** 2025-09-23
**Priority:** High
**Type:** Feature
**Status:** In Progress

## Overview

Create a functional module which wraps a synchronous simulation, including calling an extrnal matlab code. 

## Description

- MUST be able to run "in-the-loop" synchronous simulations as part of our graph-based, (asynchronous) simulation framework
- Within this loop, there will be multiple components:
 - Mock Forecast
 - Business Logic
 - Dynamical Sim: physics + control code
- The physics and control code live in matlab; we will need a python wrapper to invoke it
 - We MUST reference external packages for this, e.g. https://www.mathworks.com/help/matlab/matlab-engine-for-python.html
- The scope of this ticket is to demonstrate the design works, including calling python code
- We do NOT need comprehensive, realistic DataModels and functional models for the forecasting and business logic. Simple is good for now. 

Below is a sample stencil for the code. Use it for guidance ONLY! There are known issues with it. It will need to be adapted to fit our patterns. 

```
class SimInputs:
    time_index: pd.DatetimeIndex
    init_battery_state: BatteryState
    
    pricing_data: np.ndarray
    
    mock_forecast_config: MockForecastConfig  # add noise to actuals
    business_logic_config: BusinessLogicConfig
    dynamic_sim_config: DynamicSimConfig

class SimOutputs:
    forecasts: PriceForecasts[]
    guidances: Guidance[]
    battery_telemetry: BatteryTelemetry

class SynchronousSim:
    def run(BusinessLogic, DynamicSim, MockForecast,inputs: SimInputs):
        self._bl = BusinessLogic(Sim_Inputs.business_logic_config)
        self._ds = DynamicSim(Sim_Inputs.dynamic_sim_config)
        self._mf = MockForecast(Sim_Inputs.mock_forecast_config)
        self.forecasts = []
        self.guidances = []
        self.battery_telemetry = BatteryTelemetry()
        self.battery_telemetry[0] = inputs.init_battery_state
        
        for ti, tstamp in enumerate(inputs.time_index):
            # Mock a forecast
            self.forecasts[ti] = self._mf.step(inputs.pricing_data[ti])
            # Guidance based on forecast and running battery system data
            self.guidances[ti] = self._bl.step(self.forecasts[ti], self.battery_telemetry[:ti])
            # Pass updated guidance to physics sim
            self.battery_telemetry[ti] = self._ds.step(self.guidances[ti])
        
        return SimOutputs({
            "forecasts": self.forecasts,
            "guidances": self.guidances,
            "battery_telemetry": self.battery_telemetry
        })

# --- config for the Simulink bridge ---
@dataclass(frozen=True)
class DynamicSimConfig:
    # hard-coded dummy paths/names per your instruction
    model_path: str = "/opt/matlab/models/battery_system_model.slx"
    model_name: str = "battery_system_model"
    dt_hours: float = 1.0
    # names of variables/signals used for data exchange
    var_guidance_target_name: str = "guidance_target_charge_kwh_h1"
    var_guidance_usage_name: str  = "guidance_usage_forecast_kwh_h1"
    signal_charge_kw: str = "charge_kW"   # logged signal name in Simulink
    signal_discharge_kw: str = "discharge_kW"
    signal_soc_kwh: str = "soc_kWh"
    use_fast_restart: bool = True
    sim_mode: str = "accelerator"  # or "normal"

class DynamicSim:
    """
    Stateful bridge to a Simulink model via MATLAB Engine.

    Minimal contract for your SynchronousSim:
      - __init__(config): prepare engine + model
      - step(guidance) -> BatteryTelemetryPoint: advance one tick (dt_hours)
    """
    def __init__(self, cfg: DynamicSimConfig):
        self.cfg = cfg
        self._eng = None
        self._t_seconds = 0.0  # current simulation time in seconds
        self._initialized = False

        # start MATLAB and load the model
        self._start_engine_and_load()
    
    # ---- public API used by SynchronousSim ----
    def step(self, guidance: Guidance) -> BatteryTelemetryPoint:
        """Advance Simulink by one dt using current guidance; return per-tick telemetry."""
        
        start_s = self._t_seconds
        stop_s = self._t_seconds + dt_s

        sim_args = self._eng.struct(
            "SaveOutput", "on",
            "ReturnWorkspaceOutputs", "on",
            "StartTime", str(start_s),
            "StopTime",  str(stop_s),
            nargout=1
        )
        sim_out = self._eng.sim(self.cfg.model_name, sim_args, nargout=1)
        
        # Pull logged signals (adapt names to Python model)
        logs = sim_out["logsout"]
        charge_ts    = self._eng.getElement(logs, self.cfg.signal_charge_kw)
        discharge_ts = self._eng.getElement(logs, self.cfg.signal_discharge_kw)
        soc_ts       = self._eng.getElement(logs, self.cfg.signal_soc_kwh)

        charge_kwh    = self._kw_timeseries_to_kwh(charge_ts)
        discharge_kwh = self._kw_timeseries_to_kwh(discharge_ts)
        soc_kwh       = self._last_value(soc_ts)

        # advance internal clock
        self._t_seconds = stop_s

        return BatteryTelemetryPoint(
            charge_kwh=charge_kwh,
            discharge_kwh=discharge_kwh,
            soc_kwh=soc_kwh,
        )
        
    # ---- private methods ----
    def _start_engine_and_load(self):
        import matlab.engine  # MATLAB Engine for Python

        self._eng = matlab.engine.start_matlab()
        # Load the model from a hard-coded path; keep the model name handy
        self._eng.load_system(self.cfg.model_path, nargout=0) 

```
