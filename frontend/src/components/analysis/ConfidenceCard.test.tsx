import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { ConfidenceCard } from "./ConfidenceCard";
import type { ConfidenceSchema } from "../../types/api";

const confidence: ConfidenceSchema = {
  score: 0.42,
  category: "medium",
  factor_scores: { weather_data_availability: 0.8, satellite_freshness: 0.2 },
  weights: { weather_data_availability: 0.1, satellite_freshness: 0.1 },
  triggered_caps: ["max_score_if_satellite_stale_or_low_quality"],
  strong_factors: ["weather_data_availability"],
  weak_factors: ["satellite_freshness"],
};

describe("ConfidenceCard", () => {
  it("renders the Uzbek confidence category and never claims it is an AI accuracy score", () => {
    render(<ConfidenceCard confidence={confidence} />);

    expect(screen.getByText("O'rtacha")).toBeInTheDocument();
    expect(screen.getAllByText("Ob-havo ma'lumotining to'liqligi").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sun'iy yo'ldosh ma'lumotining yangiligi").length).toBeGreaterThan(0);

    const bodyText = document.body.textContent ?? "";
    expect(bodyText.toLowerCase()).not.toContain("aniqlik");
    expect(bodyText).not.toMatch(/\d{2,3}\s*%\s*aniq/i);
  });

  it("never shows the raw internal factor-name key anywhere, and keeps the numeric score inside the collapsed technical section", () => {
    render(<ConfidenceCard confidence={confidence} />);

    // Regression: a pilot walkthrough found raw dict keys like
    // "planting_date_availability" rendered directly in the primary view.
    // With translation applied everywhere (including the technical table),
    // the raw key must never appear anywhere in the output.
    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toContain("weather_data_availability");
    expect(bodyText).not.toContain("satellite_freshness");

    // The raw score is still available (for anyone who wants it), but only
    // inside the collapsed "Texnik hisob-kitob" <details> section.
    const details = document.querySelector("details");
    expect(details?.textContent).toContain("0.42");
    const outsideDetails = Array.from(document.querySelectorAll("section.card > *")).filter(
      (el) => el.tagName !== "DETAILS"
    );
    for (const el of outsideDetails) {
      expect(el.textContent).not.toContain("0.42");
    }
  });
});
