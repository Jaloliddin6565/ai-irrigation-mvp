import type { GeoJsonPolygon } from "../types/api";

const EARTH_RADIUS_M = 6371000;

/**
 * Client-side PRELIMINARY area estimate only (equirectangular projection
 * centered on the polygon's mean latitude, shoelace formula). The backend
 * always recomputes the authoritative area via a proper geodesic
 * calculation (pyproj) at save time — this exists purely so the map can
 * show an approximate number while the user is still drawing.
 */
export function approxPolygonAreaHectares(polygon: GeoJsonPolygon): number | null {
  const ring = polygon.coordinates[0];
  if (!ring || ring.length < 4) return null;

  const meanLatRad = (ring.reduce((sum, [, lat]) => sum + lat, 0) / ring.length) * (Math.PI / 180);
  const cosLat = Math.cos(meanLatRad);

  const points = ring.map(([lon, lat]) => ({
    x: (lon * Math.PI) / 180 * EARTH_RADIUS_M * cosLat,
    y: (lat * Math.PI) / 180 * EARTH_RADIUS_M,
  }));

  let area = 0;
  for (let i = 0; i < points.length - 1; i += 1) {
    area += points[i].x * points[i + 1].y - points[i + 1].x * points[i].y;
  }
  const squareMeters = Math.abs(area) / 2;
  return squareMeters / 10000;
}

export function polygonBounds(polygon: GeoJsonPolygon): [[number, number], [number, number]] | null {
  const ring = polygon.coordinates[0];
  if (!ring || ring.length === 0) return null;
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLon = Infinity;
  let maxLon = -Infinity;
  for (const [lon, lat] of ring) {
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
  }
  return [
    [minLat, minLon],
    [maxLat, maxLon],
  ];
}

export const UZBEKISTAN_CENTER: [number, number] = [41.3775, 64.5853];
export const UZBEKISTAN_DEFAULT_ZOOM = 6;
