import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslation } from "react-i18next";

import { formatDate } from "../../utils/format";
import type { DailyWeather } from "../../types/api";

export function WeatherChart({ days }: { days: DailyWeather[] }) {
  const { t } = useTranslation();

  const sorted = [...days].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const data = sorted.map((day) => ({
    date: day.date,
    timestamp: new Date(day.date).getTime(),
    historicalEt0: day.is_forecast ? null : day.et0_mm,
    forecastEt0: day.is_forecast ? day.et0_mm : null,
    precipitation: day.precipitation_mm,
    tempMax: day.temperature_max_c,
    tempMin: day.temperature_min_c,
    isForecast: day.is_forecast,
  }));

  if (data.length === 0) {
    return <p className="field-hint">{t("charts.weatherEmpty")}</p>;
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
          <YAxis yAxisId="mm" />
          <YAxis yAxisId="c" orientation="right" />
          <Tooltip
            labelFormatter={(label: unknown) => formatDate(new Date(Number(label)).toISOString())}
          />
          <Legend />
          <Bar yAxisId="mm" dataKey="precipitation" name={t("charts.precipitation")} fill="#6ba0f0" />
          <Line
            yAxisId="mm"
            type="monotone"
            dataKey="historicalEt0"
            name={t("charts.et0Historical")}
            stroke="#2f6b3a"
            dot={false}
            connectNulls
          />
          <Line
            yAxisId="mm"
            type="monotone"
            dataKey="forecastEt0"
            name={t("charts.et0Forecast")}
            stroke="#2f6b3a"
            strokeDasharray="5 4"
            dot={false}
            connectNulls
          />
          <Line
            yAxisId="c"
            type="monotone"
            dataKey="tempMax"
            name={t("charts.tempMax")}
            stroke="#c0392b"
            dot={false}
          />
          <Line
            yAxisId="c"
            type="monotone"
            dataKey="tempMin"
            name={t("charts.tempMin")}
            stroke="#e67e22"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="field-hint">{t("charts.forecastDashedNotice")}</p>
    </div>
  );
}
