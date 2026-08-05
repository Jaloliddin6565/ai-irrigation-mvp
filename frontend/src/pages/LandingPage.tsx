import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import "./LandingPage.css";

export function LandingPage() {
  const { t } = useTranslation();

  return (
    <div className="container landing">
      <section className="landing__hero">
        <h1>{t("landing.heroTitle")}</h1>
        <p className="landing__lead">{t("landing.heroBody")}</p>
        <div className="row">
          <Link className="button" to="/farmers/new">
            {t("landing.ctaStart")}
          </Link>
          <Link className="button button--secondary" to="/methodology">
            {t("landing.ctaMethodology")}
          </Link>
        </div>
      </section>

      <section className="card">
        <h2>{t("landing.howTitle")}</h2>
        <ol>
          <li>{t("landing.howStep1")}</li>
          <li>{t("landing.howStep2")}</li>
          <li>{t("landing.howStep3")}</li>
          <li>{t("landing.howStep4")}</li>
        </ol>
      </section>

      <div className="row landing__columns">
        <section className="card">
          <h2>{t("landing.inputsTitle")}</h2>
          <ul>
            <li>{t("landing.input1")}</li>
            <li>{t("landing.input2")}</li>
            <li>{t("landing.input3")}</li>
          </ul>
        </section>
        <section className="card">
          <h2>{t("landing.outputsTitle")}</h2>
          <ul>
            <li>{t("landing.output1")}</li>
            <li>{t("landing.output2")}</li>
            <li>{t("landing.output3")}</li>
          </ul>
        </section>
      </div>

      <section className="alert alert--info">
        <h2>{t("landing.sensorFreeTitle")}</h2>
        <p>{t("landing.sensorFreeBody")}</p>
      </section>
    </div>
  );
}
