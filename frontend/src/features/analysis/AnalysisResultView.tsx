import { useTranslation } from "react-i18next";

import { ConfidenceCard } from "../../components/analysis/ConfidenceCard";
import { DataSourcePanel } from "../../components/analysis/DataSourcePanel";
import { RecommendationCard } from "../../components/analysis/RecommendationCard";
import { CollapsibleSection } from "../../components/disclosure/CollapsibleSection";
import { SatelliteChart } from "../../components/charts/SatelliteChart";
import { WaterBalanceChart } from "../../components/charts/WaterBalanceChart";
import { WeatherChart } from "../../components/charts/WeatherChart";
import { ApiErrorPanel } from "../../components/feedback/ApiErrorPanel";
import { Loading } from "../../components/feedback/Loading";
import { useSatelliteTimeseries, useWeather } from "../../api/hooks";
import { formatDate, formatMm } from "../../utils/format";
import { initializationMethodKey, messageCodeKey } from "../../utils/labels";
import type { AnalysisResponse } from "../../types/api";

/**
 * Two-level result view: RecommendationCard + ConfidenceCard + the facts
 * strip below are the primary farmer-facing view (status, window,
 * actionable amount, short reason, confidence, latest satellite date,
 * rain forecast). Everything else — the full daily water balance, all six
 * satellite indices, provenance metadata, and raw technical
 * warning/reason text — lives in collapsed expert sections below, still
 * fully reachable, never the primary content (see CLAUDE.md rule 4 and
 * docs/methodology.md).
 */
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

      <section className="card">
        <dl className="field-summary-card__facts">
          <div>
            <dt>{t("analysisResult.latestSatelliteDate")}</dt>
            <dd>
              {analysis.satellite_summary.latest_observation_date
                ? formatDate(analysis.satellite_summary.latest_observation_date)
                : t("common.none")}
            </dd>
          </div>
          <div>
            <dt>{t("analysisResult.forecastRain")}</dt>
            <dd>{formatMm(analysis.weather_summary.forecast_precipitation_mm)}</dd>
          </div>
        </dl>
      </section>

      {analysis.water_balance_summary.initialization.warning_codes.length > 0 ? (
        <div className="alert alert--warning">
          <ul>
            {analysis.water_balance_summary.initialization.warning_codes.map((message, index) => (
              <li key={`${message.code}-${index}`}>{t(messageCodeKey(message.code), message.params)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <CollapsibleSection title={t("waterBalance.title")}>
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
          {analysis.water_balance_summary.initialization.start_date ? (
            <div>
              <dt>{t("waterBalance.initStartDate")}</dt>
              <dd>{formatDate(analysis.water_balance_summary.initialization.start_date)}</dd>
            </div>
          ) : null}
          <div>
            <dt>{t("waterBalance.cropStage")}</dt>
            <dd>
              {t(`cropGrowthStage.${analysis.crop_stage.stage}`)} (Kc {analysis.crop_stage.kc.toFixed(2)})
            </dd>
          </div>
        </dl>
        <p className="field-hint">{t("waterBalance.estimateNotice")}</p>
        <p className="field-hint">{t("waterBalance.cannotInferUnloggedIrrigation")}</p>
        <WaterBalanceChart rows={analysis.water_balance_summary.daily_rows} />
      </CollapsibleSection>

      <CollapsibleSection title={t("charts.satelliteTitle")}>
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
      </CollapsibleSection>

      <CollapsibleSection title={t("charts.weatherTitle")}>
        {weather.isLoading ? <Loading /> : null}
        {weather.error ? <ApiErrorPanel error={weather.error} /> : null}
        {weather.data ? <WeatherChart days={weather.data.days} /> : null}
      </CollapsibleSection>

      <CollapsibleSection title={t("dataSource.title")}>
        <DataSourcePanel
          dataMode={analysis.data_mode}
          weather={analysis.weather_summary}
          satellite={analysis.satellite_summary}
        />
      </CollapsibleSection>

      {analysis.warnings.length > 0 ? (
        <CollapsibleSection title={t("analysisResult.rawWarnings")}>
          <ul>
            {analysis.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </CollapsibleSection>
      ) : null}
    </div>
  );
}
