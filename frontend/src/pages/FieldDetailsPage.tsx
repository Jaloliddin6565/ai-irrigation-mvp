import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAnalyses, useDeleteField, useField, useIrrigationEvents } from "../api/hooks";
import { ApiErrorPanel } from "../components/feedback/ApiErrorPanel";
import { EmptyState, Loading } from "../components/feedback/Loading";
import { FieldMap } from "../components/map/FieldMap";
import { useActiveFarmer } from "../features/farmer/ActiveFarmerContext";
import { formatDate, formatDateTime, formatHectares, formatMm } from "../utils/format";
import { qualitativeAmountKey, recommendationStatusKey, valueSourceKey } from "../utils/labels";
import "./FieldDetailsPage.css";

export function FieldDetailsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { fieldId } = useParams<{ fieldId: string }>();
  const parsedFieldId = fieldId ? Number(fieldId) : NaN;
  const validId = Number.isFinite(parsedFieldId) ? parsedFieldId : null;

  const { activeFarmerId } = useActiveFarmer();
  const field = useField(validId);
  const irrigations = useIrrigationEvents(validId);
  const analysesList = useAnalyses(validId);
  const deleteField = useDeleteField(activeFarmerId ?? -1);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  if (!Number.isFinite(parsedFieldId)) {
    return <Navigate to="/not-found" replace />;
  }

  return (
    <div className="container">
      {field.isLoading ? <Loading /> : null}
      {field.error ? <ApiErrorPanel error={field.error} /> : null}

      {field.data ? (
        <>
          <div className="row field-details__header">
            <h1>{field.data.name}</h1>
            <div className="row">
              <Link className="button button--secondary" to={`/fields/${field.data.id}/edit`}>
                {t("field.edit")}
              </Link>
              <Link className="button" to={`/fields/${field.data.id}/analysis`}>
                {t("field.runAnalysis")}
              </Link>
            </div>
          </div>

          <FieldMap polygon={field.data.geojson_polygon} />

          <section className="card">
            <h2>{t("field.detailsTitle")}</h2>
            <dl className="field-summary-card__facts">
              <div>
                <dt>{t("field.area")}</dt>
                <dd>{formatHectares(field.data.area_hectares)}</dd>
              </div>
              <div>
                <dt>{t("field.cropType")}</dt>
                <dd>{t(`cropType.${field.data.crop_type}`, field.data.crop_type)}</dd>
              </div>
              <div>
                <dt>{t("field.plantingDate")}</dt>
                <dd>{formatDate(field.data.planting_date)}</dd>
              </div>
              <div>
                <dt>{t("field.irrigationMethod")}</dt>
                <dd>{t(`irrigationMethod.${field.data.irrigation_method}`, field.data.irrigation_method)}</dd>
              </div>
              <div>
                <dt>{t("field.soilTexture")}</dt>
                <dd>{t(`soilTexture.${field.data.soil_texture}`, field.data.soil_texture)}</dd>
              </div>
              {field.data.expected_harvest_date ? (
                <div>
                  <dt>{t("field.expectedHarvestDate")}</dt>
                  <dd>{formatDate(field.data.expected_harvest_date)}</dd>
                </div>
              ) : null}
            </dl>
            {field.data.notes ? <p>{field.data.notes}</p> : null}
          </section>

          <section className="card">
            <div className="row field-details__section-header">
              <h2>{t("field.irrigationHistory")}</h2>
              <Link className="button button--secondary" to={`/fields/${field.data.id}/irrigations/new`}>
                {t("field.addIrrigation")}
              </Link>
            </div>
            {irrigations.isLoading ? <Loading /> : null}
            {irrigations.error ? <ApiErrorPanel error={irrigations.error} /> : null}
            {irrigations.data && irrigations.data.items.length === 0 ? (
              <EmptyState titleKey="field.noIrrigationEvents" />
            ) : null}
            {irrigations.data && irrigations.data.items.length > 0 ? (
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("irrigation.occurredAt")}</th>
                      <th>{t("irrigation.amountMm")}</th>
                      <th>{t("irrigation.qualitativeAmount")}</th>
                      <th>{t("irrigation.valueSource")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {irrigations.data.items.map((event) => (
                      <tr key={event.id}>
                        <td>{formatDateTime(event.occurred_at)}</td>
                        <td>{event.amount_mm !== null ? formatMm(event.amount_mm) : "—"}</td>
                        <td>
                          {event.qualitative_amount
                            ? t(qualitativeAmountKey(event.qualitative_amount))
                            : "—"}
                        </td>
                        <td>{t(valueSourceKey(event.value_source))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>

          <section className="card">
            <div className="row field-details__section-header">
              <h2>{t("field.analysisHistory")}</h2>
              <Link className="button button--secondary" to={`/fields/${field.data.id}/analyses`}>
                {t("analysisHistory.viewAll")}
              </Link>
            </div>
            {analysesList.isLoading ? <Loading /> : null}
            {analysesList.error ? <ApiErrorPanel error={analysesList.error} /> : null}
            {analysesList.data && analysesList.data.items.length === 0 ? (
              <EmptyState titleKey="field.noAnalysesYet" />
            ) : null}
            {analysesList.data && analysesList.data.items.length > 0 ? (
              <ul>
                {analysesList.data.items.slice(0, 5).map((item) => (
                  <li key={item.id}>
                    <Link to={`/fields/${field.data.id}/analyses/${item.id}`}>
                      {formatDate(item.analysis_date)} — {t(recommendationStatusKey(item.status))}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          <section className="card">
            <h2>{t("field.dangerZone")}</h2>
            {!confirmingDelete ? (
              <button
                type="button"
                className="button button--danger"
                onClick={() => setConfirmingDelete(true)}
              >
                {t("field.delete")}
              </button>
            ) : (
              <div className="row">
                <p>{t("field.deleteConfirm")}</p>
                <button
                  type="button"
                  className="button button--danger"
                  disabled={deleteField.isPending}
                  onClick={() =>
                    deleteField.mutate(field.data.id, {
                      onSuccess: () => void navigate("/dashboard"),
                    })
                  }
                >
                  {t("field.deleteConfirmYes")}
                </button>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setConfirmingDelete(false)}
                >
                  {t("common.cancel")}
                </button>
              </div>
            )}
            {deleteField.error ? <ApiErrorPanel error={deleteField.error} /> : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
