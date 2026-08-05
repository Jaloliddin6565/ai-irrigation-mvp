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

export function WaterBalanceChart({ rows }: { rows: DailyWaterBalanceRow[] }) {
  const { t } = useTranslation();

  const sorted = [...rows].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const data = sorted.map((row) => ({
    date: row.date,
    timestamp: new Date(row.date).getTime(),
    depletion: row.depletion_end_mm,
    raw: row.raw_mm,
    precipitation: row.precipitation_mm,
    irrigation: row.effective_irrigation_mm,
    stage: row.stage,
  }));

  const lastRaw = data.length > 0 ? data[data.length - 1].raw : null;

  if (data.length === 0) {
    return <p className="field-hint">{t("charts.waterBalanceEmpty")}</p>;
  }

  return (
    <div className="chart-wrap">
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
        </ComposedChart>
      </ResponsiveContainer>
      <p className="field-hint">{t("charts.waterBalanceExplainer")}</p>
    </div>
  );
}
