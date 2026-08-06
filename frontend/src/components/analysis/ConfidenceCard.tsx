import { useTranslation } from "react-i18next";

import { confidenceCategoryKey } from "../../utils/labels";
import type { ConfidenceSchema } from "../../types/api";

export function ConfidenceCard({ confidence }: { confidence: ConfidenceSchema }) {
  const { t } = useTranslation();

  return (
    <section className="card">
      <h2>{t("confidence.title")}</h2>
      <p>
        <span className={`badge badge--confidence-${confidence.category}`}>
          {t(confidenceCategoryKey(confidence.category))}
        </span>{" "}
        <span className="field-hint">
          {t("confidence.score")}: {confidence.score.toFixed(2)}
        </span>
      </p>
      <p className="field-hint">{t("confidence.explainer")}</p>

      {confidence.positive_factors.length > 0 ? (
        <div>
          <h3>{t("confidence.positiveFactors")}</h3>
          <ul>
            {confidence.positive_factors.map((factor) => (
              <li key={factor}>{factor}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {confidence.negative_factors.length > 0 ? (
        <div>
          <h3>{t("confidence.negativeFactors")}</h3>
          <ul>
            {confidence.negative_factors.map((factor) => (
              <li key={factor}>{factor}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <details>
        <summary>{t("confidence.breakdown")}</summary>
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
                  <td>{factor}</td>
                  <td>{score.toFixed(2)}</td>
                  <td>{confidence.weights[factor]?.toFixed(2) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
