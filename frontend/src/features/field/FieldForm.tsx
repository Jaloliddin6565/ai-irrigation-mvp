import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { useConfigOptions } from "../../api/hooks";
import { ApiErrorPanel } from "../../components/feedback/ApiErrorPanel";
import { Loading } from "../../components/feedback/Loading";
import { PolygonEditor } from "../../components/map/PolygonEditor";
import { formatHectares } from "../../utils/format";
import { approxPolygonAreaHectares } from "../../utils/geo";
import type { FieldCreate, FieldRead, GeoJsonPolygon } from "../../types/api";

const fieldSchema = z
  .object({
    name: z.string().trim().min(1).max(200),
    crop_type: z.string().min(1),
    crop_variety: z.string().trim().max(100).optional(),
    planting_date: z.string().min(1),
    expected_harvest_date: z.string().optional(),
    crop_stage_override: z.string().optional(),
    irrigation_method: z.string().min(1),
    soil_texture: z.string().min(1),
    root_depth_override: z.string().optional(),
    field_capacity_override: z.string().optional(),
    wilting_point_override: z.string().optional(),
    notes: z.string().trim().max(2000).optional(),
  })
  .refine(
    (values) =>
      !values.expected_harvest_date || values.expected_harvest_date > values.planting_date,
    { message: "harvest_before_planting", path: ["expected_harvest_date"] }
  )
  .refine(
    (values) => {
      if (!values.field_capacity_override || !values.wilting_point_override) return true;
      return Number(values.field_capacity_override) > Number(values.wilting_point_override);
    },
    { message: "fc_not_greater_than_wp", path: ["field_capacity_override"] }
  );

type FieldFormValues = z.infer<typeof fieldSchema>;

