"""Deterministic fixture weather provider.

Ignores the requested coordinates and returns the same static demo season
from backend/fixtures/weather/sample_field.json every time — DEMO / FIXTURE
DATA, never presented as a live result. No randomness, no wall-clock
dependence.
"""

import json
from datetime import date, timedelta
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

    def get_daily_series_for_range(
        self, lat: float, lon: float, start_date: date, end_date: date, as_of: date
    ) -> WeatherSeries:
        """Like get_daily_series, but cycles the fixed demo season to cover
        ANY requested [start_date, end_date] instead of only the fixture's
        own fixed 2024 calendar window.

        This is what makes fixture mode usable for an analysis at a real
        planting_date/analysis_date rather than only ones that happen to
        fall inside the static file's date range. Still fully deterministic
        (same request -> same output) and still DEMO/FIXTURE DATA — only
        the calendar labels are remapped; the underlying values are the
        same fixed, non-random season. is_forecast is recomputed relative
        to `as_of`, not the fixture file's own historical/forecast split.
        """
        series = self._load()
        pattern = series.days
        if not pattern:
            return WeatherSeries(timezone=series.timezone, days=[])

        total_days = (end_date - start_date).days + 1
        result_days = []
        for i in range(total_days):
            source = pattern[i % len(pattern)]
            d = start_date + timedelta(days=i)
            result_days.append(
                DailyWeather(
                    date=d,
                    is_forecast=d > as_of,
                    et0_mm=source.et0_mm,
                    precipitation_mm=source.precipitation_mm,
                    precipitation_probability_pct=source.precipitation_probability_pct,
                    temperature_max_c=source.temperature_max_c,
                    temperature_min_c=source.temperature_min_c,
                    temperature_mean_c=source.temperature_mean_c,
                    relative_humidity_mean_pct=source.relative_humidity_mean_pct,
                    wind_speed_ms=source.wind_speed_ms,
                    shortwave_radiation_mj_m2=source.shortwave_radiation_mj_m2,
                )
            )
        return WeatherSeries(timezone=series.timezone, days=result_days)
