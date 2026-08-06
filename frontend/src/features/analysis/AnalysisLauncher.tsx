import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useHealth, useIrrigationEvents, useRunAnalysis } from "../../api/hooks";
import { ApiErrorPanel } from "../../components/feedback/ApiErrorPanel";
import { DataModeBadge } from "../../components/layout/DataModeBadge";
import { formatDate, formatDateTime, todayIsoDate } from "../../utils/format";
import type { AnalysisResponse, FieldRead } from "../../types/api";

export function AnalysisLauncher({
  field,
  onAnalysisComplete,
}: {
  field: FieldRead;
  onAnalysisComplete: (analysis: AnalysisResponse) => void;
}) {
  const { t } = useTranslation();
  const health = useHealth();
  const irrigations = useIrrigationEvents(field.id);
  const runAnalysis = useRunAnalysis(field.id);
  const [analysisDate, setAnalysisDate] = useState(todayIsoDate());
  const abortControllerRef = useRef<AbortController | null>(null);

  const lastIrrigation = irrigations.data?.items[irrigations.data.items.length - 1] ?? null;

  function handleRun() {
    if (runAnalysis.isPending) return;
    const controller = new AbortController();
    abortControllerRef.current = controller;
    runAnalysis.mutate(
      { body: { analysis_date: analysisDate }, signal: controller.signal },
      { onSuccess: onAnalysisComplete }
    );
  }

  function handleCancel() {
    abortControllerRef.current?.abort();
  }

  const isAbortError = runAnalysis.error instanceof DOMException && runAnalysis.error.name === "AbortError";

  return (
    <section className="card">
      <h2>{t("analysisLauncher.title")}</h2>
      <dl className="field-summary-card__facts">
        <div>
          <dt>{t("field.cropType")}</dt>
          <dd>{t(`cropType.${field.crop_type}`, field.crop_type)}</dd>
        </div>
        <div>
          <dt>{t("field.plantingDate")}</dt>
          <dd>{formatDate(field.planting_date)}</dd>
        </div>
        <div>
          <dt>{t("analysisLauncher.lastIrrigation")}</dt>
          <dd>{lastIrrigation ? formatDateTime(lastIrrigation.occurred_at) : t("field.noIrrigationEvents")}</dd>
        </div>
        <div>
          <dt>{t("dataSource.title")}</dt>
          <dd>{health.data ? <DataModeBadge mode={health.data.data_mode} /> : "—"}</dd>
        </div>
      </dl>

      {health.data?.data_mode === "live" ? (
        <p className="alert alert--info">{t("analysisLauncher.liveModeNotice")}</p>
      ) : null}

      <div className="field">
        <label htmlFor="analysis_date">{t("analysisLauncher.analysisDate")}</label>
        <input
          id="analysis_date"
          type="date"
          value={analysisDate}
          onChange={(event) => setAnalysisDate(event.target.value)}
        />
      </div>

      {runAnalysis.error && !isAbortError ? <ApiErrorPanel error={runAnalysis.error} /> : null}

      <div className="row">
        <button className="button" type="button" onClick={handleRun} disabled={runAnalysis.isPending}>
          {runAnalysis.isPending ? t("analysisLauncher.running") : t("analysisLauncher.run")}
        </button>
        {runAnalysis.isPending ? (
          <button className="button button--secondary" type="button" onClick={handleCancel}>
            {t("common.cancel")}
          </button>
        ) : null}
      </div>
    </section>
  );
}
