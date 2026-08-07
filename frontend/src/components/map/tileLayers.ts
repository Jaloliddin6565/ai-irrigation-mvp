import * as L from "leaflet";

// OSM stays the always-available default base layer — same env vars as
// before, unchanged behavior for anyone who never configures satellite
// tiles.
export const OSM_TILE_URL =
  import.meta.env.VITE_MAP_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const OSM_TILE_ATTRIBUTION =
  import.meta.env.VITE_MAP_TILE_ATTRIBUTION ??
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

// Satellite tiles are entirely optional and operator-configured at deploy
// time. No default URL, no committed key — if unset, the app must keep
// working with OSM only and must never show a broken-tile layer or an
// unusable toggle. See docs/deployment.md.
const SATELLITE_TILE_URL = import.meta.env.VITE_SATELLITE_TILE_URL || null;
const SATELLITE_TILE_ATTRIBUTION = import.meta.env.VITE_SATELLITE_TILE_ATTRIBUTION || null;

export const isSatelliteLayerConfigured = Boolean(SATELLITE_TILE_URL);

export function createOsmLayer(): L.TileLayer {
  return L.tileLayer(OSM_TILE_URL, { attribution: OSM_TILE_ATTRIBUTION, maxZoom: 19 });
}

export function createSatelliteLayer(): L.TileLayer | null {
  if (!SATELLITE_TILE_URL) return null;
  return L.tileLayer(SATELLITE_TILE_URL, {
    attribution: SATELLITE_TILE_ATTRIBUTION ?? "",
    maxZoom: 19,
  });
}

/**
 * Adds the OSM base layer (always) and, only when a satellite tile source is
 * configured, a layer switcher control. When unconfigured, no switcher is
 * added at all — there is no state in which a satellite option is visible
 * but non-functional.
 */
export function addBaseLayers(map: L.Map, labels: { satellite: string; plain: string }): void {
  const osm = createOsmLayer().addTo(map);
  const satellite = createSatelliteLayer();
  if (satellite) {
    L.control
      .layers({ [labels.satellite]: satellite, [labels.plain]: osm }, undefined, {
        position: "topright",
        collapsed: false,
      })
      .addTo(map);
  }
}
