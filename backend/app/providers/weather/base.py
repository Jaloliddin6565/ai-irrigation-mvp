"""WeatherProvider interface. All dates/times are Asia/Tashkent."""

from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel, Field


class DailyWeather(BaseModel):
    date: date
    is_forecast: bool
    et0_mm: float
    precipitation_mm: float
    precipitation_probability_pct: float
    temperature_max_c: float
    temperature_min_c: float
    wind_speed_ms: float
    shortwave_radiation_mj_m2: float


class WeatherCoverage(BaseModel):
    """Describes how completely a WeatherSeries covers the range that was
    requested. A day absent from `WeatherSeries.days` is a real, reported
    gap — never silently converted to a zero ET0/precipitation/temperature
    value. See CLAUDE.md rule 5 and docs/methodology.md "Weather gap
    handling"."""

    requested_start_date: date
    requested_end_date: date
    received_start_date: date | None = None
    received_end_date: date | None = None
    missing_dates: list[date] = Field(default_factory=list)
    coverage_ratio: float = 1.0
    completeness_status: str = "complete"  # "complete" | "partial" | "insufficient"


class WeatherSeries(BaseModel):
    timezone: str
    days: list[DailyWeather]
    provider: str = "fixture"
    source: str = "DEMO / FIXTURE DATA"
    retrieved_at: datetime | None = None
    coverage: WeatherCoverage | None = None
    cache_hit: bool = False


class WeatherProvider(Protocol):
    def get_daily_series(
        self, lat: float, lon: float, start_date: date, end_date: date
    ) -> WeatherSeries:
        """Return history + forecast days overlapping [start_date, end_date]."""
        ...

    def get_daily_series_for_range(
        self, lat: float, lon: float, start_date: date, end_date: date, as_of: date
    ) -> WeatherSeries:
        """Return a daily series covering [start_date, end_date], with
        `is_forecast` computed relative to `as_of`.

        Fixture implementations cycle a fixed deterministic demo dataset to
        cover any requested window. Live implementations fetch the real
        historical/forecast data for exactly that window and never fall
        back to fixture values — a day this provider could not obtain is
        simply absent from `days` and reflected in `coverage`, not
        fabricated as zero.
        """
        ...
