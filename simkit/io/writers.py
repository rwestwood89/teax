"""Output persistence helpers for the async demo."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

import pandas as pd

from ..config import schema


def write_json_model(model: schema.StrictBaseModel, path: str | Path) -> Path:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump(mode="json")
    with resolved.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return resolved


def write_json_payload(payload: Dict[str, Any] | schema.StrictBaseModel | Any, path: str | Path) -> Path:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, schema.StrictBaseModel):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    with resolved.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    return resolved


def write_parquet_telemetry(telemetry: schema.BatteryTelemetry8760, path: str | Path) -> Path:
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


def write_provenance(metadata: Dict[str, Any], path: str | Path) -> Path:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)
    return resolved


def write_mock_forecast_series(
    series: schema.MockForecastSeries, path: str | Path
) -> Path:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = series.model_dump(mode="json")
    with resolved.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return resolved


def write_sync_guidance_series(
    series: schema.SyncGuidanceSeries, path: str | Path
) -> Path:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = series.model_dump(mode="json")
    with resolved.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return resolved


def write_sync_telemetry_series(
    series: schema.SyncTelemetrySeries, path: str | Path
) -> Path:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    frame = _telemetry_frames_to_dataframe(series.frames)
    frame.to_parquet(resolved, index=False)
    return resolved


def _telemetry_frames_to_dataframe(
    frames: Iterable[schema.SyncTelemetryFrame],
) -> pd.DataFrame:
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
