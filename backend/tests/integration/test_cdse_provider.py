"""Mocked tests for the assembled CdseSentinelHubProvider — Catalog +
Statistical API + quality classification behind the SatelliteProvider
interface. No real network calls.
"""

from datetime import date

import httpx
import respx

from app.core.cache import TTLCache
from app.providers.satellite.catalog import CdseCatalogClient
from app.providers.satellite.cdse import CdseSentinelHubProvider
from app.providers.satellite.cdse_auth import CdseTokenClient
from app.providers.satellite.statistics import INDEX_NAMES, CdseStatisticsClient

TOKEN_URL = "https://identity.test/token"
CATALOG_URL = "https://sh.test/catalog/v1/search"
STATISTICS_URL = "https://sh.test/statistics/v1"

VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[69.0, 41.0], [69.1, 41.0], [69.1, 41.1], [69.0, 41.1], [69.0, 41.0]]],
}


def _mock_token() -> None:
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    )


def _feature(scene_id: str, dt: str, cloud_cover: float) -> dict:
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


def _provider(**overrides: object) -> CdseSentinelHubProvider:
    token_client = CdseTokenClient(
        client_id="id",
        client_secret="secret",  # pragma: allowlist secret
        token_url=TOKEN_URL,
        expiry_margin_seconds=10,
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )
    catalog_client = CdseCatalogClient(
        catalog_url=CATALOG_URL,
        token_client=token_client,
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )
    statistics_client = CdseStatisticsClient(
        statistics_url=STATISTICS_URL,
        token_client=token_client,
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )
    defaults: dict = dict(
        catalog_client=catalog_client,
        statistics_client=statistics_client,
        max_cloud_cover_pct=80.0,
        min_valid_pixel_ratio=0.6,
        max_observation_age_days=None,
    )
    defaults.update(overrides)
    return CdseSentinelHubProvider(**defaults)


@respx.mock
def test_end_to_end_usable_observation() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S1", "2026-06-01T07:00:00Z", 10.0)], "links": []}
        )
    )
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(200, json=_stats_payload("2026-06-01"))
    )
    series = _provider().get_index_timeseries_for_range(
        VALID_POLYGON, date(2026, 5, 1), date(2026, 6, 1)
    )
    assert len(series.observations) == 1
    obs = series.observations[0]
    assert obs.quality_status == "usable"
    assert obs.scene_id == "S1"
    assert obs.valid_pixel_ratio == 100 / (100 + 10)
    assert series.provider == "cdse-sentinel-hub"
    assert series.rejected_acquisitions == []


@respx.mock
def test_no_catalog_acquisitions_returns_empty_series_not_an_error() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(200, json={"features": [], "links": []})
    )
    series = _provider().get_index_timeseries_for_range(
        VALID_POLYGON, date(2026, 5, 1), date(2026, 6, 1)
    )
    assert series.observations == []


@respx.mock
def test_low_valid_pixel_ratio_observation_is_tagged_and_excluded_from_usable() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S1", "2026-06-01T07:00:00Z", 10.0)], "links": []}
        )
    )
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(
            200, json=_stats_payload("2026-06-01", sample_count=20, no_data_count=80)
        )
    )
    series = _provider(min_valid_pixel_ratio=0.6).get_index_timeseries_for_range(
        VALID_POLYGON, date(2026, 5, 1), date(2026, 6, 1)
    )
    assert len(series.observations) == 1
    assert series.observations[0].quality_status == "low_valid_pixel_ratio"


@respx.mock
def test_stale_observation_is_tagged_stale() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S1", "2026-05-01T07:00:00Z", 10.0)], "links": []}
        )
    )
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(200, json=_stats_payload("2026-05-01"))
    )
    series = _provider(max_observation_age_days=10).get_index_timeseries_for_range(
        VALID_POLYGON, date(2026, 5, 1), date(2026, 6, 1)
    )
    assert len(series.observations) == 1
    assert series.observations[0].quality_status == "stale"


@respx.mock
def test_acquisition_with_no_matching_statistics_interval_is_rejected() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S1", "2026-06-01T07:00:00Z", 10.0)], "links": []}
        )
    )
    # Statistics for a different date than the acquisition -> no match.
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(200, json=_stats_payload("2026-06-02"))
    )
    series = _provider().get_index_timeseries_for_range(
        VALID_POLYGON, date(2026, 5, 1), date(2026, 6, 1)
    )
    assert series.observations == []
    assert len(series.rejected_acquisitions) == 1


@respx.mock
def test_cloud_cover_rejected_acquisitions_are_reported() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S1", "2026-06-01T07:00:00Z", 99.0)], "links": []}
        )
    )
    series = _provider(max_cloud_cover_pct=80.0).get_index_timeseries_for_range(
        VALID_POLYGON, date(2026, 5, 1), date(2026, 6, 1)
    )
    assert series.observations == []
    assert len(series.rejected_acquisitions) == 1
    assert "cloud_cover" in series.rejected_acquisitions[0].reason


@respx.mock
def test_get_latest_observation_returns_the_most_recent_usable_one() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    _feature("S1", "2026-05-20T07:00:00Z", 10.0),
                    _feature("S2", "2026-06-01T07:00:00Z", 10.0),
                ],
                "links": [],
            },
        )
    )
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    _stats_payload("2026-05-20")["data"][0],
                    _stats_payload("2026-06-01")["data"][0],
                ]
            },
        )
    )
    latest = _provider().get_latest_observation(VALID_POLYGON, as_of=date(2026, 6, 1))
    assert latest is not None
    assert latest.acquisition_date == date(2026, 6, 1)


@respx.mock
def test_cache_hit_avoids_a_second_catalog_call() -> None:
    catalog_route = respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S1", "2026-06-01T07:00:00Z", 10.0)], "links": []}
        )
    )
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(200, json=_stats_payload("2026-06-01"))
    )
    _mock_token()
    cache: TTLCache = TTLCache()
    provider = _provider(cache=cache, cache_ttl_seconds=60)
    series1 = provider.get_index_timeseries_for_range(
        VALID_POLYGON, date(2026, 5, 1), date(2026, 6, 1)
    )
    series2 = provider.get_index_timeseries_for_range(
        VALID_POLYGON, date(2026, 5, 1), date(2026, 6, 1)
    )
    assert catalog_route.call_count == 1
    assert series1.cache_hit is False
    assert series2.cache_hit is True
