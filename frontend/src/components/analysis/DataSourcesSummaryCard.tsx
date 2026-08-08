import { useTranslation } from "react-i18next";

import type { FieldSummary } from "../../types/api";

/**
 * Simple, always-visible "which sources fed this analysis" card — distinct
 * from the deeper technical <CollapsibleSection title={t("dataSource.title")}>
 * (DataSourcePanel) further down, which carries provider/retrieval-time/
 * cache-hit provenance for experts. This card is the plain farmer-facing
 * summary requested for the Award MVP.
 *
 * Soil: no live public soil-properties source is integrated yet (ISRIC
 * SoilGrids' REST point-query returns null for every tested Uzbekistan
 * coordinate — a real regional coverage gap, not a request bug). This
 * always shows the farmer-provided soil texture and must never claim
 * SoilGrids integration until a working public source is actually wired in.
 */
export function DataSourcesSummaryCard({ fieldSummary }: { fieldSummary: FieldSummary }) {
  const { t } = useTranslation();

  return (
    <section className="card">
      <h2>{t("dataSourcesSummary.title")}</h2>
      <dl className="field-summary-card__facts">
        <div>
          <dt>{t("dataSourcesSummary.satelliteLabel")}</dt>
          <dd>{t("dataSourcesSummary.satelliteValue")}</dd>
        </div>
        <div>
          <dt>{t("dataSourcesSummary.weatherLabel")}</dt>
          <dd>{t("dataSourcesSummary.weatherValue")}</dd>
        </div>
        <div>
          <dt>{t("dataSourcesSummary.agronomicModelLabel")}</dt>
          <dd>{t("dataSourcesSummary.agronomicModelValue")}</dd>
        </div>
        <div>
          <dt>{t("dataSourcesSummary.aiLabel")}</dt>
          <dd>{t("dataSourcesSummary.aiValue")}</dd>
        </div>
        <div>
          <dt>{t("dataSourcesSummary.fieldDataLabel")}</dt>
          <dd>{t("dataSourcesSummary.fieldDataValue")}</dd>
        </div>
        <div>
          <dt>{t("dataSourcesSummary.soilLabel")}</dt>
          <dd>
            {t("dataSourcesSummary.soilFarmerProvided")} —{" "}
            {t(`soilTexture.${fieldSummary.soil_texture}`, fieldSummary.soil_texture)}
          </dd>
        </div>
      </dl>
    </section>
  );
}
