"""WeatherProvider interface. All dates/times are Asia/Tashkent."""

from datetime import date
from typing import Protocol

from pydantic import BaseModel


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


class WeatherSeries(BaseModel):
    timezone: str
    days: list[DailyWeather]


class WeatherProvider(Protocol):
    def get_daily_series(
        self, lat: float, lon: float, start_date: date, end_date: date
    ) -> WeatherSeries:
        """Return history + forecast days overlapping [start_date, end_date]."""
        ...
