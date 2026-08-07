import math

import httpx
import pytest

from app.core.provider_errors import UnsupportedGeometryError
from app.providers.satellite.statistics import (
    METERS_PER_DEGREE_LATITUDE,
    TARGET_RESOLUTION_METERS,
    _polygon_reference_latitude,
    _resolution_degrees_for_polygon,
    _safe_provider_error_summary,
)


UZBEKISTAN_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [69.20, 41.20],
            [69.30, 41.20],
            [69.30, 41.30],
            [69.20, 41.30],
            [69.20, 41.20],
        ]
    ],
}


def test_reference_latitude_uses_polygon_extent_midpoint() -> None:
    assert _polygon_reference_latitude(UZBEKISTAN_POLYGON) == pytest.approx(41.25)


def test_epsg4326_resolution_is_degree_scale_not_ten_degrees() -> None:
    resx, resy = _resolution_degrees_for_polygon(UZBEKISTAN_POLYGON)

    assert 0 < resx < 0.001
    assert 0 < resy < 0.001
    assert resx != pytest.approx(10.0)
    assert resy != pytest.approx(10.0)


def test_resolution_is_approximately_ten_metres_at_uzbekistan_latitude() -> None:
    reference_latitude = _polygon_reference_latitude(UZBEKISTAN_POLYGON)
    resx, resy = _resolution_degrees_for_polygon(UZBEKISTAN_POLYGON)

    north_south_metres = resy * METERS_PER_DEGREE_LATITUDE
    east_west_metres = (
        resx
        * METERS_PER_DEGREE_LATITUDE
        * math.cos(math.radians(reference_latitude))
    )

    assert north_south_metres == pytest.approx(TARGET_RESOLUTION_METERS, rel=1e-6)
    assert east_west_metres == pytest.approx(TARGET_RESOLUTION_METERS, rel=1e-6)


def test_longitude_degree_resolution_increases_with_latitude() -> None:
    lower_lat_polygon = {
        "type": "Polygon",
        "coordinates": [[[69.0, 38.0], [69.1, 38.0], [69.1, 38.1], [69.0, 38.0]]],
    }
    higher_lat_polygon = {
        "type": "Polygon",
        "coordinates": [[[69.0, 45.0], [69.1, 45.0], [69.1, 45.1], [69.0, 45.0]]],
    }

    lower_resx, lower_resy = _resolution_degrees_for_polygon(lower_lat_polygon)
    higher_resx, higher_resy = _resolution_degrees_for_polygon(higher_lat_polygon)

    assert higher_resx > lower_resx
    assert higher_resy == pytest.approx(lower_resy)


def test_invalid_polygon_coordinates_raise_supported_error() -> None:
    with pytest.raises(UnsupportedGeometryError):
        _resolution_degrees_for_polygon({"type": "Polygon", "coordinates": [[]]})


def test_safe_provider_error_summary_extracts_only_expected_fields() -> None:
    response = httpx.Response(
        400,
        json={
            "error": {
                "code": "COMMON_BAD_PAYLOAD",
                "reason": "Invalid request",
                "message": "Resolution is invalid",
                "access_token": "must-not-appear",
                "client_secret": "must-not-appear",
            }
        },
    )

    summary = _safe_provider_error_summary(response)

    assert summary is not None
    assert "COMMON_BAD_PAYLOAD" in summary
    assert "Invalid request" in summary
    assert "Resolution is invalid" in summary
    assert "access_token" not in summary
    assert "client_secret" not in summary
    assert "must-not-appear" not in summary


def test_safe_provider_error_summary_handles_non_json_response() -> None:
    response = httpx.Response(400, content=b"not-json")

    assert _safe_provider_error_summary(response) is None
