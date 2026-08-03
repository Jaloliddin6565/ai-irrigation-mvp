from datetime import date

from app.providers.satellite.fixture import FixtureSatelliteProvider
from app.providers.weather.fixture import FixtureWeatherProvider
from app.settings import FIXTURES_DIR

WIDE_RANGE = (date(2024, 1, 1), date(2024, 12, 31))


def test_satellite_fixture_is_deterministic() -> None:
    provider = FixtureSatelliteProvider(FIXTURES_DIR)
    first = provider.get_index_timeseries({}, *WIDE_RANGE)
    second = provider.get_index_timeseries({}, *WIDE_RANGE)

    assert first == second
    assert len(first.observations) == 7


def test_satellite_fixture_includes_a_low_quality_observation() -> None:
    provider = FixtureSatelliteProvider(FIXTURES_DIR)
    series = provider.get_index_timeseries({}, *WIDE_RANGE)

    ratios = [obs.valid_pixel_ratio for obs in series.observations]
    assert min(ratios) < 0.5, "fixture must include a cloudy/low-quality observation"


def test_satellite_fixture_latest_observation_respects_as_of_date() -> None:
    provider = FixtureSatelliteProvider(FIXTURES_DIR)
    latest = provider.get_latest_observation({}, as_of=date(2024, 4, 20))

    assert latest is not None
    assert latest.acquisition_date <= date(2024, 4, 20)


def test_weather_fixture_is_deterministic() -> None:
    provider = FixtureWeatherProvider(FIXTURES_DIR)
    first = provider.get_daily_series(0, 0, *WIDE_RANGE)
    second = provider.get_daily_series(0, 0, *WIDE_RANGE)

    assert first == second
    assert len(first.days) == 47
    assert any(day.is_forecast for day in first.days)
    assert any(not day.is_forecast for day in first.days)
    assert first.timezone == "Asia/Tashkent"
