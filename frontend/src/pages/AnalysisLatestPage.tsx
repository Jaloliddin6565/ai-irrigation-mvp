import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAnalyses, useAnalysis, useField } from "../api/hooks";
import { ApiErrorPanel } from "../components/feedback/ApiErrorPanel";
import { Loading } from "../components/feedback/Loading";
import { AnalysisLauncher } from "../features/analysis/AnalysisLauncher";
import { AnalysisResultView } from "../features/analysis/AnalysisResultView";
import type { AnalysisResponse } from "../types/api";

export function AnalysisLatestPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { fieldId } = useParams<{ fieldId: string }>();
  const parsedFieldId = fieldId ? Number(fieldId) : NaN;
  const validId = Number.isFinite(parsedFieldId) ? parsedFieldId : null;

  const field = useField(validId);
  const analysesList = useAnalyses(validId);
  const latestId = analysesList.data?.items[0]?.id ?? null;
  const latest = useAnalysis(validId, latestId);
  const [justCompleted, setJustCompleted] = useState<AnalysisResponse | null>(null);

  if (!Number.isFinite(parsedFieldId)) {
    return <Navigate to="/not-found" replace />;
  }

  const displayed = justCompleted ?? latest.data;

  return (
    <div className="container stack">
      <h1>{t("analysisLauncher.pageTitle")}</h1>

      {field.isLoading ? <Loading /> : null}
      {field.error ? <ApiErrorPanel error={field.error} /> : null}

      {field.data ? (
        <AnalysisLauncher
          field={field.data}
          onAnalysisComplete={(analysis) => {
            setJustCompleted(analysis);
            void navigate(`/fields/${parsedFieldId}/analyses/${analysis.id}`);
          }}
        />
      ) : null}

      {analysesList.isLoading ? <Loading /> : null}
      {analysesList.error ? <ApiErrorPanel error={analysesList.error} /> : null}
      {analysesList.data && analysesList.data.items.length === 0 && !justCompleted ? (
        <p className="field-hint">{t("analysisLauncher.noneYet")}</p>
      ) : null}

      {latest.isLoading ? <Loading /> : null}
      {latest.error ? <ApiErrorPanel error={latest.error} /> : null}
      {displayed ? <AnalysisResultView analysis={displayed} /> : null}
    </div>
  );
}
