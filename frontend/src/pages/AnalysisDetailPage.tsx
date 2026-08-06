import { Link, Navigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAnalysis } from "../api/hooks";
import { ApiErrorPanel } from "../components/feedback/ApiErrorPanel";
import { Loading } from "../components/feedback/Loading";
import { AnalysisResultView } from "../features/analysis/AnalysisResultView";

export function AnalysisDetailPage() {
  const { t } = useTranslation();
  const { fieldId, analysisId } = useParams<{ fieldId: string; analysisId: string }>();
  const parsedFieldId = fieldId ? Number(fieldId) : NaN;
  const parsedAnalysisId = analysisId ? Number(analysisId) : NaN;
  const validFieldId = Number.isFinite(parsedFieldId) ? parsedFieldId : null;
  const validAnalysisId = Number.isFinite(parsedAnalysisId) ? parsedAnalysisId : null;

  const analysis = useAnalysis(validFieldId, validAnalysisId);

  if (validFieldId === null || validAnalysisId === null) {
    return <Navigate to="/not-found" replace />;
  }

  return (
    <div className="container stack">
      <div className="row">
        <h1>{t("analysisDetail.title")}</h1>
        <Link to={`/fields/${validFieldId}/analyses`}>{t("analysisHistory.viewAll")}</Link>
      </div>

      {analysis.isLoading ? <Loading /> : null}
      {analysis.error ? <ApiErrorPanel error={analysis.error} /> : null}
      {analysis.data ? <AnalysisResultView analysis={analysis.data} /> : null}
    </div>
  );
}
