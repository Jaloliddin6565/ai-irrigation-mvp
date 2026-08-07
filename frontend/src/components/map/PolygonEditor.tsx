import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import * as L from "leaflet";
import "@geoman-io/leaflet-geoman-free";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import "./PolygonEditor.css";
import { addBaseLayers, isSatelliteLayerConfigured } from "./tileLayers";
import { applyUzbekGeomanLang } from "./geomanLang";
import { useGeolocation } from "./useGeolocation";
import { approxPolygonAreaHectares, UZBEKISTAN_CENTER, UZBEKISTAN_DEFAULT_ZOOM } from "../../utils/geo";
import type { GeoJsonPolygon } from "../../types/api";

applyUzbekGeomanLang();

const GEOLOCATION_ZOOM = 15;

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
  const locationLayerRef = useRef<L.LayerGroup | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const geolocation = useGeolocation();

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current).setView(UZBEKISTAN_CENTER, UZBEKISTAN_DEFAULT_ZOOM);
    addBaseLayers(map, {
      satellite: t("field.baseLayerSatellite"),
      plain: t("field.baseLayerPlain"),
    });

    const group = L.featureGroup().addTo(map);
    mapRef.current = map;
    groupRef.current = group;
    locationLayerRef.current = L.layerGroup().addTo(map);

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
      locationLayerRef.current = null;
    };
    // Intentionally run once: the map/group must persist across re-renders
    // (e.g. form validation errors) so drawn geometry is never wiped.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recenter/mark the map whenever a geolocation fix comes back. Separate
  // from the setup effect above so a location fix never rebuilds the map
  // (which would risk losing the drawn polygon).
  useEffect(() => {
    const map = mapRef.current;
    const locationLayer = locationLayerRef.current;
    if (!map || !locationLayer || !geolocation.position) return;

    locationLayer.clearLayers();
    const { lat, lon, accuracyMeters } = geolocation.position;
    L.marker([lat, lon]).addTo(locationLayer);
    if (accuracyMeters) {
      L.circle([lat, lon], { radius: accuracyMeters, color: "#2f6b3a", weight: 1, fillOpacity: 0.08 }).addTo(
        locationLayer
      );
    }
    map.setView([lat, lon], GEOLOCATION_ZOOM);
  }, [geolocation.position]);

  function handleClear() {
    const group = groupRef.current;
    if (!group) return;
    group.eachLayer((layer) => group.removeLayer(layer));
    onChangeRef.current(null, null);
  }

  function handleFitToPolygon() {
    const map = mapRef.current;
    const group = groupRef.current;
    if (!map || !group) return;
    const layers = group.getLayers();
    if (layers.length === 0) return;
    map.fitBounds(group.getBounds(), { maxZoom: 16, padding: [16, 16] });
  }

  const geolocationMessageKey: Record<typeof geolocation.status, string | null> = {
    idle: null,
    locating: "field.locating",
    success: null,
    denied: "field.locateDenied",
    unavailable: "field.locateUnavailable",
    unsupported: "field.locateUnsupported",
  };
  const geolocationMessage = geolocationMessageKey[geolocation.status];

  return (
    <div className="polygon-editor">
      <div ref={containerRef} className="polygon-editor__map" role="group" aria-label={t("field.mapLabel")} />
      <div className="row polygon-editor__actions">
        <button
          type="button"
          className="button button--secondary"
          onClick={geolocation.locate}
          disabled={geolocation.status === "locating"}
        >
          {t("field.locateMe")}
        </button>
        <button type="button" className="button button--secondary" onClick={handleFitToPolygon}>
          {t("field.fitToPolygon")}
        </button>
        <button type="button" className="button button--secondary" onClick={handleClear}>
          {t("field.clearPolygon")}
        </button>
      </div>
      {geolocationMessage ? <p className="field-hint">{t(geolocationMessage)}</p> : null}
      <p className="field-hint">{t("field.polygonHint")}</p>
      {isSatelliteLayerConfigured ? (
        <p className="field-hint">{t("field.satelliteGuidanceNotice")}</p>
      ) : null}
    </div>
  );
}
