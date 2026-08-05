import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate, useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { useCreateIrrigationEvent, useField } from "../api/hooks";
import { ApiErrorPanel } from "../components/feedback/ApiErrorPanel";
import { Loading } from "../components/feedback/Loading";
import type { IrrigationEventCreate } from "../types/api";

function defaultLocalDateTime(): string {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

const irrigationSchema = z
  .object({
    occurred_at: z.string().min(1),
    duration_minutes: z.string().optional(),
    amount_mm: z.string().optional(),
    total_volume_m3: z.string().optional(),
    flow_rate_m3_hour: z.string().optional(),
    qualitative_amount: z.string().optional(),
    value_source: z.enum(["measured", "farmer_estimate"]),
    notes: z.string().trim().max(2000).optional(),
  })
  .refine(
    (values) =>
      Boolean(
        values.duration_minutes ||
          values.amount_mm ||
          values.total_volume_m3 ||
          values.flow_rate_m3_hour ||
          values.qualitative_amount
      ),
    { message: "at_least_one_amount", path: ["amount_mm"] }
  );

type IrrigationFormValues = z.infer<typeof irrigationSchema>;

function toPositiveNumber(value: string | undefined): number | null {
  if (!value || value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function IrrigationNewPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { fieldId } = useParams<{ fieldId: string }>();
  const parsedFieldId = fieldId ? Number(fieldId) : NaN;
  const field = useField(Number.isFinite(parsedFieldId) ? parsedFieldId : null);
  const createEvent = useCreateIrrigationEvent(parsedFieldId);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<IrrigationFormValues>({
    resolver: zodResolver(irrigationSchema),
    defaultValues: { occurred_at: defaultLocalDateTime(), value_source: "farmer_estimate" },
  });

  const submit = handleSubmit((values) => {
    const payload: IrrigationEventCreate = {
      occurred_at: values.occurred_at,
      duration_minutes: values.duration_minutes ? Number(values.duration_minutes) : null,
      amount_mm: toPositiveNumber(values.amount_mm),
      total_volume_m3: toPositiveNumber(values.total_volume_m3),
      flow_rate_m3_hour: toPositiveNumber(values.flow_rate_m3_hour),
      qualitative_amount: values.qualitative_amount
        ? (values.qualitative_amount as IrrigationEventCreate["qualitative_amount"])
        : null,
      value_source: values.value_source,
      notes: values.notes ? values.notes : null,
    };
    createEvent.mutate(payload, {
      onSuccess: () => void navigate(`/fields/${parsedFieldId}`),
    });
  });

  return (
    <div className="container">
      <h1>{t("irrigation.newTitle")}</h1>
      {field.data ? <p className="field-hint">{field.data.name}</p> : null}
      {field.isLoading ? <Loading /> : null}

      <form className="card" onSubmit={submit} noValidate>
        <p className="field-hint">{t("irrigation.measuredNotice")}</p>

        <div className="field">
          <label htmlFor="occurred_at">{t("irrigation.occurredAt")}</label>
          <input id="occurred_at" type="datetime-local" {...register("occurred_at")} />
          {errors.occurred_at ? (
            <span className="field-error">{t("irrigation.errors.occurredAt")}</span>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="duration_minutes">{t("irrigation.durationMinutes")}</label>
          <input id="duration_minutes" type="number" min="1" step="1" {...register("duration_minutes")} />
        </div>

        <div className="field">
          <label htmlFor="amount_mm">{t("irrigation.amountMm")}</label>
          <input id="amount_mm" type="number" min="0" step="0.1" {...register("amount_mm")} />
          <span className="field-hint">{t("irrigation.amountMmHint")}</span>
        </div>

        <div className="field">
          <label htmlFor="total_volume_m3">{t("irrigation.totalVolumeM3")}</label>
          <input id="total_volume_m3" type="number" min="0" step="1" {...register("total_volume_m3")} />
        </div>

        <div className="field">
          <label htmlFor="flow_rate_m3_hour">{t("irrigation.flowRate")}</label>
          <input id="flow_rate_m3_hour" type="number" min="0" step="0.1" {...register("flow_rate_m3_hour")} />
        </div>

        <div className="field">
          <label htmlFor="qualitative_amount">{t("irrigation.qualitativeAmount")}</label>
          <select id="qualitative_amount" {...register("qualitative_amount")}>
            <option value="">{t("common.none")}</option>
            <option value="little">{t("irrigation.qualitativeAmountOption.little")}</option>
            <option value="moderate">{t("irrigation.qualitativeAmountOption.moderate")}</option>
            <option value="a_lot">{t("irrigation.qualitativeAmountOption.a_lot")}</option>
          </select>
        </div>

        {errors.amount_mm?.message === "at_least_one_amount" ? (
          <span className="field-error">{t("irrigation.errors.atLeastOneAmount")}</span>
        ) : null}

        <div className="field">
          <label htmlFor="value_source">{t("irrigation.valueSource")}</label>
          <select id="value_source" {...register("value_source")}>
            <option value="measured">{t("irrigation.valueSourceOption.measured")}</option>
            <option value="farmer_estimate">{t("irrigation.valueSourceOption.farmer_estimate")}</option>
          </select>
        </div>

        <div className="field">
          <label htmlFor="notes">{t("irrigation.notes")}</label>
          <textarea id="notes" {...register("notes")} />
        </div>

        {createEvent.error ? <ApiErrorPanel error={createEvent.error} /> : null}

        <button className="button" type="submit" disabled={createEvent.isPending}>
          {createEvent.isPending ? t("common.saving") : t("irrigation.submit")}
        </button>
      </form>
    </div>
  );
}
