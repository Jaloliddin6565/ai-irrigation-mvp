"""Mocked tests for the CDSE Statistical API client. No real network calls —
respx intercepts httpx at the transport layer.
"""

import math
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
from app.providers.satellite.cdse_auth import CdseTokenClient
from app.providers.satellite.scl import EXCLUDED_SCL_CLASSES
from app.providers.satellite.statistics import INDEX_NAMES, CdseStatisticsClient, build_evalscript

TOKEN_URL = "https://identity.test/token"
STATISTICS_URL = "https://sh.test/statistics/v1"

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


def _statistics_client(**overrides: object) -> CdseStatisticsClient:
    defaults: dict = dict(
        statistics_url=STATISTICS_URL,
        token_client=_token_client(),
        timeout_seconds=5.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
    )
    defaults.update(overrides)
    return CdseStatisticsClient(**defaults)


def _mock_token() -> None:
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    )


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
                    "percentiles": {
                        "25.0": base - 0.05,
                        "50.0": base,
                        "75.0": base + 0.05,
                    },
                }
            }
        }
    }


def _full_payload(
    interval_from: str = "2026-06-01T00:00:00Z",
    interval_to: str = "2026-06-01T23:59:59Z",
    *,
    sample_count: int = 100,
    no_data_count: int = 10,
) -> dict:
    return {
        "data": [
            {
                "interval": {"from": interval_from, "to": interval_to},
                "outputs": {
                    idx: _index_output(
                        sample_count=sample_count, no_data_count=no_data_count, base=0.1 * (i + 1)
                    )
                    for i, idx in enumerate(INDEX_NAMES)
                },
            }
        ]
    }


@respx.mock
async def test_valid_parcel_statistics_parses_all_six_indices() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(return_value=httpx.Response(200, json=_full_payload()))
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
    )
    assert len(results) == 1
    assert set(results[0].index_stats.keys()) == set(INDEX_NAMES)


@respx.mock
async def test_percentiles_mean_and_std_are_parsed_correctly() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(return_value=httpx.Response(200, json=_full_payload()))
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
    )
    ndvi = results[0].index_stats["ndvi"]
    assert ndvi["p50"] == pytest.approx(0.1)
    assert ndvi["p25"] == pytest.approx(0.05)
    assert ndvi["p75"] == pytest.approx(0.15)
    assert ndvi["mean"] == pytest.approx(0.1)
    assert ndvi["std"] == pytest.approx(0.05)


@respx.mock
async def test_valid_and_invalid_pixel_counts_are_parsed() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(200, json=_full_payload(sample_count=80, no_data_count=20))
    )
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
    )
    assert results[0].valid_pixel_count == 80
    assert results[0].invalid_pixel_count == 20


@respx.mock
async def test_actual_interval_dates_are_preserved() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(
            200, json=_full_payload("2026-06-05T00:00:00Z", "2026-06-05T23:59:59Z")
        )
    )
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 10)
    )
    assert results[0].interval_start == date(2026, 6, 5)
    assert results[0].interval_end == date(2026, 6, 5)


@respx.mock
async def test_zero_sample_count_interval_is_dropped() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(200, json=_full_payload(sample_count=0, no_data_count=100))
    )
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
    )
    assert results == []


@respx.mock
async def test_missing_interval_entry_is_skipped_not_crashed() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(200, json={"data": [{"outputs": {}}]})
    )
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
    )
    assert results == []


@respx.mock
async def test_malformed_interval_entry_type_is_skipped() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(return_value=httpx.Response(200, json={"data": ["not-a-dict"]}))
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
    )
    assert results == []


@respx.mock
async def test_non_finite_stat_value_causes_the_interval_to_be_dropped() -> None:
    import json as _json

    _mock_token()
    payload = _full_payload()
    payload["data"][0]["outputs"]["ndvi"]["bands"]["B0"]["stats"]["mean"] = math.nan
    # httpx's own json= encoding rejects NaN outright (allow_nan=False); a
    # real provider bug could still produce this over the wire, so build the
    # raw body ourselves (stdlib json.dumps allows NaN by default) to prove
    # our own parser rejects it rather than crashing.
    body = _json.dumps(payload).encode()
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(200, content=body, headers={"content-type": "application/json"})
    )
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
    )
    assert results == []


