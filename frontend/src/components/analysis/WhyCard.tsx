import { useTranslation } from "react-i18next";

import type { AISummary, RecommendationSchema, WeatherSummary } from "../../types/api";

// Frontend-only illustrative threshold for "no significant rain expected" —
// NOT the backend's actual forecast-rain-delay threshold (that decision is
// already made server-side and reflected in recommendation.status /
// reason_codes.forecast_rain_delay). This only decides whether to surface
// an extra plain-Uzbek forecast note in this summary section, so it must
// never contradict the backend's own recommendation.status.
const NO_RAIN_EXPECTED_THRESHOLD_MM = 5;

const IRRIGATION_RELEVANT_STATUSES = new Set(["monitor", "irrigate_soon", "irrigate_now"]);

/**
 * "Nega?" (Why?) synthesis section — a short, plain-Uzbek list built only
 * from real, already-available structured fields (AI category, AI-FAO
 * agreement, forecast precipitation). Deliberately does not repeat the
 * water-balance mm reasons already shown in RecommendationCard's own
 * "Sabablar" list, to avoid duplicating primary content. Renders nothing
 * when no condition applies, rather than an empty card.
 */
export function WhyCard({
  recommendation,
  aiSummary,
  weatherSummary,
}: {
  recommendation: RecommendationSchema;
  aiSummary: AISummary;
  weatherSummary: WeatherSummary;
}) {
  const { t } = useTranslation();
  const bullets: string[] = [];

  if (
    IRRIGATION_RELEVANT_STATUSES.has(recommendation.status) &&
    weatherSummary.forecast_precipitation_mm < NO_RAIN_EXPECTED_THRESHOLD_MM
  ) {
    bullets.push(t("whySection.noRainExpected"));
  }

  if (aiSummary.status === "available" && aiSummary.wetness_category) {
    if (aiSummary.wetness_category === "dry") {
      bullets.push(t("whySection.wetnessDry"));
    } else if (aiSummary.wetness_category === "wet") {
      bullets.push(t("whySection.wetnessWet"));
    } else {
      bullets.push(t("whySection.wetnessModerate"));
    }
  }

  if (aiSummary.agreement_with_fao === "agree") {
    bullets.push(t("whySection.agreementAgree"));
  } else if (aiSummary.agreement_with_fao === "partial") {
    bullets.push(t("whySection.agreementPartial"));
  } else if (aiSummary.agreement_with_fao === "disagree") {
    bullets.push(t("whySection.confidenceLoweredNotice"));
  }

  if (bullets.length === 0) {
    return null;
  }

  return (
    <section className="card">
      <h2>{t("whySection.title")}</h2>
      <ul>
        {bullets.map((bullet) => (
          <li key={bullet}>{bullet}</li>
        ))}
      </ul>
    </section>
  );
}
