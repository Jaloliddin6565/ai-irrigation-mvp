"""Mocked tests for the CDSE Catalog API client. No real network calls —
respx intercepts httpx at the transport layer.
"""

import json as _json
from datetime import date

import httpx
import pytest
import respx

from app.core.provider_errors import (
    ProviderMalformedResponseError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    UnsupportedGeometryError,
)
from app.providers.satellite.catalog import CdseCatalogClient
from app.providers.satellite.cdse_auth import CdseTokenClient

TOKEN_URL = "https://identity.test/token"
CATALOG_URL = "https://sh.test/catalog/v1/search"

VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[69.0, 41.0], [69.1, 41.0], [69.1, 41.1], [69.0, 41.1], [69.0, 41.0]]],
}


def _token_client() -> CdseTokenClient:
    return CdseTokenClient(
        client_id="id",
        client_secret="secret",  # pragma: allowlist secret
        token_url=TOKEN_URL,
        expiry_margin_seconds=10,
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )


def _catalog_client(**overrides: object) -> CdseCatalogClient:
    defaults: dict = dict(
        catalog_url=CATALOG_URL,
        token_client=_token_client(),
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )
    defaults.update(overrides)
    return CdseCatalogClient(**defaults)


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


@respx.mock
async def test_successful_search_returns_accepted_acquisitions() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S1", "2026-06-01T07:00:00Z", 10.0)], "links": []}
        )
    )
    result = await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 1),
        max_cloud_cover_pct=80.0,
    )
    assert len(result.accepted) == 1
    assert result.accepted[0].scene_id == "S1"
    assert result.rejected == []


@respx.mock
async def test_no_acquisitions_returns_empty_accepted_list() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(200, json={"features": [], "links": []})
    )
    result = await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 1),
        max_cloud_cover_pct=80.0,
    )
    assert result.accepted == []


@respx.mock
async def test_real_acquisition_datetime_is_preserved_exactly() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S1", "2026-06-15T08:23:45Z", 5.0)], "links": []}
        )
    )
    result = await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 30),
        max_cloud_cover_pct=80.0,
    )
    assert result.accepted[0].acquisition_date == date(2026, 6, 15)
    assert result.accepted[0].acquisition_datetime.hour == 8
    assert result.accepted[0].acquisition_datetime.minute == 23


@respx.mock
async def test_cloud_cover_over_threshold_is_rejected_with_a_reason() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature("S1", "2026-06-01T07:00:00Z", 95.0)], "links": []}
        )
    )
    result = await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 1),
        max_cloud_cover_pct=80.0,
    )
    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "cloud_cover" in result.rejected[0].reason


@respx.mock
async def test_request_body_uses_the_complete_field_polygon() -> None:
    _mock_token()
    route = respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(200, json={"features": [], "links": []})
    )
    await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 1),
        max_cloud_cover_pct=80.0,
    )
    sent_body = _json.loads(route.calls[0].request.content)
    assert sent_body["intersects"] == VALID_POLYGON


async def test_point_geometry_raises_unsupported_geometry_error() -> None:
    with pytest.raises(UnsupportedGeometryError):
        await _catalog_client().search(
            {"type": "Point", "coordinates": [69.0, 41.0]},
            start_date=date(2026, 5, 1),
            end_date=date(2026, 6, 1),
            max_cloud_cover_pct=80.0,
        )


@respx.mock
async def test_response_missing_features_array_raises_malformed_response_error() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(return_value=httpx.Response(200, json={"links": []}))
    with pytest.raises(ProviderMalformedResponseError):
        await _catalog_client().search(
            VALID_POLYGON,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 6, 1),
            max_cloud_cover_pct=80.0,
        )


@respx.mock
async def test_duplicate_scene_id_is_deduplicated() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    _feature("S1", "2026-06-01T07:00:00Z", 10.0),
                    _feature("S1", "2026-06-01T07:00:00Z", 10.0),
                ],
                "links": [],
            },
        )
    )
    result = await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 1),
        max_cloud_cover_pct=80.0,
    )
    assert len(result.accepted) == 1