@respx.mock
async def test_missing_data_array_raises_malformed_response_error() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(ProviderMalformedResponseError):
        await _statistics_client().get_parcel_statistics(
            VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
        )


@respx.mock
async def test_malformed_json_raises_malformed_response_error() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(
            200, content=b"not json", headers={"content-type": "application/json"}
        )
    )
    with pytest.raises(ProviderMalformedResponseError):
        await _statistics_client().get_parcel_statistics(
            VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
        )


async def test_point_geometry_raises_unsupported_geometry_error() -> None:
    with pytest.raises(UnsupportedGeometryError):
        await _statistics_client().get_parcel_statistics(
            {"type": "Point", "coordinates": [69.0, 41.0]},
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 1),
        )


@respx.mock
async def test_request_body_uses_the_complete_field_polygon() -> None:
    import json as _json

    _mock_token()
    route = respx.post(STATISTICS_URL).mock(return_value=httpx.Response(200, json=_full_payload()))
    await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
    )
    sent_body = _json.loads(route.calls[0].request.content)
    assert sent_body["input"]["bounds"]["geometry"] == VALID_POLYGON


@respx.mock
async def test_timeout_propagates_as_provider_timeout_error() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(side_effect=httpx.ConnectTimeout("boom"))
    with pytest.raises(ProviderTimeoutError):
        await _statistics_client().get_parcel_statistics(
            VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
        )


@respx.mock
async def test_401_triggers_token_refresh_and_one_retry() -> None:
    token_route = respx.post(TOKEN_URL)
    token_route.side_effect = [
        httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600}),
        httpx.Response(200, json={"access_token": "tok-2", "expires_in": 3600}),
    ]
    stats_route = respx.post(STATISTICS_URL)
    stats_route.side_effect = [httpx.Response(401), httpx.Response(200, json=_full_payload())]
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
    )
    assert len(results) == 1
    assert token_route.call_count == 2


@respx.mock
async def test_429_propagates_as_rate_limit_error() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(ProviderRateLimitError):
        await _statistics_client().get_parcel_statistics(
            VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
        )


@respx.mock
async def test_5xx_propagates_as_provider_server_error() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderServerError):
        await _statistics_client().get_parcel_statistics(
            VALID_POLYGON, start_date=date(2026, 6, 1), end_date=date(2026, 6, 1)
        )


def test_evalscript_contains_the_scl_exclusion_list() -> None:
    script = build_evalscript()
    for scl_class in EXCLUDED_SCL_CLASSES:
        assert str(int(scl_class)) in script


def test_evalscript_declares_all_six_index_outputs_plus_datamask() -> None:
    script = build_evalscript()
    for index in INDEX_NAMES:
        assert f'"{index}"' in script
    assert '"dataMask"' in script


def test_evalscript_requests_plain_dn_bands_not_per_band_units() -> None:
    # Regression for a real 400 ("Script must return an array") discovered
    # live during Phase 4.5: the Statistical API rejects a per-band
    # object-array `bands: [{name, units}, ...]` input specification (it
    # was also independently confirmed that requesting SCL with
    # units: "REFLECTANCE" is rejected outright: "Invalid script! Band
    # 'SCL' ... requested in unsupported units 'REFLECTANCE'"). Bands must
    # be requested as plain digital-number (DN) band names with no `units`
    # field, and reflectance is computed in-script.
    script = build_evalscript()
    assert '"units"' not in script
    assert '"REFLECTANCE"' not in script  # as a units value; REFLECTANCE_SCALE (a plain
    # in-script constant name) is fine and expected — see the scaling test below.
    assert 'bands: ["B03", "B04", "B05", "B08", "B11", "B12", "SCL", "dataMask"]' in script


