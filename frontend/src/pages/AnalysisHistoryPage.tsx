import { Link, Navigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAnalyses, useField } from "../api/hooks";
import { ApiErrorPanel } from "../components/feedback/ApiErrorPanel";
import { EmptyState, Loading } from "../components/feedback/Loading";
import { formatDate } from "../utils/format";
import { confidenceCategoryKey, recommendationStatusKey } from "../utils/labels";

export function AnalysisHistoryPage() {
  const { t } = useTranslation();
  const { fieldId } = useParams<{ fieldId: string }>();
  const parsedFieldId = fieldId ? Number(fieldId) : NaN;
  const validId = Number.isFinite(parsedFieldId) ? parsedFieldId : null;

  const field = useField(validId);
  const analysesList = useAnalyses(validId);

  if (!Number.isFinite(parsedFieldId)) {
    return <Navigate to="/not-found" replace />;
  }

  return (
    <div className="container">
      <h1>{t("analysisHistory.title")}</h1>
      {field.data ? <p className="field-hint">{field.data.name}</p> : null}

      {analysesList.isLoading ? <Loading /> : null}
      {analysesList.error ? <ApiErrorPanel error={analysesList.error} /> : null}

      {analysesList.data && analysesList.data.items.length === 0 ? (
        <EmptyState titleKey="field.noAnalysesYet" />
      ) : null}

      {analysesList.data && analysesList.data.items.length > 0 ? (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("analysisHistory.date")}</th>
                <th>{t("analysisHistory.status")}</th>
                <th>{t("analysisHistory.confidence")}</th>
                <th>{t("analysisHistory.dataMode")}</th>
              </tr>
            </thead>
            <tbody>
              {analysesList.data.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link to={`/fields/${parsedFieldId}/analyses/${item.id}`}>
                      {formatDate(item.analysis_date)}
                    </Link>
                  </td>
                  <td>{t(recommendationStatusKey(item.status))}</td>
                  <td>{t(confidenceCategoryKey(item.confidence_category))}</td>
                  <td>{item.data_mode}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
