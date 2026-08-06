import math

import pytest

from app.core.errors import AppError
from app.domain.geo import validate_and_normalize_polygon

VALID_SQUARE = {
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


def _validate(geojson: dict, *, max_vertices: int = 1000, max_area_hectares: float = 500.0):
    return validate_and_normalize_polygon(
        geojson, max_vertices=max_vertices, max_area_hectares=max_area_hectares
    )


def test_valid_square_area_matches_independent_flat_earth_estimate() -> None:
    result = _validate(VALID_SQUARE)

    lat = 41.3005
    m_per_deg_lat = 111_320
    m_per_deg_lon = 111_320 * math.cos(math.radians(lat))
    side_deg = 0.001
    expected_area_ha = (side_deg * m_per_deg_lat) * (side_deg * m_per_deg_lon) / 10_000

    assert result.area_hectares == pytest.approx(expected_area_ha, rel=0.02)


def test_valid_square_centroid_is_near_the_average_of_corners() -> None:
    result = _validate(VALID_SQUARE)

    assert result.centroid_longitude == pytest.approx(69.2405, abs=1e-4)
    assert result.centroid_latitude == pytest.approx(41.3005, abs=1e-4)


def test_normalized_geojson_is_a_clean_polygon() -> None:
    result = _validate(VALID_SQUARE)

    assert result.normalized_geojson["type"] == "Polygon"
    assert len(result.normalized_geojson["coordinates"][0]) == 5
    assert (
        result.normalized_geojson["coordinates"][0][0]
        == result.normalized_geojson["coordinates"][0][-1]
    )


@pytest.mark.parametrize(
    "geojson",
    [
        {"type": "Point", "coordinates": [69.24, 41.30]},
        {"type": "LineString", "coordinates": [[69.24, 41.30], [69.25, 41.31]]},
        {"type": "MultiPolygon", "coordinates": [VALID_SQUARE["coordinates"]]},
    ],
    ids=["point", "linestring", "multipolygon"],
)
def test_rejects_non_polygon_geometry_types(geojson: dict) -> None:
    with pytest.raises(AppError) as exc_info:
        _validate(geojson)
    assert exc_info.value.code == "invalid_geometry"


def test_rejects_unclosed_ring() -> None:
    geojson = {
        "type": "Polygon",
        "coordinates": [[[69.24, 41.30], [69.25, 41.30], [69.25, 41.31], [69.24, 41.31]]],
    }
    with pytest.raises(AppError):
        _validate(geojson)


def test_rejects_ring_with_too_few_points() -> None:
    geojson = {
        "type": "Polygon",
        "coordinates": [[[69.24, 41.30], [69.25, 41.30], [69.24, 41.30]]],
    }
    with pytest.raises(AppError):
        _validate(geojson)


@pytest.mark.parametrize(
    "bad_point",
    [
        [200.0, 41.30],  # longitude out of range
        [69.24, 95.0],  # latitude out of range
        [-200.0, 41.30],
        [69.24, -95.0],
    ],
)
def test_rejects_out_of_range_coordinates(bad_point: list[float]) -> None:
    geojson = {
        "type": "Polygon",
        "coordinates": [
            [[69.24, 41.30], bad_point, [69.25, 41.31], [69.24, 41.31], [69.24, 41.30]]
        ],
    }
    with pytest.raises(AppError):
        _validate(geojson)


def test_rejects_self_intersecting_bowtie_polygon() -> None:
    bowtie = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
    }
    with pytest.raises(AppError):
        _validate(bowtie)


def test_rejects_empty_geometry() -> None:
    with pytest.raises(AppError):
        _validate({"type": "Polygon", "coordinates": []})


def test_rejects_non_dict_geometry() -> None:
    with pytest.raises(AppError):
        _validate("not a geometry")  # type: ignore[arg-type]


def test_rejects_polygon_exceeding_max_area() -> None:
    huge = {
        "type": "Polygon",
        "coordinates": [[[60, 30], [70, 30], [70, 40], [60, 40], [60, 30]]],
    }
    with pytest.raises(AppError) as exc_info:
        _validate(huge, max_area_hectares=10)
    assert "exceeds the maximum allowed" in (exc_info.value.message_en or "")


def test_rejects_polygon_exceeding_max_vertices() -> None:
    many_points = [[69.24 + 0.0001 * i, 41.30] for i in range(20)] + [[69.24, 41.30]]
    geojson = {"type": "Polygon", "coordinates": [many_points]}
    with pytest.raises(AppError):
        _validate(geojson, max_vertices=5)


def test_identical_input_produces_identical_output() -> None:
    first = _validate(VALID_SQUARE)
    second = _validate(VALID_SQUARE)
    assert first == second