# Sanitized regression fixture: structurally identical to a real CDSE
# Statistical API response observed during the Phase 4.5 live connectivity
# check (numeric values replaced with round placeholders; no identifiers,
# credentials, or headers were ever part of this response body). Confirms
# our parser's assumed shape — interval.from/to, outputs.<index>.bands.B0.
# stats.{sampleCount,noDataCount,mean,stDev,min,max,percentiles} with
# percentile keys "25.0"/"50.0"/"75.0" — matches what the real API sends,
# unchanged from what CdseStatisticsClient already assumed.
_LIVE_SHAPE_REGRESSION_PAYLOAD = {
    "data": [
        {
            "interval": {"from": "2026-07-22T00:00:00Z", "to": "2026-07-23T00:00:00Z"},
            "outputs": {
                "ndvi": {
                    "bands": {
                        "B0": {
                            "stats": {
                                "min": 0.48,
                                "max": 0.48,
                                "mean": 0.48,
                                "stDev": 0.0,
                                "sampleCount": 1,
                                "noDataCount": 0,
                                "percentiles": {"25.0": 0.48, "50.0": 0.48, "75.0": 0.48},
                            }
                        }
                    }
                },
                "ndmi": {
                    "bands": {
                        "B0": {
                            "stats": {
                                "min": 0.17,
                                "max": 0.17,
                                "mean": 0.17,
                                "stDev": 0.0,
                                "sampleCount": 1,
                                "noDataCount": 0,
                                "percentiles": {"25.0": 0.17, "50.0": 0.17, "75.0": 0.17},
                            }
                        }
                    }
                },
                "ndre": {
                    "bands": {
                        "B0": {
                            "stats": {
                                "min": 0.33,
                                "max": 0.33,
                                "mean": 0.33,
                                "stDev": 0.0,
                                "sampleCount": 1,
                                "noDataCount": 0,
                                "percentiles": {"25.0": 0.33, "50.0": 0.33, "75.0": 0.33},
                            }
                        }
                    }
                },
                "msi": {
                    "bands": {
                        "B0": {
                            "stats": {
                                "min": 0.72,
                                "max": 0.72,
                                "mean": 0.72,
                                "stDev": 0.0,
                                "sampleCount": 1,
                                "noDataCount": 0,
                                "percentiles": {"25.0": 0.72, "50.0": 0.72, "75.0": 0.72},
                            }
                        }
                    }
                },
                "ndwi": {
                    "bands": {
                        "B0": {
                            "stats": {
                                "min": -0.5,
                                "max": -0.5,
                                "mean": -0.5,
                                "stDev": 0.0,
                                "sampleCount": 1,
                                "noDataCount": 0,
                                "percentiles": {"25.0": -0.5, "50.0": -0.5, "75.0": -0.5},
                            }
                        }
                    }
                },
                "nbr2": {
                    "bands": {
                        "B0": {
                            "stats": {
                                "min": 0.14,
                                "max": 0.14,
                                "mean": 0.14,
                                "stDev": 0.0,
                                "sampleCount": 1,
                                "noDataCount": 0,
                                "percentiles": {"25.0": 0.14, "50.0": 0.14, "75.0": 0.14},
                            }
                        }
                    }
                },
            },
        }
    ]
}


@respx.mock
async def test_parses_the_sanitized_live_response_shape_regression() -> None:
    _mock_token()
    respx.post(STATISTICS_URL).mock(
        return_value=httpx.Response(200, json=_LIVE_SHAPE_REGRESSION_PAYLOAD)
    )
    results = await _statistics_client().get_parcel_statistics(
        VALID_POLYGON, start_date=date(2026, 7, 22), end_date=date(2026, 7, 23)
    )
    assert len(results) == 1
    assert results[0].interval_start == date(2026, 7, 22)
    assert set(results[0].index_stats.keys()) == set(INDEX_NAMES)
    assert results[0].index_stats["ndvi"]["p50"] == pytest.approx(0.48)
    assert results[0].valid_pixel_count == 1
    assert results[0].invalid_pixel_count == 0


def test_evalscript_scales_reflectance_bands_by_the_dn_factor() -> None:
    script = build_evalscript()
    assert "REFLECTANCE_SCALE" in script
    for band in ("B03", "B04", "B05", "B08", "B11", "B12"):
        assert f"sample.{band} / REFLECTANCE_SCALE" in script
    # SCL is a classification code, never scaled.
    assert "sample.SCL / REFLECTANCE_SCALE" not in script
