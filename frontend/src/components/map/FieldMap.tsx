import "leaflet/dist/leaflet.css";
import * as L from "leaflet";
import { useEffect, useRef } from "react";

import "./PolygonEditor.css";
import { UZBEKISTAN_CENTER, UZBEKISTAN_DEFAULT_ZOOM } from "../../utils/geo";
import type { GeoJsonPolygon } from "../../types/api";

const TILE_URL = import.meta.env.VITE_MAP_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION =
  import.meta.env.VITE_MAP_TILE_ATTRIBUTION ??
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

/** Read-only display of a saved field polygon, fit to its bounds. */
export function FieldMap({ polygon }: { polygon: GeoJsonPolygon }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      dragging: true,
      scrollWheelZoom: false,
    }).setView(UZBEKISTAN_CENTER, UZBEKISTAN_DEFAULT_ZOOM);
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map);

    const latLngs = polygon.coordinates[0].map(([lon, lat]) => [lat, lon] as L.LatLngExpression);
    const layer = L.polygon(latLngs, { color: "#2f6b3a" }).addTo(map);
    map.fitBounds(layer.getBounds(), { maxZoom: 16, padding: [16, 16] });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={containerRef} className="polygon-editor__map" />;
}
