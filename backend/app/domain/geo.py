"""GeoJSON Polygon validation, normalization, area, and centroid calculation.

Area is computed via a WGS84 geodesic calculation (pyproj), independent of
the storage backend — this is what makes the same computation correct
whether the polygon sits in SQLite (MVP) or PostGIS geography (future, see
docs/postgis_migration.md). Centroid uses Shapely's planar centroid, which
is an acceptable approximation at field scale. Client-supplied area/centroid
values are never trusted — both are always recomputed here.
"""

from dataclasses import dataclass
from typing import Any

from pyproj import Geod
from shapely.geometry import shape
from shapely.validation import explain_validity

from app.core.errors import AppError

_GEOD = Geod(ellps="WGS84")

MIN_RING_POSITIONS = 4  # triangle + closing point, per GeoJSON spec


@dataclass(frozen=True)
class ValidatedPolygon:
    normalized_geojson: dict[str, Any]
    area_hectares: float
    centroid_latitude: float
    centroid_longitude: float


def _invalid_geometry_error(message_en: str, message_uz: str) -> AppError:
    return AppError(
        code="invalid_geometry",
        message_uz=message_uz,
        message_en=message_en,
        status_code=422,
    )


def _validate_ring_structure(ring: Any, *, ring_label: str) -> None:
    if not isinstance(ring, list) or len(ring) < MIN_RING_POSITIONS:
        raise _invalid_geometry_error(
            f"Polygon {ring_label} must have at least {MIN_RING_POSITIONS} positions"
            " (including closure).",
            "Poligon konturi kamida 4 ta nuqtadan iborat bo'lishi kerak"
            " (yopilish nuqtasi bilan birga).",
        )
    if ring[0] != ring[-1]:
        raise _invalid_geometry_error(
            f"Polygon {ring_label} must be closed (first and last position equal).",
            "Poligon konturi yopiq bo'lishi kerak (birinchi va oxirgi nuqta bir xil).",
        )
    for position in ring:
        if not isinstance(position, list | tuple) or len(position) < 2:
            raise _invalid_geometry_error(
                "Each coordinate must be a [longitude, latitude] pair.",
                "Har bir koordinata [uzunlik, kenglik] juftligi bo'lishi kerak.",
            )
        lon, lat = position[0], position[1]
        if not isinstance(lon, int | float) or not isinstance(lat, int | float):
            raise _invalid_geometry_error(
                "Coordinates must be numeric.", "Koordinatalar raqamli bo'lishi kerak."
            )
        if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
            raise _invalid_geometry_error(
                f"Coordinate out of range: [{lon}, {lat}].",
                f"Koordinata diapazondan tashqarida: [{lon}, {lat}].",
            )


def validate_and_normalize_polygon(
    geojson: Any,
    *,
    max_vertices: int,
    max_area_hectares: float,
) -> ValidatedPolygon:
    """Validate a client-supplied GeoJSON geometry and return normalized results.

    Raises AppError (422, code="invalid_geometry") on any rule violation.
    """
    if not isinstance(geojson, dict):
        raise _invalid_geometry_error(
            "Geometry must be a GeoJSON object.", "Geometriya GeoJSON obyekti bo'lishi kerak."
        )

    geometry_type = geojson.get("type")
    if geometry_type != "Polygon":
        raise _invalid_geometry_error(
            f"Only Polygon geometry is accepted, got '{geometry_type}'.",
            f"Faqat Polygon turi qabul qilinadi, '{geometry_type}' emas.",
        )

    coordinates = geojson.get("coordinates")
    if not coordinates or not isinstance(coordinates, list) or not coordinates[0]:
        raise _invalid_geometry_error("Polygon geometry is empty.", "Poligon geometriyasi bo'sh.")

    total_vertices = sum(len(ring) for ring in coordinates if isinstance(ring, list))
    if total_vertices > max_vertices:
        raise _invalid_geometry_error(
            f"Polygon has too many vertices ({total_vertices} > {max_vertices}).",
            f"Poligon nuqtalari juda ko'p ({total_vertices} > {max_vertices}).",
        )

    _validate_ring_structure(coordinates[0], ring_label="exterior ring")
    for hole_index, hole in enumerate(coordinates[1:], start=1):
        _validate_ring_structure(hole, ring_label=f"hole #{hole_index}")

    try:
        polygon = shape(geojson)
    except (ValueError, TypeError) as exc:
        raise _invalid_geometry_error(
            f"Could not parse geometry: {exc}", "Geometriyani tahlil qilib bo'lmadi."
        ) from exc

    if polygon.is_empty:
        raise _invalid_geometry_error("Polygon geometry is empty.", "Poligon geometriyasi bo'sh.")

    if not polygon.is_valid:
        raise _invalid_geometry_error(
            f"Polygon geometry is invalid: {explain_validity(polygon)}",
            "Poligon geometriyasi yaroqsiz (chegaralar o'zini o'zi kesib o'tgan bo'lishi mumkin).",
        )

    area_m2, _perimeter_m = _GEOD.geometry_area_perimeter(polygon)
    area_hectares = abs(area_m2) / 10_000

    if area_hectares <= 0:
        raise _invalid_geometry_error(
            "Polygon area must be greater than zero.",
            "Poligon maydoni noldan katta bo'lishi kerak.",
        )

    if area_hectares > max_area_hectares:
        raise _invalid_geometry_error(
            f"Polygon area ({area_hectares:.2f} ha) exceeds the maximum allowed"
            f" ({max_area_hectares} ha).",
            f"Poligon maydoni ({area_hectares:.2f} ga) ruxsat etilgan maksimal maydondan"
            f" ({max_area_hectares} ga) katta.",
        )

    centroid = polygon.centroid
    centroid_longitude, centroid_latitude = round(centroid.x, 7), round(centroid.y, 7)

    normalized_geojson: dict[str, Any] = {
        "type": "Polygon",
        "coordinates": [
            [[round(float(lon), 7), round(float(lat), 7)] for lon, lat in ring]
            for ring in coordinates
        ],
    }

    return ValidatedPolygon(
        normalized_geojson=normalized_geojson,
        area_hectares=round(area_hectares, 4),
        centroid_latitude=centroid_latitude,
        centroid_longitude=centroid_longitude,
    )
