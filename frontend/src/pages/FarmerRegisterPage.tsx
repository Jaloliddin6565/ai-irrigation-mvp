import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { useCreateFarmer } from "../api/hooks";
import { ApiError } from "../api/client";
import { ApiErrorPanel } from "../components/feedback/ApiErrorPanel";
import { useActiveFarmer } from "../features/farmer/ActiveFarmerContext";
import type { PreferredLanguage } from "../types/api";

const farmerSchema = z.object({
  full_name: z.string().trim().min(2).max(200),
  phone: z
    .string()
    .trim()
    .regex(/^\+?[1-9]\d{7,14}$/, "phone"),
  email: z.union([z.string().trim().email(), z.literal("")]).optional(),
  region: z.string().trim().min(2).max(100),
  district: z.string().trim().min(2).max(100),
  preferred_language: z.enum(["uz", "ru", "en"]),
});

type FarmerFormValues = z.infer<typeof farmerSchema>;

export function FarmerRegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setActiveFarmerId } = useActiveFarmer();
  const createFarmer = useCreateFarmer();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FarmerFormValues>({
    resolver: zodResolver(farmerSchema),
    defaultValues: { preferred_language: "uz" as PreferredLanguage },
  });

  const onSubmit = handleSubmit((values) => {
    createFarmer.mutate(
      {
        full_name: values.full_name,
        phone: values.phone,
        email: values.email ? values.email : null,
        region: values.region,
        district: values.district,
        preferred_language: values.preferred_language,
      },
      {
        onSuccess: (farmer) => {
          setActiveFarmerId(farmer.id);
          void navigate("/dashboard");
        },
      }
    );
  });

  const isPhoneConflict =
    createFarmer.error instanceof ApiError && createFarmer.error.code === "farmer_phone_conflict";

  return (
    <div className="container">
      <h1>{t("farmer.registerTitle")}</h1>
      <p className="field-hint">{t("farmer.registerIntro")}</p>

      <form className="card" onSubmit={onSubmit} noValidate>
        <div className="field">
          <label htmlFor="full_name">{t("farmer.fullName")}</label>
          <input
            id="full_name"
            autoComplete="name"
            aria-invalid={errors.full_name ? true : undefined}
            aria-describedby={errors.full_name ? "full_name-error" : undefined}
            {...register("full_name")}
          />
          {errors.full_name ? (
            <span id="full_name-error" className="field-error">
              {t("farmer.errors.fullName")}
            </span>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="phone">{t("farmer.phone")}</label>
          <input
            id="phone"
            autoComplete="tel"
            placeholder="+998901234567"
            aria-invalid={errors.phone || isPhoneConflict ? true : undefined}
            aria-describedby={errors.phone || isPhoneConflict ? "phone-error" : undefined}
            {...register("phone")}
          />
          {errors.phone ? (
            <span id="phone-error" className="field-error">
              {t("farmer.errors.phone")}
            </span>
          ) : null}
          {isPhoneConflict ? (
            <span id="phone-error" className="field-error">
              {t("farmer.errors.phoneConflict")}
            </span>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="email">{t("farmer.email")}</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={errors.email ? "email-error" : undefined}
            {...register("email")}
          />
          {errors.email ? (
            <span id="email-error" className="field-error">
              {t("farmer.errors.email")}
            </span>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="region">{t("farmer.region")}</label>
          <input
            id="region"
            aria-invalid={errors.region ? true : undefined}
            aria-describedby={errors.region ? "region-error" : undefined}
            {...register("region")}
          />
          {errors.region ? (
            <span id="region-error" className="field-error">
              {t("farmer.errors.region")}
            </span>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="district">{t("farmer.district")}</label>
          <input
            id="district"
            aria-invalid={errors.district ? true : undefined}
            aria-describedby={errors.district ? "district-error" : undefined}
            {...register("district")}
          />
          {errors.district ? (
            <span id="district-error" className="field-error">
              {t("farmer.errors.district")}
            </span>
          ) : null}
        </div>

        <div className="field">
          <label htmlFor="preferred_language">{t("farmer.preferredLanguage")}</label>
          <select id="preferred_language" {...register("preferred_language")}>
            <option value="uz">O'zbek</option>
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        </div>

        {createFarmer.error && !isPhoneConflict ? (
          <ApiErrorPanel error={createFarmer.error} />
        ) : null}

        <button className="button" type="submit" disabled={createFarmer.isPending}>
          {createFarmer.isPending ? t("common.saving") : t("farmer.submit")}
        </button>
      </form>
    </div>
  );
}
