import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAnalyses, useAnalysis } from "../../api/hooks";
import { confidenceCategoryKey, recommendationStatusKey } from "../../utils/labels";
import { formatDate, formatHectares } from "../../utils/format";
import type { FieldRead } from "../../types/api";

export function FieldSummaryCard({ field }: { field: FieldRead }) {
  const { t } = useTranslation();
  const analysesList = useAnalyses(field.id);
  const latestId = analysesList.data?.items[0]?.id ?? null;
  const latest = useAnalysis(field.id, latestId);

  return (
    <article className="card">
      <h3>{field.name}</h3>
      <dl className="field-summary-card__facts">
        <div>
          <dt>{t("field.crop")}</dt>
          <dd>{t(`cropType.${field.crop_type}`, field.crop_type)}</dd>
        </div>
        <div>
          <dt>{t("field.area")}</dt>
          <dd>{formatHectares(field.area_hectares)}</dd>
        </div>
        <div>
          <dt>{t("dashboard.lastAnalysisDate")}</dt>
          <dd>{latest.data ? formatDate(latest.data.analysis_date) : t("dashboard.noAnalysisYet")}</dd>
        </div>
        {latest.data ? (
          <>
            <div>
              <dt>{t("dashboard.recommendationStatus")}</dt>
              <dd>{t(recommendationStatusKey(latest.data.recommendation.status))}</dd>
            </div>
            <div>
              <dt>{t("dashboard.confidence")}</dt>
              <dd>{t(confidenceCategoryKey(latest.data.confidence.category))}</dd>
            </div>
            <div>
              <dt>{t("dashboard.latestSatelliteDate")}</dt>
              <dd>{formatDate(latest.data.satellite_summary.latest_observation_date)}</dd>
            </div>
          </>
        ) : null}
      </dl>
      <div className="row">
        <Link className="button button--secondary" to={`/fields/${field.id}`}>
          {t("dashboard.viewField")}
        </Link>
        <Link className="button" to={`/fields/${field.id}/analysis`}>
          {latest.data ? t("dashboard.viewResult") : t("dashboard.runAnalysis")}
        </Link>
      </div>
    </article>
  );
}
