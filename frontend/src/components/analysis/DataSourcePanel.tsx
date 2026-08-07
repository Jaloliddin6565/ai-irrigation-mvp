import { useTranslation } from "react-i18next";

import "./DataSourcePanel.css";
import { DataModeBadge } from "../layout/DataModeBadge";
import { formatDate, formatDateTime, formatPercent } from "../../utils/format";
import { satelliteQualityKey, weatherCompletenessKey } from "../../utils/labels";
import type { SatelliteSummary, WeatherSummary } from "../../types/api";

export function DataSourcePanel({
  dataMode,
  weather,
  satellite,
}: {
  dataMode: WeatherSummary["data_mode"];
  weather: WeatherSummary;
  satellite: SatelliteSummary;
}) {
  const { t } = useTranslation();

  return (
    <div>
      <div className="row data-source-panel__header">
        <DataModeBadge mode={dataMode} />
      </div>

      <div className="row data-source-panel__columns">
        <div>
          <h3>{t("dataSource.weatherTitle")}</h3>
          <dl className="field-summary-card__facts">
            <div>
              <dt>{t("dataSource.provider")}</dt>
              <dd>{weather.provider}</dd>
            </div>
            <div>
              <dt>{t("dataSource.retrievedAt")}</dt>
              <dd>{formatDateTime(weather.retrieved_at)}</dd>
            </div>
            <div>
              <dt>{t("dataSource.coverage")}</dt>
              <dd>{t(weatherCompletenessKey(weather.completeness_status))}</dd>
            </div>
            <div>
              <dt>{t("dataSource.cacheHit")}</dt>
              <dd>{weather.cache_hit ? t("common.yes") : t("common.no")}</dd>
            </div>
          </dl>
          {weather.missing_dates.length > 0 ? (
            <p className="field-hint">
              {t("dataSource.missingDates")}: {weather.missing_dates.map(formatDate).join(", ")}
            </p>
          ) : null}
        </div>

        <div>
          <h3>{t("dataSource.satelliteTitle")}</h3>
          <dl className="field-summary-card__facts">
            <div>
              <dt>{t("dataSource.provider")}</dt>
              <dd>{satellite.provider}</dd>
            </div>
            <div>
              <dt>{t("dataSource.acquisitionDate")}</dt>
              <dd>{formatDate(satellite.latest_observation_date)}</dd>
            </div>
            <div>
              <dt>{t("dataSource.observationAge")}</dt>
              <dd>
                {satellite.latest_observation_age_days !== null
                  ? t("dataSource.daysAgo", { count: satellite.latest_observation_age_days })
                  : "—"}
              </dd>
            </div>
            <div>
              <dt>{t("dataSource.validPixelRatio")}</dt>
              <dd>{formatPercent(satellite.latest_valid_pixel_ratio)}</dd>
            </div>
            <div>
              <dt>{t("dataSource.qualityStatus")}</dt>
              <dd>{t(satelliteQualityKey(satellite.data_quality))}</dd>
            </div>
            <div>
              <dt>{t("dataSource.cacheHit")}</dt>
              <dd>{satellite.cache_hit ? t("common.yes") : t("common.no")}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
