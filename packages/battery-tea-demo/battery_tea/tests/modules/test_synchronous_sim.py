"""Tests for SynchronousSimModule."""
from __future__ import annotations

from pathlib import Path

import pytest

from simkit.config import schema
from simkit.io.readers import read_json_model
from battery_tea import schemas
from battery_tea.modules.synchronous_sim import SynchronousSimModule

SYNC_FIXTURES = Path(__file__).parent.parent / "fixtures" / "synchronous_sim"


@pytest.fixture
def time_grid() -> schema.SyncTimeGrid:
    return read_json_model(SYNC_FIXTURES / "time_grid.json", schema.SyncTimeGrid)


@pytest.fixture
def initial_state() -> schemas.BatteryState:
    return read_json_model(SYNC_FIXTURES / "initial_state.json", schemas.BatteryState)


@pytest.fixture
def forecast_config() -> schema.MockForecastConfig:
    return read_json_model(SYNC_FIXTURES / "forecast_config.json", schema.MockForecastConfig)


@pytest.fixture
def guidance_config() -> schemas.GuidanceConfig:
    return read_json_model(SYNC_FIXTURES / "guidance_config.json", schemas.GuidanceConfig)


@pytest.fixture
def dynamics_config() -> schema.DynamicSimConfig:
    return read_json_model(SYNC_FIXTURES / "dynamic_sim_config.json", schema.DynamicSimConfig)


@pytest.fixture
def price_trajectory_dict() -> dict:
    """Return raw dict for price trajectory (requires special parsing)."""
    import json
    with open(SYNC_FIXTURES / "actual_pricing.json") as f:
        return json.load(f)


class TestSynchronousSimModuleValidation:
    """Tests for validate_and_fill_default."""

    def test_complete_inputs_valid(
        self,
        time_grid: schema.SyncTimeGrid,
        initial_state: schemas.BatteryState,
        forecast_config: schema.MockForecastConfig,
        guidance_config: schemas.GuidanceConfig,
        dynamics_config: schema.DynamicSimConfig,
        price_trajectory_dict: dict,
    ):
        """Complete inputs validate successfully."""
        module = SynchronousSimModule()

        inputs = module.validate_and_fill_default(
            time_grid=time_grid,
            initial_state=initial_state,
            price_trajectory=price_trajectory_dict,
            forecast_config=forecast_config,
            guidance_config=guidance_config,
            dynamics_config=dynamics_config,
        )

        assert inputs.time_grid == time_grid
        assert inputs.initial_state == initial_state
        assert inputs.forecast_config == forecast_config
        assert inputs.guidance_config == guidance_config


class TestSynchronousSimModuleRun:
    """Tests for run method."""

    def test_run_produces_sync_sim_outputs(
        self,
        time_grid: schema.SyncTimeGrid,
        initial_state: schemas.BatteryState,
        forecast_config: schema.MockForecastConfig,
        guidance_config: schemas.GuidanceConfig,
        dynamics_config: schema.DynamicSimConfig,
        price_trajectory_dict: dict,
    ):
        """Run produces SyncSimOutputs."""
        module = SynchronousSimModule()

        result = module.run(
            time_grid=time_grid,
            initial_state=initial_state,
            price_trajectory=price_trajectory_dict,
            forecast_config=forecast_config,
            guidance_config=guidance_config,
            dynamics_config=dynamics_config,
        )

        assert result.data is not None
        assert isinstance(result.data, schemas.SyncSimOutputs)

    def test_run_produces_forecasts(
        self,
        time_grid: schema.SyncTimeGrid,
        initial_state: schemas.BatteryState,
        forecast_config: schema.MockForecastConfig,
        guidance_config: schemas.GuidanceConfig,
        dynamics_config: schema.DynamicSimConfig,
        price_trajectory_dict: dict,
    ):
        """Run produces forecast series."""
        module = SynchronousSimModule()

        result = module.run(
            time_grid=time_grid,
            initial_state=initial_state,
            price_trajectory=price_trajectory_dict,
            forecast_config=forecast_config,
            guidance_config=guidance_config,
            dynamics_config=dynamics_config,
        )

        forecasts = result.data.forecasts
        assert forecasts is not None
        # Should have one forecast per outer step
        assert len(forecasts.series) == len(time_grid.outer_steps)

    def test_run_produces_guidances(
        self,
        time_grid: schema.SyncTimeGrid,
        initial_state: schemas.BatteryState,
        forecast_config: schema.MockForecastConfig,
        guidance_config: schemas.GuidanceConfig,
        dynamics_config: schema.DynamicSimConfig,
        price_trajectory_dict: dict,
    ):
        """Run produces guidance series."""
        module = SynchronousSimModule()

        result = module.run(
            time_grid=time_grid,
            initial_state=initial_state,
            price_trajectory=price_trajectory_dict,
            forecast_config=forecast_config,
            guidance_config=guidance_config,
            dynamics_config=dynamics_config,
        )

        guidances = result.data.guidances
        assert guidances is not None
        assert len(guidances.series) == len(time_grid.outer_steps)

    def test_run_produces_telemetry(
        self,
        time_grid: schema.SyncTimeGrid,
        initial_state: schemas.BatteryState,
        forecast_config: schema.MockForecastConfig,
        guidance_config: schemas.GuidanceConfig,
        dynamics_config: schema.DynamicSimConfig,
        price_trajectory_dict: dict,
    ):
        """Run produces telemetry series."""
        module = SynchronousSimModule()

        result = module.run(
            time_grid=time_grid,
            initial_state=initial_state,
            price_trajectory=price_trajectory_dict,
            forecast_config=forecast_config,
            guidance_config=guidance_config,
            dynamics_config=dynamics_config,
        )

        telemetry = result.data.telemetry
        assert telemetry is not None
        assert len(telemetry.frames) == len(time_grid.outer_steps)

    def test_run_includes_notes(
        self,
        time_grid: schema.SyncTimeGrid,
        initial_state: schemas.BatteryState,
        forecast_config: schema.MockForecastConfig,
        guidance_config: schemas.GuidanceConfig,
        dynamics_config: schema.DynamicSimConfig,
        price_trajectory_dict: dict,
    ):
        """Run includes execution notes."""
        module = SynchronousSimModule()

        result = module.run(
            time_grid=time_grid,
            initial_state=initial_state,
            price_trajectory=price_trajectory_dict,
            forecast_config=forecast_config,
            guidance_config=guidance_config,
            dynamics_config=dynamics_config,
        )

        assert result.notes is not None
