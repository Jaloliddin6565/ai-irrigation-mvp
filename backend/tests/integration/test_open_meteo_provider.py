"""Mocked tests for the live Open-Meteo weather provider. No real network
calls — respx intercepts httpx at the transport layer; DATA_MODE stays
fixture everywhere else in the suite.
"""

from datetime import date

import httpx
import pytest
import respx

from app.core.cache import TTLCache
from app.core.provider_errors import (
    InvalidDateRangeError,
    ProviderMalformedResponseError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.providers.weather.open_meteo import OpenMeteoProvider

ARCHIVE_URL = "https://archive.test/archive"
FORECAST_URL = "https://forecast.test/forecast"


def _provider(**overrides: object) -> OpenMeteoProvider:
    defaults: dict = dict(
        forecast_url=FORECAST_URL,
        archive_url=ARCHIVE_URL,
        timezone="Asia/Tashkent",
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )
    defaults.update(overrides)
    return OpenMeteoProvider(**defaults)


def _daily_payload(dates: list[str], et0: list, precip: list) -> dict:
    return {
        "daily": {
            "time": dates,
            "et0_fao_evapotranspiration": et0,
            "precipitation_sum": precip,
            "temperature_2m_max": [30.0] * len(dates),
            "temperature_2m_min": [15.0] * len(dates),
            "temperature_2m_mean": [22.0] * len(dates),
            "relative_humidity_2m_mean": [50.0] * len(dates),
            "wind_speed_10m_max": [2.0] * len(dates),
            "shortwave_radiation_sum": [20.0] * len(dates),
        }
    }


@respx.mock
def test_historical_only_range_returns_archive_days_with_full_probability() -> None:
    respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(
            200, json=_daily_payload(["2026-06-01", "2026-06-02"], [4.0, 4.5], [0.0, 2.0])
        )
    )
    series = _provider().get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 2), as_of=date(2026, 6, 2)
    )
    assert len(series.days) == 2
    assert series.days[0].et0_mm == 4.0
    assert series.days[0].is_forecast is False
    assert series.days[0].precipitation_probability_pct == 100.0
    assert series.provider == "open-meteo"
    assert series.coverage is not None
    assert series.coverage.completeness_status == "complete"


@respx.mock
def test_forecast_only_range_uses_real_precipitation_probability() -> None:
    payload = _daily_payload(["2026-06-03"], [4.2], [1.0])
    payload["daily"]["precipitation_probability_max"] = [30.0]
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=payload))
    series = _provider().get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 3), date(2026, 6, 3), as_of=date(2026, 6, 2)
    )
    assert len(series.days) == 1
    assert series.days[0].is_forecast is True
    assert series.days[0].precipitation_probability_pct == 30.0


@respx.mock
def test_split_range_queries_both_archive_and_forecast_endpoints() -> None:
    archive_route = respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=_daily_payload(["2026-06-01"], [4.0], [0.0]))
    )
    forecast_payload = _daily_payload(["2026-06-02"], [4.1], [0.0])
    forecast_payload["daily"]["precipitation_probability_max"] = [10.0]
    forecast_route = respx.get(FORECAST_URL).mock(
        return_value=httpx.Response(200, json=forecast_payload)
    )
    series = _provider().get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 2), as_of=date(2026, 6, 1)
    )
    assert archive_route.call_count == 1
    assert forecast_route.call_count == 1
    assert [d.date.isoformat() for d in series.days] == ["2026-06-01", "2026-06-02"]


@respx.mock
def test_missing_date_in_response_is_a_reported_gap_not_a_fabricated_zero() -> None:
    respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(
            200, json=_daily_payload(["2026-06-01", "2026-06-03"], [4.0, 4.2], [0.0, 0.0])
        )
    )
    series = _provider().get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 3), as_of=date(2026, 6, 3)
    )
    assert len(series.days) == 2
    assert series.coverage is not None
    assert series.coverage.missing_dates == [date(2026, 6, 2)]
    assert series.coverage.completeness_status == "partial"
    assert all(d.date != date(2026, 6, 2) for d in series.days)


@respx.mock
def test_null_value_row_is_dropped_not_zero_filled() -> None:
    payload = _daily_payload(["2026-06-01", "2026-06-02"], [4.0, None], [0.0, 0.0])
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=payload))
    series = _provider().get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 2), as_of=date(2026, 6, 2)
    )
    assert len(series.days) == 1
    assert series.days[0].date == date(2026, 6, 1)
    assert series.coverage is not None
    assert date(2026, 6, 2) in series.coverage.missing_dates


