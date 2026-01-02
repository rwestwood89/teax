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
    """Create registry with all battery TEA modules."""
    return create_registry([
        RateDataModule,
        ConfigureBatteryModule,
        SimplePerformanceSimModule,
        CostCalculatorModule,
        ProjectAnalyzerModule,
        SynchronousSimModule,
    ])
