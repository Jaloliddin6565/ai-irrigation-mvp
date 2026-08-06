import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { RecommendationCard } from "./RecommendationCard";
import type { RecommendationSchema } from "../../types/api";

const baseRecommendation: RecommendationSchema = {
  status: "irrigate_soon",
  recommended_min_mm: 20,
  recommended_max_mm: 26,
  recommended_min_m3_per_ha: 200,
  recommended_max_m3_per_ha: 260,
  total_min_volume_m3: 300,
  total_max_volume_m3: 390,
  window_start_date: "2026-06-01",
  window_end_date: "2026-06-03",
  reasons: ["Namlik RAW ning 70% iga yetdi."],
  warnings: [],
};

describe("RecommendationCard", () => {
  it("shows the Uzbek status label and the recommended range, never a single value", () => {
    render(
      <RecommendationCard
        recommendation={baseRecommendation}
        methodologyVersion="0.3.0"
        analysisDate="2026-05-30"
      />
    );

    expect(screen.getByText("Yaqin kunlarda sug'oring")).toBeInTheDocument();
    expect(screen.getByText(/20,0 mm.*26,0 mm/)).toBeInTheDocument();
  });

  it("hides the numeric range for insufficient_data results", () => {
    render(
      <RecommendationCard
        recommendation={{
          ...baseRecommendation,
          status: "insufficient_data",
          reasons: ["Insufficient data to produce a water-balance-based recommendation."],
        }}
        methodologyVersion="0.3.0"
        analysisDate="2026-05-30"
      />
    );

    expect(screen.getByText("Ma'lumot yetarli emas")).toBeInTheDocument();
    expect(screen.queryByText(/mm –/)).not.toBeInTheDocument();
  });

  it("renders warnings when present", () => {
    render(
      <RecommendationCard
        recommendation={{ ...baseRecommendation, warnings: ["Ob-havo ma'lumoti to'liq emas."] }}
        methodologyVersion="0.3.0"
        analysisDate="2026-05-30"
      />
    );

    expect(screen.getByText("Ob-havo ma'lumoti to'liq emas.")).toBeInTheDocument();
  });
});
