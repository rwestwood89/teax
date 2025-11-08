"""Input adapters for loading fixtures and configs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Type, TypeVar

import pandas as pd
import yaml
from pydantic import BaseModel

from ..config import defaults, schema
from ..config.pipeline_schema import PipelineSpecLoader, PipelineSpecification

ModelT = TypeVar("ModelT", bound=BaseModel)


def _load_raw(path: str | Path, loader: Callable[[Path], Any]) -> Any:
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")
    return loader(resolved)


def read_json_model(path: str | Path, model_cls: Type[ModelT]) -> ModelT:
    def loader(resolved: Path) -> Dict[str, Any]:
        with resolved.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    payload = _load_raw(path, loader)
    return model_cls(**payload)


def read_yaml_config(path: str | Path) -> Dict[str, Any]:
    def loader(resolved: Path) -> Dict[str, Any]:
        with resolved.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    return _load_raw(path, loader)


def read_parquet_load_profile(path: str | Path, source: str = "fixture") -> schema.LoadProfile8760:
    def loader(resolved: Path) -> pd.DataFrame:
        return pd.read_parquet(resolved)

    frame = _load_raw(path, loader)
    if "load_kwh" not in frame.columns:
        raise ValueError("Parquet load profile must contain 'load_kwh' column")
    if "timestamp" in frame.columns:
        ts = pd.to_datetime(frame["timestamp"], utc=False)
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        time_index = ts.dt.tz_convert("UTC")
    else:
        time_index = defaults.default_time_index(defaults.DEFAULT_PRICE_YEAR, "UTC")
    return schema.LoadProfile8760(
        time_index=[ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts for ts in time_index],
        load_kwh=frame["load_kwh"].tolist(),
        source=source,
    )


def read_parquet_pv_profile(path: str | Path, source: str = "fixture") -> schema.PVProfile8760:
    def loader(resolved: Path) -> pd.DataFrame:
        return pd.read_parquet(resolved)

    frame = _load_raw(path, loader)
    if "production_kwh" not in frame.columns:
        raise ValueError("PV profile parquet must contain 'production_kwh'")
    if "timestamp" in frame.columns:
        ts = pd.to_datetime(frame["timestamp"], utc=False)
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        time_index = ts.dt.tz_convert("UTC")
    else:
        time_index = defaults.default_time_index(defaults.DEFAULT_PRICE_YEAR, "UTC")
    return schema.PVProfile8760(
        time_index=[ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts for ts in time_index],
        production_kwh=frame["production_kwh"].tolist(),
        source=source,
    )


def read_pipeline_spec(path: str | Path) -> PipelineSpecification:
    """Load and validate a pipeline specification from YAML, including metadata."""

    loader = PipelineSpecLoader()
    return loader.load(path)
