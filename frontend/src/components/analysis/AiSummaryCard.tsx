import { useTranslation } from "react-i18next";

import "./AiSummaryCard.css";
import { CollapsibleSection } from "../disclosure/CollapsibleSection";
import {
  aiAgreementKey,
  aiDataBasisKey,
  aiValidationStatusKey,
  aiWetnessCategoryKey,
  confidenceCategoryKey,
} from "../../utils/labels";
import type { AISummary, ConfidenceCategory } from "../../types/api";

/**
 * Farmer-facing "AI tahlili" card. Primary view is deliberately limited to
 * the Uzbek category/badge presentation (wetness_index * 100, rounded, and
 * always labeled "AI namlik indeksi" — never "% soil moisture" or "measured
 * soil moisture", see CLAUDE.md rule 3). Model provenance/metrics live in a
 * collapsed "AI modeli haqida" section, matching ConfidenceCard's
 * primary/expert split.
 *
 * When ai_summary.status is "unavailable" this renders a plain info notice
 * instead of a broken/empty card — the primary FAO-56 recommendation
 * (RecommendationCard) is unaffected and rendered independently.
 */
export function AiSummaryCard({
  aiSummary,
  confidenceCategory,
}: {
  aiSummary: AISummary;
  confidenceCategory: ConfidenceCategory;
}) {
  const { t } = useTranslation();

  if (aiSummary.status !== "available" || aiSummary.wetness_index === null || aiSummary.wetness_category === null) {
    return (
      <section className="card ai-summary-card">
        <h2>{t("aiSummary.title")}</h2>
        <div className="alert alert--info">{t("aiSummary.unavailableBody")}</div>
      </section>
    );
  }

  const indexOn100 = Math.round(aiSummary.wetness_index * 100);

  return (
    <section className="card ai-summary-card">
      <h2>{t("aiSummary.title")}</h2>

      <p className="ai-summary-card__index">
        <span>{t("aiSummary.indexLabel")}:</span>
        <span className="ai-summary-card__index-value">{indexOn100}</span>
        <span className="ai-summary-card__index-unit">{t("aiSummary.indexUnit")}</span>
      </p>

      <div className="ai-summary-card__facts">
        <div className="ai-summary-card__fact">
          <span className="ai-summary-card__fact-label">{t("aiSummary.statusLabel")}:</span>
          <span className={`badge badge--wetness-${aiSummary.wetness_category}`}>
            {t(aiWetnessCategoryKey(aiSummary.wetness_category))}
          </span>
        </div>
        <div className="ai-summary-card__fact">
          <span className="ai-summary-card__fact-label">{t("aiSummary.agreementLabel")}:</span>
          <span className={`badge badge--agreement-${aiSummary.agreement_with_fao}`}>
            {t(aiAgreementKey(aiSummary.agreement_with_fao))}
          </span>
        </div>
        <div className="ai-summary-card__fact">
          <span className="ai-summary-card__fact-label">{t("aiSummary.confidenceLabel")}:</span>
          <span className={`badge badge--confidence-${confidenceCategory}`}>
            {t(confidenceCategoryKey(confidenceCategory))}
          </span>
        </div>
      </div>

      <p className="field-hint">{t(aiValidationStatusKey(aiSummary.validation_status))}</p>
      <p className="field-hint">
        {t("aiSummary.dataBasisLabel")}: {t(aiDataBasisKey(aiSummary.data_basis))}
      </p>

      <CollapsibleSection title={t("aiSummary.modelInfoTitle")}>
        <dl className="field-summary-card__facts ai-summary-card__model-info">
          <div>
            <dt>{t("aiSummary.modelInfoModelLabel")}</dt>
            <dd>{t("aiSummary.modelInfoModelValue")}</dd>
          </div>
          <div>
            <dt>{t("aiSummary.modelInfoTrainingLabel")}</dt>
            <dd>{t("aiSummary.modelInfoTrainingValue")}</dd>
          </div>
          <div>
            <dt>{t("aiSummary.modelInfoValidationLabel")}</dt>
            <dd>{t("aiSummary.modelInfoValidationValue")}</dd>
          </div>
          <div>
            <dt>{t("aiSummary.modelInfoMetricsLabel")}</dt>
            <dd>{t("aiSummary.modelInfoMetricsValue")}</dd>
          </div>
        </dl>
        <p className="field-hint">{t("aiSummary.modelInfoMetricsNotice")}</p>
        <p className="field-hint">{t("aiSummary.sensorRoadmap")}</p>
      </CollapsibleSection>
    </section>
  );
}
