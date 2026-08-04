"""End-to-end mocked tests proving DATA_MODE=live wiring: the full
POST /analyze pipeline running against OpenMeteoProvider +
CdseSentinelHubProvider with every external call intercepted by respx — no
real network access. These are the tests that prove "live mode never
silently falls back to fixture data" and "missing credentials fail
clearly" as actual system behaviour, not just unit-level claims.

DATA_MODE is restored to fixture (the suite default) after every test via
the `live_mode` fixture, and all provider-factory singletons are cleared so
no live-mode state leaks into later fixture-mode tests.
"""

from collections.abc import Generator
from datetime import date, timedelta

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.providers import factory as provider_factory
from app.settings import get_settings

TOKEN_URL = "https://identity.test/token"
CATALOG_URL = "https://sh.test/catalog/v1/search"
STATISTICS_URL = "https://sh.test/statistics/v1"
ARCHIVE_URL = "https://archive.test/archive"
FORECAST_URL = "https://forecast.test/forecast"

VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [69.2400, 41.3000],
            [69.2410, 41.3000],
            [69.2410, 41.3010],
            [69.2400, 41.3010],
            [69.2400, 41.3000],
        ]
    ],
}

FAKE_CLIENT_SECRET = "unit-test-cdse-secret-never-persisted"  # pragma: allowlist secret
FAKE_ACCESS_TOKEN = "unit-test-access-token-never-persisted"  # pragma: allowlist secret


@pytest.fixture
def live_mode(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("OPEN_METEO_ARCHIVE_URL", ARCHIVE_URL)
    monkeypatch.setenv("OPEN_METEO_FORECAST_URL", FORECAST_URL)
    monkeypatch.setenv("CDSE_TOKEN_URL", TOKEN_URL)
    monkeypatch.setenv("CDSE_CATALOG_URL", CATALOG_URL)
    monkeypatch.setenv("CDSE_STATISTICS_URL", STATISTICS_URL)
    monkeypatch.setenv("CDSE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("CDSE_CLIENT_SECRET", FAKE_CLIENT_SECRET)
    get_settings.cache_clear()
    provider_factory._weather_cache.cache_clear()
    provider_factory._satellite_cache.cache_clear()
    provider_factory._cdse_token_client.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()
        provider_factory._weather_cache.cache_clear()
        provider_factory._satellite_cache.cache_clear()
        provider_factory._cdse_token_client.cache_clear()


@pytest.fixture
def live_mode_no_credentials(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.delenv("CDSE_CLIENT_ID", raising=False)
    monkeypatch.delenv("CDSE_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    provider_factory._weather_cache.cache_clear()
    provider_factory._satellite_cache.cache_clear()
    provider_factory._cdse_token_client.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()
        provider_factory._weather_cache.cache_clear()
        provider_factory._satellite_cache.cache_clear()
        provider_factory._cdse_token_client.cache_clear()


def _weather_side_effect(request: httpx.Request) -> httpx.Response:
    params = dict(request.url.params)
    start = date.fromisoformat(params["start_date"])
    end = date.fromisoformat(params["end_date"])
    days: list[str] = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    n = len(days)
    payload = {
        "daily": {
            "time": days,
            "et0_fao_evapotranspiration": [4.0] * n,
            "precipitation_sum": [0.0] * n,
            "temperature_2m_max": [30.0] * n,
            "temperature_2m_min": [15.0] * n,
            "wind_speed_10m_max": [2.0] * n,
            "shortwave_radiation_sum": [20.0] * n,
        }
    }
    if "forecast" in str(request.url):
        payload["daily"]["precipitation_probability_max"] = [10.0] * n
    return httpx.Response(200, json=payload)


def _mock_weather() -> None:
    respx.get(ARCHIVE_URL).mock(side_effect=_weather_side_effect)
    respx.get(FORECAST_URL).mock(side_effect=_weather_side_effect)


def _mock_token() -> None:
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": FAKE_ACCESS_TOKEN, "expires_in": 3600}
        )
    )


def _feature(scene_id: str, dt: str, cloud_cover: float = 10.0) -> dict:
    return {
        "id": scene_id,
        "collection": "sentinel-2-l2a",
        "properties": {"datetime": dt, "eo:cloud_cover": cloud_cover},
    }


def _index_output(*, sample_count: int = 100, no_data_count: int = 10, base: float = 0.3) -> dict:
    return {
        "bands": {
            "B0": {
                "stats": {
                    "sampleCount": sample_count,
                    "noDataCount": no_data_count,
                    "mean": base,
                    "stDev": 0.05,
                    "min": base - 0.1,
                    "max": base + 0.1,
                    "percentiles": {"25.0": base - 0.05, "50.0": base, "75.0": base + 0.05},
                }
            }
        }
    }


def _stats_payload(interval_date: str, *, sample_count: int = 100, no_data_count: int = 10) -> dict:
    from app.providers.satellite.statistics import INDEX_NAMES

    return {
        "data": [
            {
                "interval": {
                    "from": f"{interval_date}T00:00:00Z",
                    "to": f"{interval_date}T23:59:59Z",
                },
                "outputs": {
                    idx: _index_output(
                        sample_count=sample_count, no_data_count=no_data_count, base=0.1 * (i + 1)
                    )
                    for i, idx in enumerate(INDEX_NAMES)
                },
            }
        ]
    }


def _mock_satellite_with_one_acquisition(
    acquisition_dt: str, *, sample_count=100, no_data_count=10
) -> None:
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S2A_TEST", acquisition_dt)], "links": []}
        )
    )
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_stats_payload(
                acquisition_dt.split("T")[0], sample_count=sample_count, no_data_count=no_data_count
            ),
        )
    )