function toOptionalNumber(value: string | undefined): number | null | undefined {
  if (value === undefined || value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export type FieldFormSubmitValues = FieldCreate;

export function FieldForm({
  initial,
  submitLabelKey,
  isSubmitting,
  submitError,
  onSubmit,
}: {
  initial?: FieldRead;
  submitLabelKey: string;
  isSubmitting: boolean;
  submitError: unknown;
  onSubmit: (values: FieldFormSubmitValues) => void;
}) {
  const { t } = useTranslation();
  const configOptions = useConfigOptions();
  const [polygon, setPolygon] = useState<GeoJsonPolygon | null>(initial?.geojson_polygon ?? null);
  const [approxArea, setApproxArea] = useState<number | null>(
    initial ? approxPolygonAreaHectares(initial.geojson_polygon) : null
  );
  const [polygonTouched, setPolygonTouched] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FieldFormValues>({
    resolver: zodResolver(fieldSchema),
    defaultValues: initial
      ? {
          name: initial.name,
          crop_type: initial.crop_type,
          crop_variety: initial.crop_variety ?? "",
          planting_date: initial.planting_date,
          expected_harvest_date: initial.expected_harvest_date ?? "",
          crop_stage_override: initial.crop_stage_override ?? "",
          irrigation_method: initial.irrigation_method,
          soil_texture: initial.soil_texture,
          root_depth_override: initial.root_depth_override?.toString() ?? "",
          field_capacity_override: initial.field_capacity_override?.toString() ?? "",
          wilting_point_override: initial.wilting_point_override?.toString() ?? "",
          notes: initial.notes ?? "",
        }
      : undefined,
  });

  if (configOptions.isLoading) return <Loading />;
  if (configOptions.error) return <ApiErrorPanel error={configOptions.error} />;
  if (!configOptions.data) return null;

  const submit = handleSubmit((values) => {
    setPolygonTouched(true);
    if (!polygon) return;

    onSubmit({
      farmer_id: initial?.farmer_id ?? 0,
      name: values.name,
      geojson_polygon: polygon,
      crop_type: values.crop_type as FieldCreate["crop_type"],
      crop_variety: values.crop_variety ? values.crop_variety : null,
      planting_date: values.planting_date,
      expected_harvest_date: values.expected_harvest_date ? values.expected_harvest_date : null,
      crop_stage_override: values.crop_stage_override
        ? (values.crop_stage_override as FieldCreate["crop_stage_override"])
        : null,
      irrigation_method: values.irrigation_method as FieldCreate["irrigation_method"],
      soil_texture: values.soil_texture as FieldCreate["soil_texture"],
      root_depth_override: toOptionalNumber(values.root_depth_override),
      field_capacity_override: toOptionalNumber(values.field_capacity_override),
      wilting_point_override: toOptionalNumber(values.wilting_point_override),
      notes: values.notes ? values.notes : null,
    });
  });

  return (
    <form className="stack" onSubmit={submit} noValidate>
      <section className="card">
        <h2>{t("field.sectionBasic")}</h2>
        <div className="field">
          <label htmlFor="name">{t("field.name")}</label>
          <input id="name" {...register("name")} />
          {errors.name ? <span className="field-error">{t("field.errors.name")}</span> : null}
        </div>
      </section>

      <section className="card">
        <h2>{t("field.sectionPolygon")}</h2>
        <PolygonEditor
          value={polygon}
          onChange={(next, area) => {
            setPolygon(next);
            setApproxArea(area);
            setPolygonTouched(true);
          }}
        />
        {approxArea !== null ? (
          <p className="field-hint">
            {t("field.approxArea")}: {formatHectares(approxArea)} ({t("field.approxAreaNotice")})
          </p>
        ) : null}
        {polygonTouched && !polygon ? (
          <span className="field-error">{t("field.errors.polygon")}</span>
        ) : null}
      </section>

      <section className="card">
        <h2>{t("field.sectionCrop")}</h2>
        <div className="field">
          <label htmlFor="crop_type">{t("field.cropType")}</label>
          <select id="crop_type" {...register("crop_type")}>
            <option value="" disabled>
              {t("common.selectOption")}
            </option>
            {Object.entries(configOptions.data.crops).map(([key, entry]) => (
              <option key={key} value={key}>
                {entry.label_uz}
              </option>
            ))}
          </select>
          {errors.crop_type ? (
            <span className="field-error">{t("field.errors.cropType")}</span>
          ) : null}
        </div>
        <div className="field">
          <label htmlFor="crop_variety">{t("field.cropVariety")}</label>
          <input id="crop_variety" {...register("crop_variety")} />
        </div>
        <div className="field">
          <label htmlFor="planting_date">{t("field.plantingDate")}</label>
          <input id="planting_date" type="date" {...register("planting_date")} />
          {errors.planting_date ? (
            <span className="field-error">{t("field.errors.plantingDate")}</span>
          ) : null}
        </div>
        <div className="field">
          <label htmlFor="expected_harvest_date">{t("field.expectedHarvestDate")}</label>
          <input id="expected_harvest_date" type="date" {...register("expected_harvest_date")} />
          {errors.expected_harvest_date ? (
            <span className="field-error">{t("field.errors.harvestDate")}</span>
          ) : null}
        </div>
        <div className="field">
          <label htmlFor="crop_stage_override">{t("field.cropStageOverride")}</label>
          <select id="crop_stage_override" {...register("crop_stage_override")}>
            <option value="">{t("common.none")}</option>
            <option value="initial">{t("cropStage.initial")}</option>
            <option value="development">{t("cropStage.development")}</option>
            <option value="mid">{t("cropStage.mid")}</option>
            <option value="late">{t("cropStage.late")}</option>
          </select>
        </div>
      </section>

      <section className="card">
        <h2>{t("field.sectionAgronomy")}</h2>
        <div className="field">
          <label htmlFor="irrigation_method">{t("field.irrigationMethod")}</label>
          <select id="irrigation_method" {...register("irrigation_method")}>
            <option value="" disabled>
              {t("common.selectOption")}
            </option>
            {Object.entries(configOptions.data.irrigation_methods).map(([key, entry]) => (
              <option key={key} value={key}>
                {entry.label_uz}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="soil_texture">{t("field.soilTexture")}</label>
          <select id="soil_texture" {...register("soil_texture")}>
            <option value="" disabled>
              {t("common.selectOption")}
            </option>
            {Object.entries(configOptions.data.soils).map(([key, entry]) => (
              <option key={key} value={key}>
                {entry.label_uz}
              </option>
            ))}
          </select>
        </div>
        <p className="field-hint">{t("field.overridesHint")}</p>
        <div className="field">
          <label htmlFor="root_depth_override">{t("field.rootDepthOverride")}</label>
          <input id="root_depth_override" type="number" step="0.1" min="0" max="5" {...register("root_depth_override")} />
        </div>
        <div className="field">
          <label htmlFor="field_capacity_override">{t("field.fieldCapacityOverride")}</label>
          <input
            id="field_capacity_override"
            type="number"
            step="0.01"
            min="0"
            max="1"
            {...register("field_capacity_override")}
          />
        </div>
        <div className="field">
          <label htmlFor="wilting_point_override">{t("field.wiltingPointOverride")}</label>
          <input
            id="wilting_point_override"
            type="number"
            step="0.01"
            min="0"
            max="1"
            {...register("wilting_point_override")}
          />
          {errors.field_capacity_override ? (
            <span className="field-error">{t("field.errors.fcGtWp")}</span>
          ) : null}
        </div>
        <div className="field">
          <label htmlFor="notes">{t("field.notes")}</label>
          <textarea id="notes" {...register("notes")} />
        </div>
      </section>

      {submitError ? <ApiErrorPanel error={submitError} /> : null}

      <button className="button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? t("common.saving") : t(submitLabelKey)}
      </button>
    </form>
  );
}
