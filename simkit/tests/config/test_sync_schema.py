from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from simkit.config import schema, time_utils


_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "synchronous_sim"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_timespan_normalization() -> None:
    one_hour = schema.TimeSpan(raw="1H")
    assert one_hour.delta == pd.Timedelta(hours=1)
    assert one_hour.to_pandas_freq() == "h"

    numeric_minutes = schema.TimeSpan(raw=30, unit="minutes")
    assert numeric_minutes.delta == pd.Timedelta(minutes=30)

    five_minutes = schema.TimeSpan(raw=timedelta(minutes=5))
    assert five_minutes.to_pandas_freq() == "5min"


def test_sync_time_grid_round_trip() -> None:
    grid = schema.SyncTimeGrid(**_load_fixture("time_grid.json"))
    assert grid.outer_duration == pd.Timedelta(hours=1)

    first_outer = grid.outer_steps[0]
    inner_config = grid.inner_loops[0]
    inner_index = time_utils.build_inner_index(first_outer, inner_config)

    assert len(inner_index) == inner_config.samples_per_outer
    assert inner_index[0].tzinfo is not None
    assert inner_index[-1] == inner_index[0] + pd.Timedelta(minutes=55)


def test_price_trajectory_window_slicing() -> None:
    tz = timezone.utc
    trajectory = schema.PriceTrajectory(
        time_index=[datetime(2025, 1, 1, hour, 0, tzinfo=tz) for hour in range(4)],
        values=[0.1, 0.2, 0.3, 0.4],
        currency="USD",
        unit="USD/kWh",
        source="fixture",
    )

    window = trajectory.window(schema.TimeSpan(raw="2H"))
    assert isinstance(window, schema.PriceTrajectoryWindow)
    assert len(window.time_index) == 2
    assert window.start == trajectory.start
    assert window.unit == trajectory.unit


def test_sync_sim_outputs_alignment() -> None:
    tz = timezone.utc
    metadata = schema.MockForecastMetadata(currency="USD", unit="USD/kWh")
    forecast_point = schema.MockForecastPoint(
        outer_index=0,
        issued_at=datetime(2025, 1, 1, 0, 0, tzinfo=tz),
        timestamps=(datetime(2025, 1, 1, 0, 0, tzinfo=tz),),
        values=(0.1,),
        metadata=metadata,
    )
    forecasts = schema.MockForecastSeries(series=(forecast_point,))

    guidance = schema.SyncGuidanceSeries(
        series=(
            schema.SyncGuidance(
                outer_index=0,
                timestamp=datetime(2025, 1, 1, 0, 0, tzinfo=tz),
                setpoint_kw=0.0,
            ),
        )
    )

    inner_times = (
        datetime(2025, 1, 1, 0, 0, tzinfo=tz),
        datetime(2025, 1, 1, 0, 5, tzinfo=tz),
    )
    telemetry_frame = schema.SyncTelemetryFrame(
        outer_index=0,
        timestamp=datetime(2025, 1, 1, 0, 0, tzinfo=tz),
        inner_times=inner_times,
        soc_kwh=(240.0, 241.0),
        charge_in_kw=(0.0, 0.0),
        discharge_in_kw=(0.0, 0.0),
    )
    telemetry = schema.SyncTelemetrySeries(frames=(telemetry_frame,))

    outputs = schema.SyncSimOutputs(
        forecasts=forecasts,
        guidances=guidance,
        telemetry=telemetry,
    )
    assert outputs.forecasts.outer_indices == (0,)

    mismatched_frame = schema.SyncTelemetryFrame(
        outer_index=1,
        timestamp=datetime(2025, 1, 1, 1, 0, tzinfo=tz),
        inner_times=inner_times,
        soc_kwh=(240.0, 241.0),
        charge_in_kw=(0.0, 0.0),
        discharge_in_kw=(0.0, 0.0),
    )
    with pytest.raises(ValueError):
        schema.SyncSimOutputs(
            forecasts=forecasts,
            guidances=guidance,
            telemetry=schema.SyncTelemetrySeries(frames=(mismatched_frame,)),
        )
