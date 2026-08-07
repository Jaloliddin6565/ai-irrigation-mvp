import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslation } from "react-i18next";

import { formatDate } from "../../utils/format";
import type { DailyWaterBalanceRow } from "../../types/api";

// Depletion at/near TAW for many consecutive days is either correct
// clamping (no water input while ET continues) or a sign the model has no
// record of irrigation that actually happened — the water balance can't
// tell the two apart from its own numbers alone (see
// docs/methodology.md), so this only surfaces the pattern, never
// reinterprets it as measured soil moisture or a defect.
const TAW_NEAR_THRESHOLD_FRACTION = 0.95;
const FLAT_AT_TAW_WARNING_MIN_DAYS = 5;

function longestNearTawRunDays(rows: { depletion: number; taw: number }[]): number {
  let longest = 0;
  let current = 0;
  for (const row of rows) {
    if (row.taw > 0 && row.depletion >= row.taw * TAW_NEAR_THRESHOLD_FRACTION) {
      current += 1;
      longest = Math.max(longest, current);
    } else {
      current = 0;
    }
  }
  return longest;
}

export function WaterBalanceChart({ rows }: { rows: DailyWaterBalanceRow[] }) {
  const { t } = useTranslation();

  const sorted = [...rows].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const data = sorted.map((row) => ({
    date: row.date,
    timestamp: new Date(row.date).getTime(),
    depletion: row.depletion_end_mm,
    raw: row.raw_mm,
    taw: row.taw_mm,
    precipitation: row.precipitation_mm,
    irrigation: row.effective_irrigation_mm,
    stage: row.stage,
  }));

  const lastRaw = data.length > 0 ? data[data.length - 1].raw : null;
  const lastTaw = data.length > 0 ? data[data.length - 1].taw : null;
  const flatAtTawDays = longestNearTawRunDays(data);

  if (data.length === 0) {
    return <p className="field-hint">{t("charts.waterBalanceEmpty")}</p>;
  }

  return (
    <div className="chart-wrap" role="img" aria-label={t("charts.waterBalanceAriaLabel")}>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ left: 8, right: 16, top: 16, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="timestamp"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(value: number) => formatDate(new Date(value).toISOString())}
          />
          <YAxis />
          <Tooltip
            labelFormatter={(label: unknown) => formatDate(new Date(Number(label)).toISOString())}
          />
          <Legend />
          <Bar dataKey="precipitation" name={t("charts.precipitation")} fill="#6ba0f0" />
          <Bar dataKey="irrigation" name={t("charts.irrigationEvents")} fill="#2f6b3a" />
          <Line
            type="monotone"
            dataKey="depletion"
            name={t("charts.depletion")}
            stroke="#c0392b"
            dot={false}
          />
          {lastRaw !== null ? (
            <ReferenceLine
              y={lastRaw}
              stroke="#e67e22"
              strokeDasharray="4 4"
              label={{ value: t("charts.rawThreshold"), position: "insideTopRight" }}
            />
          ) : null}
          {lastTaw !== null ? (
            <ReferenceLine
              y={lastTaw}
              stroke="#8e44ad"
              strokeDasharray="2 6"
              label={{ value: t("charts.tawThreshold"), position: "insideBottomRight" }}
            />
          ) : null}
        </ComposedChart>
      </ResponsiveContainer>
      <p className="field-hint">{t("charts.waterBalanceExplainer")}</p>

      {flatAtTawDays >= FLAT_AT_TAW_WARNING_MIN_DAYS ? (
        <div className="alert alert--warning">
          {t("charts.flatAtTawWarning", { days: flatAtTawDays })}
        </div>
      ) : null}

      <details className="chart-data-table">
        <summary>{t("charts.viewAsTable")}</summary>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("analysisHistory.date")}</th>
                <th>{t("charts.depletion")}</th>
                <th>RAW (mm)</th>
                <th>{t("charts.precipitation")}</th>
                <th>{t("charts.irrigationEvents")}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.date}>
                  <td>{formatDate(row.date)}</td>
                  <td>{row.depletion.toFixed(1)}</td>
                  <td>{row.raw.toFixed(1)}</td>
                  <td>{row.precipitation.toFixed(1)}</td>
                  <td>{row.irrigation.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
