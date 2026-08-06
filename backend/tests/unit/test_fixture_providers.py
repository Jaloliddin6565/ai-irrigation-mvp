from datetime import date, timedelta

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


def test_weather_fixture_anchored_range_covers_any_real_date_window() -> None:
    provider = FixtureWeatherProvider(FIXTURES_DIR)
    analysis_date = date(2026, 6, 1)
    start = analysis_date - timedelta(days=90)
    end = analysis_date + timedelta(days=3)

    series = provider.get_daily_series_for_range(0, 0, start, end, as_of=analysis_date)

    assert len(series.days) == (end - start).days + 1
    assert series.days[0].date == start
    assert series.days[-1].date == end
    assert all(not d.is_forecast for d in series.days if d.date <= analysis_date)
    assert all(d.is_forecast for d in series.days if d.date > analysis_date)


def test_weather_fixture_anchored_range_is_deterministic() -> None:
    provider = FixtureWeatherProvider(FIXTURES_DIR)
    analysis_date = date(2026, 6, 1)
    start = analysis_date - timedelta(days=10)
    end = analysis_date

    first = provider.get_daily_series_for_range(0, 0, start, end, as_of=analysis_date)
    second = provider.get_daily_series_for_range(0, 0, start, end, as_of=analysis_date)
    assert first == second


def test_satellite_fixture_anchored_range_covers_any_real_date_window() -> None:
    provider = FixtureSatelliteProvider(FIXTURES_DIR)
    analysis_date = date(2026, 6, 1)
    start = analysis_date - timedelta(days=90)

    series = provider.get_index_timeseries_for_range({}, start, analysis_date)

    assert len(series.observations) > 0
    assert all(start <= obs.acquisition_date <= analysis_date for obs in series.observations)
    # Still includes a deliberately low-quality observation, cycled through.
    assert min(obs.valid_pixel_ratio for obs in series.observations) < 0.5


def test_satellite_fixture_anchored_range_is_deterministic() -> None:
    provider = FixtureSatelliteProvider(FIXTURES_DIR)
    analysis_date = date(2026, 6, 1)
    start = analysis_date - timedelta(days=90)

    first = provider.get_index_timeseries_for_range({}, start, analysis_date)
    second = provider.get_index_timeseries_for_range({}, start, analysis_date)
    assert first == second
