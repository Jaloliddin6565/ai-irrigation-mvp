import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import * as L from "leaflet";
import "@geoman-io/leaflet-geoman-free";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import "./PolygonEditor.css";
import { approxPolygonAreaHectares, UZBEKISTAN_CENTER, UZBEKISTAN_DEFAULT_ZOOM } from "../../utils/geo";
import type { GeoJsonPolygon } from "../../types/api";

const TILE_URL = import.meta.env.VITE_MAP_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION =
  import.meta.env.VITE_MAP_TILE_ATTRIBUTION ??
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function layerToPolygon(layer: L.Polygon): GeoJsonPolygon {
  const geoJson = layer.toGeoJSON();
  const geometry = geoJson.type === "Feature" ? geoJson.geometry : geoJson;
  if (geometry.type !== "Polygon") {
    throw new Error("Expected a Polygon geometry from the drawn layer");
  }
  return { type: "Polygon", coordinates: geometry.coordinates };
}

function polygonToLatLngs(polygon: GeoJsonPolygon): L.LatLngExpression[] {
  return polygon.coordinates[0].map(([lon, lat]) => [lat, lon]);
}

interface PolygonEditorProps {
  value: GeoJsonPolygon | null;
  onChange: (polygon: GeoJsonPolygon | null, approxAreaHectares: number | null) => void;
}

/**
 * Draws exactly one editable field polygon. Preliminary client-side area is
 * shown for feedback only — the backend always recomputes the authoritative
 * area server-side (see CLAUDE.md / docs/architecture.md).
 */
export function PolygonEditor({ value, onChange }: PolygonEditorProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const groupRef = useRef<L.FeatureGroup | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current).setView(UZBEKISTAN_CENTER, UZBEKISTAN_DEFAULT_ZOOM);
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map);

    const group = L.featureGroup().addTo(map);
    mapRef.current = map;
    groupRef.current = group;

    map.pm.addControls({
      position: "topleft",
      drawMarker: false,
      drawCircleMarker: false,
      drawPolyline: false,
      drawRectangle: false,
      drawCircle: false,
      drawText: false,
      drawPolygon: true,
      editMode: true,
      dragMode: true,
      cutPolygon: false,
      removalMode: true,
      rotateMode: false,
    });

    function emitChange(layer: L.Polygon | null) {
      if (!layer) {
        onChangeRef.current(null, null);
        return;
      }
      const polygon = layerToPolygon(layer);
      onChangeRef.current(polygon, approxPolygonAreaHectares(polygon));
    }

    function attachLayerListeners(layer: L.Polygon) {
      layer.on("pm:edit", () => emitChange(layer));
      layer.on("pm:markerdragend", () => emitChange(layer));
      layer.on("pm:vertexadded", () => emitChange(layer));
    }

    map.on("pm:create", (e) => {
      const created = e.layer as L.Polygon;
      // Only one field polygon is allowed — replace any previous one.
      group.eachLayer((existing) => group.removeLayer(existing));
      group.addLayer(created);
      attachLayerListeners(created);
      emitChange(created);
    });

    map.on("pm:remove", (e) => {
      if (group.hasLayer(e.layer)) {
        group.removeLayer(e.layer);
      }
      emitChange(null);
    });

    if (value) {
      const initialLayer = L.polygon(polygonToLatLngs(value));
      group.addLayer(initialLayer);
      attachLayerListeners(initialLayer);
      initialLayer.pm.enable();
      map.fitBounds(initialLayer.getBounds(), { maxZoom: 16, padding: [16, 16] });
    }

    return () => {
      map.remove();
      mapRef.current = null;
      groupRef.current = null;
    };
    // Intentionally run once: the map/group must persist across re-renders
    // (e.g. form validation errors) so drawn geometry is never wiped.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleClear() {
    const group = groupRef.current;
    if (!group) return;
    group.eachLayer((layer) => group.removeLayer(layer));
    onChangeRef.current(null, null);
  }

  return (
    <div className="polygon-editor">
      <div ref={containerRef} className="polygon-editor__map" role="group" aria-label={t("field.mapLabel")} />
      <div className="row polygon-editor__actions">
        <button type="button" className="button button--secondary" onClick={handleClear}>
          {t("field.clearPolygon")}
        </button>
        <p className="field-hint">{t("field.polygonHint")}</p>
      </div>
    </div>
  );
}