@respx.mock
async def test_results_are_sorted_chronologically() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    _feature("S2", "2026-06-10T07:00:00Z", 10.0),
                    _feature("S1", "2026-06-01T07:00:00Z", 10.0),
                ],
                "links": [],
            },
        )
    )
    result = await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 30),
        max_cloud_cover_pct=80.0,
    )
    assert [a.scene_id for a in result.accepted] == ["S1", "S2"]


@respx.mock
async def test_pagination_follows_the_next_link() -> None:
    # The real CDSE Catalog API's "next" link (verified live during
    # Phase 4.5) points back at the *same* URL and carries an opaque
    # cursor fragment in link.body that must be merged into the original
    # request body — it is not a distinctly-queried follow-up URL. This
    # mock reproduces that exact, sanitized shape (real example observed:
    # {"rel": "next", "href": "<same url>", "method": "POST",
    # "body": {"next": "2"}, "merge": true}).
    _mock_token()
    route = respx.post(CATALOG_URL)
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "features": [_feature("S1", "2026-06-01T07:00:00Z", 10.0)],
                "links": [
                    {
                        "href": CATALOG_URL,
                        "rel": "next",
                        "method": "POST",
                        "body": {"next": "2"},
                        "merge": True,
                    }
                ],
                "context": {"next": "2", "limit": 1, "returned": 1},
            },
        ),
        httpx.Response(
            200, json={"features": [_feature("S2", "2026-06-02T07:00:00Z", 10.0)], "links": []}
        ),
    ]
    result = await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 30),
        max_cloud_cover_pct=80.0,
    )
    assert {a.scene_id for a in result.accepted} == {"S1", "S2"}
    assert route.call_count == 2


@respx.mock
async def test_pagination_merges_the_cursor_into_the_original_request_body() -> None:
    _mock_token()
    route = respx.post(CATALOG_URL)
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "features": [_feature("S1", "2026-06-01T07:00:00Z", 10.0)],
                "links": [
                    {
                        "href": CATALOG_URL,
                        "rel": "next",
                        "method": "POST",
                        "body": {"next": "2"},
                        "merge": True,
                    }
                ],
            },
        ),
        httpx.Response(200, json={"features": [], "links": []}),
    ]
    await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 30),
        max_cloud_cover_pct=80.0,
    )
    second_request_body = _json.loads(route.calls[1].request.content)
    # The cursor is merged in ...
    assert second_request_body["next"] == "2"
    # ... alongside the *original* search parameters, not replacing them.
    assert second_request_body["intersects"] == VALID_POLYGON
    assert second_request_body["collections"] == ["sentinel-2-l2a"]


@respx.mock
async def test_timeout_propagates_as_provider_timeout_error() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(side_effect=httpx.ConnectTimeout("boom"))
    with pytest.raises(ProviderTimeoutError):
        await _catalog_client().search(
            VALID_POLYGON,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 6, 1),
            max_cloud_cover_pct=80.0,
        )


@respx.mock
async def test_401_on_search_triggers_token_refresh_and_one_retry() -> None:
    token_route = respx.post(TOKEN_URL)
    token_route.side_effect = [
        httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600}),
        httpx.Response(200, json={"access_token": "tok-2", "expires_in": 3600}),
    ]
    catalog_route = respx.post(CATALOG_URL)
    catalog_route.side_effect = [
        httpx.Response(401),
        httpx.Response(200, json={"features": [], "links": []}),
    ]
    result = await _catalog_client().search(
        VALID_POLYGON,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 1),
        max_cloud_cover_pct=80.0,
    )
    assert result.accepted == []
    assert token_route.call_count == 2


@respx.mock
async def test_429_propagates_as_rate_limit_error() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(ProviderRateLimitError):
        await _catalog_client().search(
            VALID_POLYGON,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 6, 1),
            max_cloud_cover_pct=80.0,
        )


@respx.mock
async def test_5xx_propagates_as_provider_server_error() -> None:
    _mock_token()
    respx.post(CATALOG_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderServerError):
        await _catalog_client().search(
            VALID_POLYGON,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 6, 1),
            max_cloud_cover_pct=80.0,
        )
