import { useTranslation } from "react-i18next";

import { CollapsibleSection } from "../disclosure/CollapsibleSection";
import { confidenceCategoryKey, confidenceFactorKey, triggeredCapKey } from "../../utils/labels";
import type { ConfidenceSchema } from "../../types/api";

/**
 * Primary view shows only the Uzbek category + a short plain-language
 * explanation — never the raw 0-1 score or internal factor-name keys (a
 * pilot walkthrough found both being rendered directly). The numeric score,
 * factor weights, and stable factor-name keys move into the collapsed
 * "Texnik hisob-kitob" section for anyone who wants the detail. Never
 * described as AI accuracy or a probability — see CLAUDE.md rule 3.
 */
export function ConfidenceCard({ confidence }: { confidence: ConfidenceSchema }) {
  const { t } = useTranslation();

  return (
    <section className="card">
      <h2>{t("confidence.title")}</h2>
      <p>
        <span className={`badge badge--confidence-${confidence.category}`}>
          {t(confidenceCategoryKey(confidence.category))}
        </span>
      </p>
      <p className="field-hint">{t("confidence.explainer")}</p>

      {confidence.strong_factors.length > 0 ? (
        <div>
          <h3>{t("confidence.positiveFactors")}</h3>
          <ul>
            {confidence.strong_factors.map((factor) => (
              <li key={factor}>{t(confidenceFactorKey(factor))}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {confidence.weak_factors.length > 0 ? (
        <div>
          <h3>{t("confidence.negativeFactors")}</h3>
          <ul>
            {confidence.weak_factors.map((factor) => (
              <li key={factor}>{t(confidenceFactorKey(factor))}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <CollapsibleSection title={t("confidence.technicalSection")}>
        <p>
          {t("confidence.score")}: {confidence.score.toFixed(2)}
        </p>
        {confidence.triggered_caps.length > 0 ? (
          <ul>
            {confidence.triggered_caps.map((cap) => (
              <li key={cap}>{t(triggeredCapKey(cap))}</li>
            ))}
          </ul>
        ) : null}
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("confidence.factor")}</th>
                <th>{t("confidence.factorScore")}</th>
                <th>{t("confidence.factorWeight")}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(confidence.factor_scores).map(([factor, score]) => (
                <tr key={factor}>
                  <td>{t(confidenceFactorKey(factor))}</td>
                  <td>{score.toFixed(2)}</td>
                  <td>{confidence.weights[factor]?.toFixed(2) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CollapsibleSection>
    </section>
  );
}
