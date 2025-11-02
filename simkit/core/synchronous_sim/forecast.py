"""Mock forecast component used by the synchronous simulation module."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd

from ...config import schema


class MockForecastComponent:
    """Generates deterministic forecasts with optional noise injection."""

    def __init__(self, config: schema.MockForecastConfig, trajectory: schema.PriceTrajectory) -> None:
        self._config = config
        self._trajectory = trajectory
        self._rng = np.random.default_rng(config.seed)
        self._metadata = schema.MockForecastMetadata(
            currency=trajectory.currency,
            unit=trajectory.unit,
        )
        self._start_index_by_outer: Dict[int, int] = {}
        self._lookahead_samples = self._resolve_sample_count(config.lookahead)

    def _resolve_sample_count(self, span: schema.TimeSpan) -> int:
        frequency = self._trajectory.frequency
        if frequency == pd.Timedelta(0):
            return 1
        ratio = span.delta / frequency
        return max(1, int(math.ceil(float(ratio))))

    def initialize(self, time_grid: schema.SyncTimeGrid) -> None:
        # This is a kind of annoying mapping, but needed to allow for the PriceTrajectory not have identical time index as the SyncTimeGrid
        index_map: Dict[datetime, int] = {
            timestamp: idx for idx, timestamp in enumerate(self._trajectory.time_index)
        }
        for step in time_grid.outer_steps:
            if step.start not in index_map:
                raise ValueError(
                    f"Price trajectory missing timestamp for outer step {step.index}"
                )
            self._start_index_by_outer[step.index] = index_map[step.start]

    def step(self, outer_step: schema.SyncOuterStep) -> schema.MockForecastPoint:
        if outer_step.index not in self._start_index_by_outer:
            raise ValueError(
                f"MockForecastComponent not initialized for outer index {outer_step.index}"
            )
        start_idx = self._start_index_by_outer[outer_step.index]
        end_idx = start_idx + self._lookahead_samples

        timestamps = self._trajectory.time_index[start_idx:end_idx]
        values = self._trajectory.values[start_idx:end_idx]
        if len(timestamps) < self._lookahead_samples:
            raise ValueError("Price trajectory does not extend to the required lookahead horizon")

        noise = self._rng.normal(0.0, self._config.noise_std_dev, size=len(values))
        forecast_values = [float(v + n) for v, n in zip(values, noise)]

        return schema.MockForecastPoint(
            outer_index=outer_step.index,
            issued_at=outer_step.start,
            timestamps=tuple(timestamps),
            values=tuple(forecast_values),
            metadata=self._metadata,
        )

    def reset(self) -> None:
        """Reset the random generator to make the component deterministic again."""

        self._rng = np.random.default_rng(self._config.seed)
