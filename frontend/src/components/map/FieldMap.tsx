import "leaflet/dist/leaflet.css";
import * as L from "leaflet";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import "./PolygonEditor.css";
import { addBaseLayers } from "./tileLayers";
import { UZBEKISTAN_CENTER, UZBEKISTAN_DEFAULT_ZOOM } from "../../utils/geo";
import type { GeoJsonPolygon } from "../../types/api";

/** Read-only display of a saved field polygon, fit to its bounds. */
export function FieldMap({ polygon }: { polygon: GeoJsonPolygon }) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      dragging: true,
      scrollWheelZoom: false,
    }).setView(UZBEKISTAN_CENTER, UZBEKISTAN_DEFAULT_ZOOM);
    addBaseLayers(map, {
      satellite: t("field.baseLayerSatellite"),
      plain: t("field.baseLayerPlain"),
    });

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
