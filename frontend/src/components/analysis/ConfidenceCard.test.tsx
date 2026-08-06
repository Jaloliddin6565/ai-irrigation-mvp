import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { ConfidenceCard } from "./ConfidenceCard";
import type { ConfidenceSchema } from "../../types/api";

const confidence: ConfidenceSchema = {
  score: 0.42,
  category: "medium",
  factor_scores: { weather_availability: 0.8, satellite_freshness: 0.2 },
  weights: { weather_availability: 0.1, satellite_freshness: 0.1 },
  triggered_caps: ["satellite_stale"],
  positive_factors: ["Ob-havo ma'lumotlari to'liq."],
  negative_factors: ["Sun'iy yo'ldosh ma'lumotlari eskirgan."],
};

describe("ConfidenceCard", () => {
  it("renders the Uzbek confidence category and never claims it is an AI accuracy score", () => {
    render(<ConfidenceCard confidence={confidence} />);

    expect(screen.getByText("O'rtacha")).toBeInTheDocument();
    expect(screen.getByText("Ob-havo ma'lumotlari to'liq.")).toBeInTheDocument();
    expect(screen.getByText("Sun'iy yo'ldosh ma'lumotlari eskirgan.")).toBeInTheDocument();

    const bodyText = document.body.textContent ?? "";
    expect(bodyText.toLowerCase()).not.toContain("aniqlik");
    expect(bodyText).not.toMatch(/\d{2,3}\s*%\s*aniq/i);
  });
});