@respx.mock
def test_duplicate_date_keeps_only_the_first_occurrence() -> None:
    payload = _daily_payload(["2026-06-01", "2026-06-01"], [4.0, 9.9], [0.0, 0.0])
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=payload))
    series = _provider().get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
    )
    assert len(series.days) == 1
    assert series.days[0].et0_mm == 4.0


@respx.mock
def test_mismatched_array_lengths_raise_malformed_response_error() -> None:
    payload = _daily_payload(["2026-06-01", "2026-06-02"], [4.0], [0.0, 0.0])
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(ProviderMalformedResponseError):
        _provider().get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 1), date(2026, 6, 2), as_of=date(2026, 6, 2)
        )


@respx.mock
def test_missing_daily_block_raises_malformed_response_error() -> None:
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(ProviderMalformedResponseError):
        _provider().get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
        )


@respx.mock
def test_negative_et0_raises_malformed_response_error() -> None:
    payload = _daily_payload(["2026-06-01"], [-1.0], [0.0])
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(ProviderMalformedResponseError):
        _provider().get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
        )


@respx.mock
def test_negative_precipitation_raises_malformed_response_error() -> None:
    payload = _daily_payload(["2026-06-01"], [4.0], [-0.5])
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(ProviderMalformedResponseError):
        _provider().get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
        )


@respx.mock
def test_malformed_json_raises_malformed_response_error() -> None:
    respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(
            200, content=b"not json", headers={"content-type": "application/json"}
        )
    )
    with pytest.raises(ProviderMalformedResponseError):
        _provider().get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
        )


def test_end_before_start_raises_invalid_date_range_error() -> None:
    with pytest.raises(InvalidDateRangeError):
        _provider().get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 2), date(2026, 6, 1), as_of=date(2026, 6, 1)
        )


@respx.mock
def test_timeout_raises_provider_timeout_error() -> None:
    respx.get(ARCHIVE_URL).mock(side_effect=httpx.ConnectTimeout("boom"))
    with pytest.raises(ProviderTimeoutError):
        _provider().get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
        )


@respx.mock
def test_429_raises_rate_limit_error() -> None:
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(ProviderRateLimitError):
        _provider().get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
        )


@respx.mock
def test_5xx_raises_provider_server_error() -> None:
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderServerError):
        _provider().get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
        )


@respx.mock
def test_cache_hit_avoids_a_second_http_call() -> None:
    route = respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=_daily_payload(["2026-06-01"], [4.0], [0.0]))
    )
    cache: TTLCache = TTLCache()
    provider = _provider(cache=cache, cache_ttl_seconds=60)
    series1 = provider.get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
    )
    series2 = provider.get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
    )
    assert route.call_count == 1
    assert series1.cache_hit is False
    assert series2.cache_hit is True


@respx.mock
def test_distinct_coordinates_produce_distinct_cache_entries() -> None:
    route = respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=_daily_payload(["2026-06-01"], [4.0], [0.0]))
    )
    cache: TTLCache = TTLCache()
    provider = _provider(cache=cache, cache_ttl_seconds=60)
    provider.get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
    )
    provider.get_daily_series_for_range(
        50.0, 60.0, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
    )
    assert route.call_count == 2


@respx.mock
def test_distinct_date_ranges_produce_distinct_cache_entries() -> None:
    route = respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=_daily_payload(["2026-06-01"], [4.0], [0.0]))
    )
    cache: TTLCache = TTLCache()
    provider = _provider(cache=cache, cache_ttl_seconds=60)
    provider.get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
    )
    provider.get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 5), date(2026, 6, 5), as_of=date(2026, 6, 5)
    )
    assert route.call_count == 2


@respx.mock
def test_cache_expiry_triggers_a_fresh_fetch() -> None:
    route = respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=_daily_payload(["2026-06-01"], [4.0], [0.0]))
    )
    now = [0.0]
    cache: TTLCache = TTLCache(clock=lambda: now[0])
    provider = _provider(cache=cache, cache_ttl_seconds=10)
    provider.get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
    )
    now[0] = 11.0
    provider.get_daily_series_for_range(
        41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
    )
    assert route.call_count == 2


@respx.mock
def test_a_failed_request_is_never_cached() -> None:
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(500))
    cache: TTLCache = TTLCache()
    provider = _provider(cache=cache, cache_ttl_seconds=60, max_retries=0)
    with pytest.raises(ProviderServerError):
        provider.get_daily_series_for_range(
            41.3, 69.3, date(2026, 6, 1), date(2026, 6, 1), as_of=date(2026, 6, 1)
        )
    assert len(cache) == 0
