import { useTranslation } from "react-i18next";

import { ConfidenceCard } from "../../components/analysis/ConfidenceCard";
import { DataSourcePanel } from "../../components/analysis/DataSourcePanel";
import { RecommendationCard } from "../../components/analysis/RecommendationCard";
import { SatelliteChart } from "../../components/charts/SatelliteChart";
import { WaterBalanceChart } from "../../components/charts/WaterBalanceChart";
import { WeatherChart } from "../../components/charts/WeatherChart";
import { ApiErrorPanel } from "../../components/feedback/ApiErrorPanel";
import { Loading } from "../../components/feedback/Loading";
import { useSatelliteTimeseries, useWeather } from "../../api/hooks";
import { formatDate } from "../../utils/format";
import { initializationMethodKey } from "../../utils/labels";
import type { AnalysisResponse } from "../../types/api";

export function AnalysisResultView({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useTranslation();
  const satellite = useSatelliteTimeseries(analysis.field_id);
  const weather = useWeather(analysis.field_id);

  return (
    <div className="stack">
      <RecommendationCard
        recommendation={analysis.recommendation}
        methodologyVersion={analysis.methodology_version}
        analysisDate={analysis.analysis_date}
      />

      <ConfidenceCard confidence={analysis.confidence} />

      <DataSourcePanel
        dataMode={analysis.data_mode}
        weather={analysis.weather_summary}
        satellite={analysis.satellite_summary}
      />

      {analysis.warnings.length > 0 ? (
        <div className="alert alert--warning">
          <h2>{t("analysis.warnings")}</h2>
          <ul>
            {analysis.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <section className="card">
        <h2>{t("waterBalance.title")}</h2>
        <dl className="field-summary-card__facts">
          <div>
            <dt>{t("waterBalance.taw")}</dt>
            <dd>{analysis.water_balance_summary.taw_mm.toFixed(1)} mm</dd>
          </div>
          <div>
            <dt>{t("waterBalance.raw")}</dt>
            <dd>{analysis.water_balance_summary.raw_mm.toFixed(1)} mm</dd>
          </div>
          <div>
            <dt>{t("waterBalance.initMethod")}</dt>
            <dd>{t(initializationMethodKey(analysis.water_balance_summary.initialization.method))}</dd>
          </div>
          <div>
            <dt>{t("waterBalance.cropStage")}</dt>
            <dd>
              {t(`cropGrowthStage.${analysis.crop_stage.stage}`)} (Kc {analysis.crop_stage.kc.toFixed(2)})
            </dd>
          </div>
        </dl>
        {analysis.water_balance_summary.initialization.warnings.length > 0 ? (
          <ul>
            {analysis.water_balance_summary.initialization.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        ) : null}
        <p className="field-hint">{t("waterBalance.estimateNotice")}</p>
        <WaterBalanceChart rows={analysis.water_balance_summary.daily_rows} />
      </section>

      <section className="card">
        <h2>{t("charts.satelliteTitle")}</h2>
        {satellite.isLoading ? <Loading /> : null}
        {satellite.error ? <ApiErrorPanel error={satellite.error} /> : null}
        {satellite.data ? <SatelliteChart observations={satellite.data.observations} /> : null}
        {satellite.data && satellite.data.rejected_acquisitions.length > 0 ? (
          <details>
            <summary>{t("charts.rejectedAcquisitions")}</summary>
            <ul>
              {satellite.data.rejected_acquisitions.map((rejected) => (
                <li key={`${rejected.acquisition_date}-${rejected.reason}`}>
                  {formatDate(rejected.acquisition_date)} — {rejected.reason}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </section>

      <section className="card">
        <h2>{t("charts.weatherTitle")}</h2>
        {weather.isLoading ? <Loading /> : null}
        {weather.error ? <ApiErrorPanel error={weather.error} /> : null}
        {weather.data ? <WeatherChart days={weather.data.days} /> : null}
      </section>
    </div>
  );
}
