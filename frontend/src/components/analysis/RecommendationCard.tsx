import { useTranslation } from "react-i18next";

import "./RecommendationCard.css";
import { CollapsibleSection } from "../disclosure/CollapsibleSection";
import { formatDate, formatM3, formatMm } from "../../utils/format";
import { messageCodeKey, recommendationStatusKey } from "../../utils/labels";
import type { MessageCode, RecommendationSchema } from "../../types/api";

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

  function translateMessage(message: MessageCode): string {
    return t(messageCodeKey(message.code), message.params);
  }

  // Pulled out of reason_codes to show as its own "why is the range this
  // wide" line, right next to the range it explains, rather than buried in
  // the general reasons list below.
  const rangeWidthReason = recommendation.reason_codes.find(
    (message) => message.code === "confidence_range_widened"
  );
  const otherReasonCodes = recommendation.reason_codes.filter(
    (message) => message.code !== "confidence_range_widened"
  );

  return (
    <section className={`card recommendation-card recommendation-card--${tone}`}>
      <p className="recommendation-card__status">{t(recommendationStatusKey(recommendation.status))}</p>

      {hasRange ? (
        <div className="recommendation-card__ranges">
          {recommendation.depletion_mm !== null ? (
            <div>
              <span className="recommendation-card__range-label">{t("recommendation.netDeficit")}</span>
              <strong>{formatMm(recommendation.depletion_mm)}</strong>
            </div>
          ) : null}
          {recommendation.base_gross_mm !== null ? (
            <div>
              <span className="recommendation-card__range-label">
                {t("recommendation.grossApplication")}
              </span>
              <strong>{formatMm(recommendation.base_gross_mm)}</strong>
            </div>
          ) : null}
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

      {rangeWidthReason ? (
        <p className="field-hint">
          <strong>{t("recommendation.uncertaintyRangeTitle")}:</strong> {translateMessage(rangeWidthReason)}
        </p>
      ) : null}

      {otherReasonCodes.length > 0 ? (
        <div>
          <h3>{t("recommendation.reasons")}</h3>
          <ul>
            {otherReasonCodes.map((message, index) => (
              <li key={`${message.code}-${index}`}>{translateMessage(message)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {recommendation.warning_codes.length > 0 ? (
        <div className="alert alert--warning">
          <h3>{t("recommendation.warnings")}</h3>
          <ul>
            {recommendation.warning_codes.map((message, index) => (
              <li key={`${message.code}-${index}`}>{translateMessage(message)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {recommendation.reasons.length > 0 || recommendation.warnings.length > 0 ? (
        <CollapsibleSection title={t("recommendation.technicalDetails")}>
          {recommendation.reasons.length > 0 ? (
            <ul>
              {recommendation.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
          {recommendation.warnings.length > 0 ? (
            <ul>
              {recommendation.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : null}
        </CollapsibleSection>
      ) : null}

      <p className="field-hint">
        {t("recommendation.methodologyVersion")}: {methodologyVersion} · {t("recommendation.analysisDate")}:{" "}
        {formatDate(analysisDate)}
      </p>
    </section>
  );
}