def _mock_satellite_empty() -> None:
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(200, json={"features": [], "links": []})
    )


def _create_field(client: TestClient) -> int:
    farmer_payload = {
        "full_name": "Aliyev Vali",
        "phone": "+998901234567",
        "region": "Toshkent viloyati",
        "district": "Zangiota tumani",
    }
    farmer_id = client.post("/api/farmers", json=farmer_payload).json()["id"]
    field_payload = {
        "farmer_id": farmer_id,
        "name": "Shimoliy dala",
        "geojson_polygon": VALID_POLYGON,
        "crop_type": "cotton",
        "planting_date": "2026-04-01",
        "irrigation_method": "drip",
        "soil_texture": "loam",
    }
    return int(client.post("/api/fields", json=field_payload).json()["id"])


@respx.mock
def test_missing_cdse_credentials_fails_clearly_not_500_not_fixture_fallback(
    db_client: TestClient, live_mode_no_credentials: None
) -> None:
    field_id = _create_field(db_client)
    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "provider_configuration_error"
    assert "CDSE_CLIENT_ID" in body["message_en"]


@respx.mock
def test_successful_mocked_live_analysis_end_to_end(db_client: TestClient, live_mode: None) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )
    _mock_token()
    _mock_weather()
    _mock_satellite_with_one_acquisition("2026-05-30T07:15:00Z")

    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["data_mode"] == "live"
    assert body["weather_summary"]["provider"] == "open-meteo"
    assert body["weather_summary"]["source"] == "Open-Meteo (live)"
    assert body["satellite_summary"]["provider"] == "cdse-sentinel-hub"
    assert body["satellite_summary"]["source"] == "CDSE Sentinel Hub (live)"


@respx.mock
def test_real_acquisition_date_is_preserved_through_the_full_pipeline(
    db_client: TestClient, live_mode: None
) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )
    _mock_token()
    _mock_weather()
    _mock_satellite_with_one_acquisition("2026-05-30T07:15:00Z")

    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["satellite_summary"]["latest_observation_date"] == "2026-05-30"


@respx.mock
def test_no_satellite_acquisitions_still_allows_water_balance_via_weather_and_irrigation(
    db_client: TestClient, live_mode: None
) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )
    _mock_token()
    _mock_weather()
    _mock_satellite_empty()

    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["satellite_summary"]["valid_observations_used"] == 0
    assert body["satellite_summary"]["adjustment_applied"] is False
    assert body["water_balance_summary"]["depletion_mm"] is not None
    assert body["recommendation"]["status"] != "insufficient_data"


@respx.mock
def test_stale_satellite_observation_is_excluded_from_adjustment(
    db_client: TestClient, live_mode: None
) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )
    monkeypatch_env_max_age = "1"
    import os

    os.environ["MAX_SATELLITE_OBSERVATION_AGE_DAYS"] = monkeypatch_env_max_age
    get_settings.cache_clear()
    try:
        _mock_token()
        _mock_weather()
        # 60 days before analysis_date -> definitely stale under a 1-day cap.
        _mock_satellite_with_one_acquisition("2026-04-02T07:15:00Z")

        response = db_client.post(
            f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["satellite_summary"]["adjustment_applied"] is False
    finally:
        del os.environ["MAX_SATELLITE_OBSERVATION_AGE_DAYS"]
        get_settings.cache_clear()


@respx.mock
def test_low_valid_pixel_ratio_observation_is_excluded_from_adjustment(
    db_client: TestClient, live_mode: None
) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )
    _mock_token()
    _mock_weather()
    _mock_satellite_with_one_acquisition("2026-05-30T07:15:00Z", sample_count=10, no_data_count=90)

    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["satellite_summary"]["adjustment_applied"] is False


@respx.mock
def test_no_secret_or_token_appears_anywhere_in_the_api_response(
    db_client: TestClient, live_mode: None
) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )
    _mock_token()
    _mock_weather()
    _mock_satellite_with_one_acquisition("2026-05-30T07:15:00Z")

    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )

    assert response.status_code == 201
    raw_text = response.text
    assert FAKE_CLIENT_SECRET not in raw_text
    assert FAKE_ACCESS_TOKEN not in raw_text


@respx.mock
def test_multiple_live_analyses_remain_persisted_separately(
    db_client: TestClient, live_mode: None
) -> None:
    field_id = _create_field(db_client)
    db_client.post(
        f"/api/fields/{field_id}/irrigations",
        json={"occurred_at": "2026-05-28T08:00:00Z", "amount_mm": 20.0, "value_source": "measured"},
    )
    _mock_token()
    _mock_weather()
    _mock_satellite_with_one_acquisition("2026-05-30T07:15:00Z")

    first = db_client.post(f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"})
    second = db_client.post(f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-02"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    history = db_client.get(f"/api/fields/{field_id}/analyses")
    assert history.json()["total"] == 2


def test_fixture_mode_is_unaffected_by_live_mode_fixtures_existing(db_client: TestClient) -> None:
    # No live_mode fixture applied here -> DATA_MODE stays "fixture" (the
    # suite default from conftest/os.environ), proving the live-mode
    # fixtures above fully clean up after themselves between tests.
    field_id = _create_field(db_client)
    response = db_client.post(
        f"/api/fields/{field_id}/analyze", json={"analysis_date": "2026-06-01"}
    )
    assert response.status_code == 201
    assert response.json()["data_mode"] == "fixture"
