"""Registry providing metadata about available pipeline modules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Mapping, MutableMapping

from ..config import schema
from .base import ModuleBase
from .battery_config import ConfigureBatteryModule
from .cost_calc import CostCalculatorModule
from .perf_sim_simple import SimplePerformanceSimModule
from .project_analyzer import ProjectAnalyzerModule
from .rate_data import RateDataModule
from .synchronous_sim import SynchronousSimModule


ModuleFactory = Callable[[], ModuleBase]


@dataclass(frozen=True)
class ModuleDescriptor:
    """Metadata describing inputs/outputs for a pipeline module."""

    module_type: str
    factory: ModuleFactory
    required_inputs: Mapping[str, type[schema.StrictBaseModel]]
    optional_inputs: Mapping[str, type[schema.StrictBaseModel]]
    outputs: Mapping[str, type[schema.StrictBaseModel]]
    version: str


class PipelineModuleRegistry:
    """Holds descriptors for known pipeline modules."""

    def __init__(self, modules: MutableMapping[str, ModuleDescriptor] | None = None) -> None:
        self._modules: Dict[str, ModuleDescriptor] = dict(modules or {})

    @classmethod
    def from_static_modules(cls) -> "PipelineModuleRegistry":
        def _factory(module_cls: type[ModuleBase]) -> ModuleFactory:
            def factory(cls=module_cls) -> ModuleBase:
                return cls()

            return factory

        registry = cls()
        registry.register(
            "RateData",
            ModuleDescriptor(
                module_type="RateData",
                factory=_factory(RateDataModule),
                required_inputs={"geography": schema.Geography},
                optional_inputs={},
                outputs={"rate_info": schema.RateInfo},
                version=RateDataModule.version,
            ),
        )
        registry.register(
            "ConfigureBattery",
            ModuleDescriptor(
                module_type="ConfigureBattery",
                factory=_factory(ConfigureBatteryModule),
                required_inputs={
                    "load_profile": schema.LoadProfile8760,
                    "rate_info": schema.RateInfo,
                },
                optional_inputs={"design_prefs": schema.DesignPrefs},
                outputs={"battery_config": schema.BatteryConfig},
                version=ConfigureBatteryModule.version,
            ),
        )
        registry.register(
            "SimplePerformanceSim",
            ModuleDescriptor(
                module_type="SimplePerformanceSim",
                factory=_factory(SimplePerformanceSimModule),
                required_inputs={
                    "battery": schema.BatteryConfig,
                    "load_profile": schema.LoadProfile8760,
                    "rate_info": schema.RateInfo,
                },
                optional_inputs={"pv_profile": schema.PVProfile8760},
                outputs={"telemetry": schema.BatteryTelemetry8760},
                version=SimplePerformanceSimModule.version,
            ),
        )
        registry.register(
            "CostCalculator",
            ModuleDescriptor(
                module_type="CostCalculator",
                factory=_factory(CostCalculatorModule),
                required_inputs={
                    "config": schema.BatteryConfig,
                    "geography": schema.Geography,
                },
                optional_inputs={},
                outputs={"cost_breakdown": schema.CostBreakdown},
                version=CostCalculatorModule.version,
            ),
        )
        registry.register(
            "ProjectAnalyzer",
            ModuleDescriptor(
                module_type="ProjectAnalyzer",
                factory=_factory(ProjectAnalyzerModule),
                required_inputs={
                    "rate_info": schema.RateInfo,
                    "telemetry": schema.BatteryTelemetry8760,
                },
                optional_inputs={
                    "financial_params": schema.FinancialParams,
                    "cost_breakdown": schema.CostBreakdown,
                },
                outputs={"financial_results": schema.FinancialResults},
                version=ProjectAnalyzerModule.version,
            ),
        )
        registry.register(
            "SynchronousSim",
            ModuleDescriptor(
                module_type="SynchronousSim",
                factory=_factory(SynchronousSimModule),
                required_inputs={
                    "time_grid": schema.SyncTimeGrid,
                    "initial_state": schema.BatteryState,
                    "price_trajectory": schema.PriceTrajectory,
                    "forecast_config": schema.MockForecastConfig,
                    "guidance_config": schema.GuidanceConfig,
                    "dynamics_config": schema.DynamicSimConfig,
                },
                optional_inputs={},
                outputs={
                    "synchronous_sim": schema.SyncSimOutputs,
                    "forecasts": schema.MockForecastSeries,
                    "guidances": schema.SyncGuidanceSeries,
                    "telemetry": schema.SyncTelemetrySeries,
                },
                version=SynchronousSimModule.version,
            ),
        )
        return registry

    def register(self, module_type: str, descriptor: ModuleDescriptor) -> None:
        if module_type in self._modules:
            raise ValueError(f"Module type {module_type!r} already registered")
        self._modules[module_type] = descriptor

    def has(self, module_type: str) -> bool:
        return module_type in self._modules

    def get(self, module_type: str) -> ModuleDescriptor:
        if module_type not in self._modules:
            raise KeyError(module_type)
        return self._modules[module_type]

    def items(self):
        return self._modules.items()

    def copy(self) -> "PipelineModuleRegistry":
        return PipelineModuleRegistry(self._modules)
