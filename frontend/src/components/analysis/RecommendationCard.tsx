import { useTranslation } from "react-i18next";

import "./RecommendationCard.css";
import { formatDate, formatM3, formatMm } from "../../utils/format";
import { recommendationStatusKey } from "../../utils/labels";
import type { RecommendationSchema } from "../../types/api";

const STATUS_TONE: Record<string, "good" | "watch" | "urgent" | "neutral"> = {
  no_irrigation_needed: "good",
  monitor: "watch",
  irrigate_soon: "watch",
  irrigate_now: "urgent",
  delay_due_to_forecast_rain: "watch",
  insufficient_data: "neutral",
};

export function RecommendationCard({
  recommendation,
  methodologyVersion,
  analysisDate,
}: {
  recommendation: RecommendationSchema;
  methodologyVersion: string;
  analysisDate: string;
}) {
  const { t } = useTranslation();
  const tone = STATUS_TONE[recommendation.status] ?? "neutral";
  const hasRange = recommendation.status !== "insufficient_data";

  return (
    <section className={`card recommendation-card recommendation-card--${tone}`}>
      <p className="recommendation-card__status">{t(recommendationStatusKey(recommendation.status))}</p>

      {hasRange ? (
        <div className="recommendation-card__ranges">
          <div>
            <span className="recommendation-card__range-label">{t("recommendation.perHectare")}</span>
            <strong>
              {formatMm(recommendation.recommended_min_mm)} – {formatMm(recommendation.recommended_max_mm)}
            </strong>
          </div>
          <div>
            <span className="recommendation-card__range-label">{t("recommendation.perHectareVolume")}</span>
            <strong>
              {formatM3(recommendation.recommended_min_m3_per_ha)} –{" "}
              {formatM3(recommendation.recommended_max_m3_per_ha)}
            </strong>
          </div>
          <div>
            <span className="recommendation-card__range-label">{t("recommendation.totalField")}</span>
            <strong>
              {formatM3(recommendation.total_min_volume_m3)} – {formatM3(recommendation.total_max_volume_m3)}
            </strong>
          </div>
          {recommendation.window_start_date ? (
            <div>
              <span className="recommendation-card__range-label">{t("recommendation.window")}</span>
              <strong>
                {formatDate(recommendation.window_start_date)} – {formatDate(recommendation.window_end_date)}
              </strong>
            </div>
          ) : null}
        </div>
      ) : null}

      {recommendation.reasons.length > 0 ? (
        <div>
          <h3>{t("recommendation.reasons")}</h3>
          <ul>
            {recommendation.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {recommendation.warnings.length > 0 ? (
        <div className="alert alert--warning">
          <h3>{t("recommendation.warnings")}</h3>
          <ul>
            {recommendation.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="field-hint">
        {t("recommendation.methodologyVersion")}: {methodologyVersion} · {t("recommendation.analysisDate")}:{" "}
        {formatDate(analysisDate)}
      </p>
    </section>
  );
}
