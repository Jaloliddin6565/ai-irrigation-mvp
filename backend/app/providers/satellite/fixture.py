"""Deterministic fixture satellite provider.

Ignores the requested polygon and returns the same static demo dataset
under backend/fixtures/satellite/sample_field.json every time — this is
DEMO / FIXTURE DATA, never presented as a live result (see settings.data_mode
and the frontend data-mode badge). Identical calls always return identical
data: no randomness, no wall-clock dependence.
"""

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from app.providers.satellite.base import ParcelObservation, SatelliteTimeseries


class FixtureSatelliteProvider:
    def __init__(self, fixtures_dir: Path) -> None:
        self._fixture_path = fixtures_dir / "satellite" / "sample_field.json"

    @lru_cache(maxsize=1)  # noqa: B019 - single fixture file, process-lifetime cache is intentional
    def _load(self) -> list[ParcelObservation]:
        with self._fixture_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return [ParcelObservation.model_validate(obs) for obs in data["observations"]]

    def get_index_timeseries(
        self, polygon: dict, start_date: date, end_date: date
    ) -> SatelliteTimeseries:
        observations = [
            obs for obs in self._load() if start_date <= obs.acquisition_date <= end_date
        ]
        return SatelliteTimeseries(observations=observations)

    def get_latest_observation(self, polygon: dict, as_of: date) -> ParcelObservation | None:
        candidates = [obs for obs in self._load() if obs.acquisition_date <= as_of]
        if not candidates:
            return None
        return max(candidates, key=lambda obs: obs.acquisition_date)

    def get_index_timeseries_for_range(
        self, polygon: dict, start_date: date, end_date: date
    ) -> SatelliteTimeseries:
        """Like get_index_timeseries, but cycles the fixed demo observations
        (same acquisition spacing, same statistics incl. the deliberately
        low-quality one) to cover ANY requested [start_date, end_date]
        instead of only the fixture's own fixed 2024 window. Still fully
        deterministic and still DEMO/FIXTURE DATA — see
        FixtureWeatherProvider.get_daily_series_for_range for the same
        rationale.
        """
        base_observations = self._load()
        if not base_observations:
            return SatelliteTimeseries(observations=[])

        interval_days = (
            (base_observations[1].acquisition_date - base_observations[0].acquisition_date).days
            if len(base_observations) > 1
            else 7
        )
        interval_days = max(interval_days, 1)

        result: list[ParcelObservation] = []
        index = 0
        current = start_date
        while current <= end_date:
            source = base_observations[index % len(base_observations)]
            result.append(source.model_copy(update={"acquisition_date": current}))
            index += 1
            current += timedelta(days=interval_days)
        return SatelliteTimeseries(observations=result)
