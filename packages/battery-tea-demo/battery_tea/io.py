"""Battery-specific I/O utilities for reading and writing battery data."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List
from zoneinfo import ZoneInfo

import pandas as pd

from . import schemas
from .defaults import DEFAULT_PRICE_YEAR


def default_time_index(year: int, timezone: str) -> List[datetime]:
    """Generate a default 8760-hour time index for a given year."""
    zone = ZoneInfo(timezone)
    start = datetime(year=year, month=1, day=1, tzinfo=zone)
    return [start + timedelta(hours=offset) for offset in range(8760)]


def read_parquet_load_profile(path: str | Path, source: str = "fixture") -> schemas.LoadProfile8760:
    """Read a load profile from a Parquet file.

    Args:
        path: Path to the Parquet file
        source: Source identifier for provenance

    Returns:
        LoadProfile8760 schema object
    """
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")

    frame = pd.read_parquet(resolved)
    if "load_kwh" not in frame.columns:
        raise ValueError("Parquet load profile must contain 'load_kwh' column")
    if "timestamp" in frame.columns:
        ts = pd.to_datetime(frame["timestamp"], utc=False)
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        time_index = ts.dt.tz_convert("UTC")
    else:
        time_index = default_time_index(DEFAULT_PRICE_YEAR, "UTC")
    return schemas.LoadProfile8760(
        time_index=[ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts for ts in time_index],
        load_kwh=frame["load_kwh"].tolist(),
        source=source,
    )


def read_parquet_pv_profile(path: str | Path, source: str = "fixture") -> schemas.PVProfile8760:
    """Read a PV production profile from a Parquet file.

    Args:
        path: Path to the Parquet file
        source: Source identifier for provenance

    Returns:
        PVProfile8760 schema object
    """
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")

    frame = pd.read_parquet(resolved)
    if "production_kwh" not in frame.columns:
        raise ValueError("PV profile parquet must contain 'production_kwh'")
    if "timestamp" in frame.columns:
        ts = pd.to_datetime(frame["timestamp"], utc=False)
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        time_index = ts.dt.tz_convert("UTC")
    else:
        time_index = default_time_index(DEFAULT_PRICE_YEAR, "UTC")
    return schemas.PVProfile8760(
        time_index=[ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts for ts in time_index],
        production_kwh=frame["production_kwh"].tolist(),
        source=source,
    )


def write_parquet_telemetry(telemetry: schemas.BatteryTelemetry8760, path: str | Path) -> Path:
    """Write battery telemetry to a Parquet file.

    Args:
        telemetry: BatteryTelemetry8760 schema object
        path: Path to write the Parquet file

    Returns:
        Path to the written file
    """
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "charge_in_kwh": telemetry.charge_in_kwh,
            "discharge_out_kwh": telemetry.discharge_out_kwh,
            "soc_kwh": telemetry.soc_kwh,
        }
    )
    frame.to_parquet(resolved, index=False)
    return resolved


def write_sync_telemetry_series(
    series: schemas.SyncTelemetrySeries, path: str | Path
) -> Path:
    """Write synchronous simulation telemetry to a Parquet file.

    Args:
        series: SyncTelemetrySeries schema object
        path: Path to write the Parquet file

    Returns:
        Path to the written file
    """
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    frame = _telemetry_frames_to_dataframe(series.frames)
    frame.to_parquet(resolved, index=False)
    return resolved


def _telemetry_frames_to_dataframe(
    frames: Iterable[schemas.SyncTelemetryFrame],
) -> pd.DataFrame:
    """Convert telemetry frames to a pandas DataFrame."""
    rows: list[Dict[str, Any]] = []
    for frame in frames:
        for idx, inner_ts in enumerate(frame.inner_times):
            rows.append(
                {
                    "outer_index": frame.outer_index,
                    "outer_timestamp": frame.timestamp,
                    "inner_timestamp": inner_ts,
                    "soc_kwh": frame.soc_kwh[idx],
                    "charge_in_kw": frame.charge_in_kw[idx],
                    "discharge_in_kw": frame.discharge_in_kw[idx],
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "outer_index",
                "outer_timestamp",
                "inner_timestamp",
                "soc_kwh",
                "charge_in_kw",
                "discharge_in_kw",
            ]
        )
    return pd.DataFrame(rows)
