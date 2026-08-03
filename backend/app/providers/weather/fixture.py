"""Deterministic fixture weather provider.

Ignores the requested coordinates and returns the same static demo season
from backend/fixtures/weather/sample_field.json every time — DEMO / FIXTURE
DATA, never presented as a live result. No randomness, no wall-clock
dependence.
"""

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.providers.weather.base import DailyWeather, WeatherSeries


class FixtureWeatherProvider:
    def __init__(self, fixtures_dir: Path) -> None:
        self._fixture_path = fixtures_dir / "weather" / "sample_field.json"

    @lru_cache(maxsize=1)  # noqa: B019 - single fixture file, process-lifetime cache is intentional
    def _load(self) -> WeatherSeries:
        with self._fixture_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return WeatherSeries(
            timezone=data["timezone"],
            days=[DailyWeather.model_validate(day) for day in data["days"]],
        )

    def get_daily_series(
        self, lat: float, lon: float, start_date: date, end_date: date
    ) -> WeatherSeries:
        series = self._load()
        filtered = [d for d in series.days if start_date <= d.date <= end_date]
        return WeatherSeries(timezone=series.timezone, days=filtered)
