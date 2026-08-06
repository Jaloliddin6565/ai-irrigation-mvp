import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { useFarmer, useFindFarmerByPhone } from "../api/hooks";
import { ApiErrorPanel } from "../components/feedback/ApiErrorPanel";
import { useActiveFarmer } from "../features/farmer/ActiveFarmerContext";

const phoneSchema = z.object({
  phone: z
    .string()
    .trim()
    .regex(/^\+?[1-9]\d{7,14}$/, "phone"),
});

type PhoneFormValues = z.infer<typeof phoneSchema>;

export function FarmerSelectPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { activeFarmerId, setActiveFarmerId, clearActiveFarmer } = useActiveFarmer();
  const currentFarmer = useFarmer(activeFarmerId);
  const findByPhone = useFindFarmerByPhone();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<PhoneFormValues>({ resolver: zodResolver(phoneSchema) });

  const onSubmit = handleSubmit((values) => {
    findByPhone.mutate(values.phone, {
      onSuccess: (farmer) => {
        setActiveFarmerId(farmer.id);
        void navigate("/dashboard");
      },
    });
  });

  return (
    <div className="container">
      <h1>{t("farmerSelect.title")}</h1>
      <p className="field-hint">{t("farmerSelect.trustedModeNotice")}</p>

      {activeFarmerId !== null ? (
        <section className="card">
          <h2>{t("farmerSelect.currentTitle")}</h2>
          {currentFarmer.isLoading ? <p>{t("common.loading")}</p> : null}
          {currentFarmer.data ? (
            <p>
              {currentFarmer.data.full_name} — {currentFarmer.data.phone}
            </p>
          ) : null}
          <div className="row">
            <Link className="button" to="/dashboard">
              {t("farmerSelect.continueToDashboard")}
            </Link>
            <button className="button button--secondary" type="button" onClick={clearActiveFarmer}>
              {t("farmerSelect.clearSelection")}
            </button>
          </div>
        </section>
      ) : null}

      <section className="card">
        <h2>{t("farmerSelect.lookupTitle")}</h2>
        <form onSubmit={onSubmit} noValidate>
          <div className="field">
            <label htmlFor="lookup_phone">{t("farmer.phone")}</label>
            <input
              id="lookup_phone"
              autoComplete="tel"
              placeholder="+998901234567"
              {...register("phone")}
            />
            {errors.phone ? (
              <span className="field-error">{t("farmer.errors.phone")}</span>
            ) : null}
          </div>
          {findByPhone.error ? <ApiErrorPanel error={findByPhone.error} /> : null}
          <button className="button" type="submit" disabled={findByPhone.isPending}>
            {findByPhone.isPending ? t("common.loading") : t("farmerSelect.lookupSubmit")}
          </button>
        </form>
      </section>

      <p>
        {t("farmerSelect.noProfileYet")} <Link to="/farmers/new">{t("farmerSelect.registerLink")}</Link>
      </p>
    </div>
  );
}
