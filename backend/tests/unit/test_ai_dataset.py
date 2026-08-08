"""Mocked tests for app/ai/dataset.py. No real network calls — respx
intercepts httpx at the transport layer, same pattern as
tests/integration/test_open_meteo_provider.py.
"""

from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from app.ai.dataset import CollectionFailure, fetch_location
from app.ai.features import RawDailyRecord
from app.ai.locations import BootstrapLocation
from app.core.http_client import RetryingHttpClient

ARCHIVE_URL = "https://archive.test/archive"
START = date(2025, 1, 1)
END = date(2025, 2, 4)  # 35 days

_LOCATION = BootstrapLocation(
    id="test_loc", region_uz="Test", label_uz="Test", latitude=41.0, longitude=69.0, split="train"
)


def _payload() -> dict:
    n_days = (END - START).days + 1
    dates = [(START + timedelta(days=i)).isoformat() for i in range(n_days)]
    hourly_times = [f"{d}T{h:02d}:00" for d in dates for h in range(24)]
    return {
        "daily": {
            "time": dates,
            "et0_fao_evapotranspiration": [5.0] * n_days,
            "precipitation_sum": [0.0] * n_days,
            "temperature_2m_max": [25.0] * n_days,
            "temperature_2m_min": [10.0] * n_days,
            "temperature_2m_mean": [17.5] * n_days,
            "relative_humidity_2m_mean": [40.0] * n_days,
            "wind_speed_10m_max": [2.0] * n_days,
            "shortwave_radiation_sum": [20.0] * n_days,
        },
        "hourly": {
            "time": hourly_times,
            "soil_moisture_7_to_28cm": [0.2] * len(hourly_times),
            "soil_moisture_28_to_100cm": [0.3] * len(hourly_times),
        },
    }


def _client() -> RetryingHttpClient:
    return RetryingHttpClient(
        provider="test",
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )


async def _fetch(client: RetryingHttpClient, cache_dir: Path) -> list[RawDailyRecord]:
    return await fetch_location(client, ARCHIVE_URL, _LOCATION, START, END, cache_dir=cache_dir)


@respx.mock
async def test_fetch_location_parses_daily_and_hourly_into_records(tmp_path: Path) -> None:
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=_payload()))

    async with _client() as client:
        records = await _fetch(client, tmp_path)

    assert len(records) == 35
    assert records[0].date == START
    assert records[0].location_id == "test_loc"
    assert records[0].et0_mm == 5.0
    # depth-weighted blend of 0.2 and 0.3 with weights 19/72, 53/72
    expected_target = (19.0 / 72.0) * 0.2 + (53.0 / 72.0) * 0.3
    assert records[0].root_zone_soil_moisture_proxy_m3m3 == pytest.approx(expected_target)


@respx.mock
async def test_fetch_location_uses_cache_on_second_call(tmp_path: Path) -> None:
    route = respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json=_payload()))

    async with _client() as client:
        first = await _fetch(client, tmp_path)
        second = await _fetch(client, tmp_path)

    assert route.call_count == 1
    assert first == second


@respx.mock
async def test_fetch_location_raises_collection_failure_on_http_error(tmp_path: Path) -> None:
    # A non-retryable status (404): RetryingHttpClient returns it as-is rather
    # than raising its own ProviderError, so this exercises dataset.py's own
    # status-code check.
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(404, text="not found"))

    async with _client() as client:
        with pytest.raises(CollectionFailure):
            await _fetch(client, tmp_path)


@respx.mock
async def test_fetch_location_raises_collection_failure_on_malformed_response(
    tmp_path: Path,
) -> None:
    respx.get(ARCHIVE_URL).mock(return_value=httpx.Response(200, json={"not_daily": True}))

    async with _client() as client:
        with pytest.raises(CollectionFailure, match="daily"):
            await _fetch(client, tmp_path)
