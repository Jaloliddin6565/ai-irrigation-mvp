import { useTranslation } from "react-i18next";

import { useConfigOptions } from "../api/hooks";

export function MethodologyPage() {
  const { t } = useTranslation();
  const configOptions = useConfigOptions();

  return (
    <div className="container stack">
      <h1>{t("methodology.title")}</h1>
      <p className="field-hint">
        {t("methodology.versionLabel")}: {configOptions.data?.methodology_version ?? "—"}
      </p>

      <section className="card">
        <h2>{t("methodology.whatTitle")}</h2>
        <p>{t("methodology.whatBody")}</p>
      </section>

      <section className="card">
        <h2>{t("methodology.etcTitle")}</h2>
        <p>{t("methodology.etcBody")}</p>
      </section>

      <section className="card">
        <h2>{t("methodology.tawRawTitle")}</h2>
        <p>{t("methodology.tawRawBody")}</p>
      </section>

      <section className="card">
        <h2>{t("methodology.dailyBalanceTitle")}</h2>
        <p>{t("methodology.dailyBalanceBody")}</p>
      </section>

      <section className="card">
        <h2>{t("methodology.irrigationRecordsTitle")}</h2>
        <p>{t("methodology.irrigationRecordsBody")}</p>
      </section>

      <section className="card">
        <h2>{t("methodology.satelliteTitle")}</h2>
        <p>{t("methodology.satelliteBody")}</p>
      </section>

      <section className="card">
        <h2>{t("methodology.weatherTitle")}</h2>
        <p>{t("methodology.weatherBody")}</p>
      </section>

      <section className="card">
        <h2>{t("methodology.confidenceTitle")}</h2>
        <p>{t("methodology.confidenceBody")}</p>
      </section>

      <section className="card">
        <h2>{t("methodology.dataModesTitle")}</h2>
        <p>{t("methodology.dataModesBody")}</p>
      </section>

      <section className="alert alert--warning">
        <h2>{t("methodology.defaultsTitle")}</h2>
        <p>{t("methodology.defaultsBody")}</p>
      </section>

      <section className="card">
        <h2>{t("methodology.limitationsTitle")}</h2>
        <ul>
          <li>{t("methodology.limitation1")}</li>
          <li>{t("methodology.limitation2")}</li>
          <li>{t("methodology.limitation3")}</li>
          <li>{t("methodology.limitation4")}</li>
          <li>{t("methodology.limitation5")}</li>
        </ul>
      </section>
    </div>
  );
}
