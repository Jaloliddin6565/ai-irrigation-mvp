import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslation } from "react-i18next";

import "./SatelliteChart.css";
import { CollapsibleSection } from "../disclosure/CollapsibleSection";
import { formatDate, formatPercent } from "../../utils/format";
import type { ParcelObservation } from "../../types/api";

// NDVI/NDMI stay prominent (the two indices farmers are actually shown by
// default); MSI/NDRE/NDWI/NBR2 move into a collapsed "more indices"
// section — all six remain fully available, just not given equal visual
// weight (see docs/methodology.md and CLAUDE.md rule 4).
const PRIMARY_INDEX_KEYS = ["ndvi", "ndmi"] as const;
const SECONDARY_INDEX_KEYS = ["msi", "ndre", "ndwi", "nbr2"] as const;
type IndexKey = (typeof PRIMARY_INDEX_KEYS)[number] | (typeof SECONDARY_INDEX_KEYS)[number];

interface ChartPoint {
  date: string;
  timestamp: number;
  p50: number;
  validPixelRatio: number;
  qualityStatus: string;
  isUsable: boolean;
}

export function SatelliteChart({ observations }: { observations: ParcelObservation[] }) {
  const { t } = useTranslation();
  const [index, setIndex] = useState<IndexKey>("ndvi");

  const sorted = [...observations].sort(
    (a, b) => new Date(a.acquisition_date).getTime() - new Date(b.acquisition_date).getTime()
  );

  const points: ChartPoint[] = sorted.map((obs) => ({
    date: obs.acquisition_date,
    timestamp: new Date(obs.acquisition_date).getTime(),
    p50: obs[index].p50,
    validPixelRatio: obs.valid_pixel_ratio,
    qualityStatus: obs.quality_status,
    isUsable: obs.quality_status === "usable",
  }));

  const flagged = points.filter((p) => !p.isUsable);

  if (observations.length === 0) {
    return <p className="field-hint">{t("charts.satelliteEmpty")}</p>;
  }

  return (
    <div>
      <div className="row">
        {PRIMARY_INDEX_KEYS.map((key) => (
          <button
            key={key}
            type="button"
            className={`button ${index === key ? "" : "button--secondary"}`}
            onClick={() => setIndex(key)}
          >
            {t(`charts.index.${key}`)}
          </button>
        ))}
      </div>
      <CollapsibleSection title={t("charts.moreIndices")}>
        <div className="row">
          {SECONDARY_INDEX_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              className={`button ${index === key ? "" : "button--secondary"}`}
              onClick={() => setIndex(key)}
            >
              {t(`charts.index.${key}`)}
            </button>
          ))}
        </div>
      </CollapsibleSection>
      <p className="field-hint">{t(`charts.indexExplainer.${index}`)}</p>

      <div
        className="chart-wrap"
        role="img"
        aria-label={t("charts.satelliteAriaLabel", { index: t(`charts.index.${index}`) })}
      >
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={points} margin={{ left: 8, right: 16, top: 16, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="timestamp"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(value: number) => formatDate(new Date(value).toISOString())}
            />
            <YAxis domain={["auto", "auto"]} />
            <Tooltip
              labelFormatter={(label: unknown) => formatDate(new Date(Number(label)).toISOString())}
              formatter={(value: unknown, name: unknown, entry: unknown) => {
                const numericValue = Number(value);
                if (name !== "p50") return [numericValue.toFixed(3), String(name)];
                const payload = (entry as { payload: ChartPoint }).payload;
                return [
                  `${numericValue.toFixed(3)} (${t("charts.validPixelRatio")}: ${formatPercent(payload.validPixelRatio)}, ${t(
                    "charts.qualityStatus"
                  )}: ${t(`satellite.observationQuality.${payload.qualityStatus}`)})`,
                  t(`charts.index.${index}`),
                ];
              }}
            />
            <Line type="monotone" dataKey="p50" stroke="#2f6b3a" dot connectNulls={false} name="p50" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {flagged.length > 0 ? (
        <div className="satellite-chart__flagged">
          <p className="field-hint">{t("charts.flaggedObservations")}</p>
          <ResponsiveContainer width="100%" height={60}>
            <ScatterChart margin={{ left: 8, right: 16 }}>
              <XAxis
                dataKey="timestamp"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(value: number) => formatDate(new Date(value).toISOString())}
              />
              <YAxis dataKey={() => 0} tick={false} width={0} />
              <Tooltip
                labelFormatter={(label: unknown) => formatDate(new Date(Number(label)).toISOString())}
                formatter={(_value: unknown, _name: unknown, entry: unknown) => {
                  const payload = (entry as { payload: ChartPoint }).payload;
                  return [t(`satellite.observationQuality.${payload.qualityStatus}`), t("charts.qualityStatus")];
                }}
              />
              <Scatter data={flagged} fill="#c0392b" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      <details className="chart-data-table">
        <summary>{t("charts.viewAsTable")}</summary>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("analysisHistory.date")}</th>
                <th>{t(`charts.index.${index}`)} (p50)</th>
                <th>{t("charts.validPixelRatio")}</th>
                <th>{t("charts.qualityStatus")}</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.date}>
                  <td>{formatDate(point.date)}</td>
                  <td>{point.p50.toFixed(3)}</td>
                  <td>{formatPercent(point.validPixelRatio)}</td>
                  <td>{t(`satellite.observationQuality.${point.qualityStatus}`)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
