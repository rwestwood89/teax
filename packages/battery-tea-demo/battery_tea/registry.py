"""Battery TEA module registry."""
from simkit.core.registry_builder import create_registry

from .modules import (
    RateDataModule,
    ConfigureBatteryModule,
    SimplePerformanceSimModule,
    CostCalculatorModule,
    ProjectAnalyzerModule,
    SynchronousSimModule,
)


def create_battery_registry():
    """Create registry with all battery TEA modules.

    Module types are mapped to YAML-friendly names (without "Module" suffix).
    """
    return create_registry(
        [
            RateDataModule,
            ConfigureBatteryModule,
            SimplePerformanceSimModule,
            CostCalculatorModule,
            ProjectAnalyzerModule,
            SynchronousSimModule,
        ],
        module_type_override={
            RateDataModule: "RateData",
            ConfigureBatteryModule: "ConfigureBattery",
            SimplePerformanceSimModule: "SimplePerformanceSim",
            CostCalculatorModule: "CostCalculator",
            ProjectAnalyzerModule: "ProjectAnalyzer",
            SynchronousSimModule: "SynchronousSim",
        },
    )
