import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useCreateIrrigationEvent } from "../../api/hooks";
import { ApiErrorPanel } from "../../components/feedback/ApiErrorPanel";
import { todayIsoDate } from "../../utils/format";
import type { IrrigationEventCreate, IrrigationEventRead, QualitativeAmount } from "../../types/api";

const RECENT_WINDOW_DAYS = 30;
const QUALITATIVE_OPTIONS: QualitativeAmount[] = ["little", "moderate", "a_lot"];

function daysSince(isoDateTime: string): number {
  const then = new Date(isoDateTime).getTime();
  const now = Date.now();
  return (now - then) / (1000 * 60 * 60 * 24);
}

/**
 * Simple pre-analysis prompt: "Oxirgi 30 kun ichida dala sug'orildimi?"
 * The water balance is highly dependent on recent irrigation history (see
 * CLAUDE.md / docs/methodology.md), so this surfaces the gap before a
 * farmer runs an analysis rather than only after, in the result warnings.
 *
 * Reuses the existing irrigation-event API (useCreateIrrigationEvent, the
 * same mutation IrrigationNewPage uses) — this is a reduced-field quick
 * entry point for the common case, not a parallel mechanism. The full
 * form (duration/volume/flow-rate/measured value_source/notes) stays
 * available from the field page for anyone who wants it.
 */
export function RecentIrrigationPrompt({
  fieldId,
  lastIrrigation,
}: {
  fieldId: number;
  lastIrrigation: IrrigationEventRead | null;
}) {
  const { t } = useTranslation();
  const createEvent = useCreateIrrigationEvent(fieldId);
  const [answer, setAnswer] = useState<"yes" | "no" | null>(null);
  const [occurredAt, setOccurredAt] = useState(todayIsoDate());
  const [amountMm, setAmountMm] = useState("");
  const [durationMinutes, setDurationMinutes] = useState("");
  const [qualitative, setQualitative] = useState<QualitativeAmount | "unknown" | "">("");

  const hasRecentRecord = lastIrrigation !== null && daysSince(lastIrrigation.occurred_at) <= RECENT_WINDOW_DAYS;

  // Already covered by an on-file record within the window — nothing to
  // ask, nothing to warn about.
  if (hasRecentRecord) return null;

  if (createEvent.isSuccess) {
    return <p className="alert alert--info">{t("recentIrrigation.recorded")}</p>;
  }

  if (answer === null) {
    return (
      <div className="card">
        <p>{t("recentIrrigation.question")}</p>
        <div className="row">
          <button type="button" className="button button--secondary" onClick={() => setAnswer("yes")}>
            {t("common.yes")}
          </button>
          <button type="button" className="button button--secondary" onClick={() => setAnswer("no")}>
            {t("common.no")}
          </button>
        </div>
      </div>
    );
  }

  if (answer === "no") {
    return <p className="alert alert--warning">{t("recentIrrigation.noneWarning")}</p>;
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const payload: IrrigationEventCreate = {
      occurred_at: occurredAt,
      duration_minutes: durationMinutes ? Number(durationMinutes) : null,
      amount_mm: amountMm ? Number(amountMm) : null,
      total_volume_m3: null,
      flow_rate_m3_hour: null,
      qualitative_amount: qualitative && qualitative !== "unknown" ? qualitative : null,
      value_source: "farmer_estimate",
      notes: null,
    };
    createEvent.mutate(payload);
  }

  const canSubmit = Boolean(amountMm || durationMinutes || (qualitative && qualitative !== "unknown"));

  return (
    <form className="card stack" onSubmit={submit}>
      <p className="field-hint">{t("recentIrrigation.measuredHint")}</p>
      <div className="field">
        <label htmlFor="recent_irrigation_date">{t("irrigation.occurredAt")}</label>
        <input
          id="recent_irrigation_date"
          type="date"
          value={occurredAt}
          max={todayIsoDate()}
          onChange={(e) => setOccurredAt(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="recent_irrigation_amount">{t("irrigation.amountMm")}</label>
        <input
          id="recent_irrigation_amount"
          type="number"
          min="0"
          step="0.1"
          value={amountMm}
          onChange={(e) => setAmountMm(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="recent_irrigation_duration">{t("irrigation.durationMinutes")}</label>
        <input
          id="recent_irrigation_duration"
          type="number"
          min="1"
          step="1"
          value={durationMinutes}
          onChange={(e) => setDurationMinutes(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="recent_irrigation_qualitative">{t("recentIrrigation.approxAmount")}</label>
        <select
          id="recent_irrigation_qualitative"
          value={qualitative}
          onChange={(e) => setQualitative(e.target.value as QualitativeAmount | "unknown" | "")}
        >
          <option value="">{t("common.selectOption")}</option>
          {QUALITATIVE_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {t(`irrigation.qualitativeAmount.${option}`)}
            </option>
          ))}
          <option value="unknown">{t("recentIrrigation.unknownAmount")}</option>
        </select>
      </div>

      {qualitative === "unknown" && !amountMm && !durationMinutes ? (
        <p className="field-hint">{t("recentIrrigation.unknownAmountHint")}</p>
      ) : null}

      {createEvent.error ? <ApiErrorPanel error={createEvent.error} /> : null}

      <button className="button" type="submit" disabled={!canSubmit || createEvent.isPending}>
        {createEvent.isPending ? t("common.saving") : t("recentIrrigation.save")}
      </button>
    </form>
  );
}
