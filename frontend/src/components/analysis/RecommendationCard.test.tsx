import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { RecommendationCard } from "./RecommendationCard";
import type { RecommendationSchema } from "../../types/api";

const baseRecommendation: RecommendationSchema = {
  status: "irrigate_soon",
  depletion_mm: 35.0,
  base_gross_mm: 38.9,
  recommended_min_mm: 20,
  recommended_max_mm: 26,
  recommended_min_m3_per_ha: 200,
  recommended_max_m3_per_ha: 260,
  total_min_volume_m3: 300,
  total_max_volume_m3: 390,
  window_start_date: "2026-06-01",
  window_end_date: "2026-06-03",
  reasons: ["Estimated depletion is 35.0mm, which is 70% of RAW (50.0mm) and 35% of TAW (100.0mm)."],
  warnings: [],
  reason_codes: [
    {
      code: "depletion_summary",
      text_en: "Estimated depletion is 35.0mm, which is 70% of RAW (50.0mm) and 35% of TAW (100.0mm).",
      params: { depletion_mm: 35.0, raw_mm: 50.0, taw_mm: 100.0, raw_percent: 70, taw_percent: 35 },
    },
  ],
  warning_codes: [],
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

  it("leads with the net deficit and gross application point estimates, alongside the range", () => {
    render(
      <RecommendationCard
        recommendation={baseRecommendation}
        methodologyVersion="0.3.0"
        analysisDate="2026-05-30"
      />
    );

    expect(screen.getByText("Hisoblangan sof suv tanqisligi")).toBeInTheDocument();
    expect(screen.getByText("Sug'orish usulini hisobga olgan holda dalaga beriladigan suv")).toBeInTheDocument();
    expect(screen.getByText("35,0 mm")).toBeInTheDocument();
    expect(screen.getByText("38,9 mm")).toBeInTheDocument();
  });

  it("shows a dedicated uncertainty-range explanation next to the range when confidence padded it", () => {
    render(
      <RecommendationCard
        recommendation={{
          ...baseRecommendation,
          reason_codes: [
            ...baseRecommendation.reason_codes,
            {
              code: "confidence_range_widened",
              text_en: "Confidence is 'medium', not 'high', so the range is widened by 10%.",
              params: { confidence_category: "medium", padding_percent: 10 },
            },
          ],
        }}
        methodologyVersion="0.3.0"
        analysisDate="2026-05-30"
      />
    );

    expect(screen.getByText("Noaniqlik oralig'i:")).toBeInTheDocument();
    expect(screen.getByText(/kengaytirildi/)).toBeInTheDocument();
  });

  it("translates reason codes into Uzbek in the primary view, not the raw English sentence", () => {
    render(
      <RecommendationCard
        recommendation={baseRecommendation}
        methodologyVersion="0.3.0"
        analysisDate="2026-05-30"
      />
    );

    expect(screen.getByText(/Taxminiy namlik kamayishi 35 mm/)).toBeInTheDocument();
    // The raw English sentence still exists (in the collapsed technical
    // section), just not as the primary visible reason text.
    const reasonsList = screen.getByText("Sabablar").closest("div");
    expect(reasonsList?.textContent).not.toContain("Estimated depletion is");
  });

  it("hides the numeric range for insufficient_data results", () => {
    render(
      <RecommendationCard
        recommendation={{
          ...baseRecommendation,
          status: "insufficient_data",
          reason_codes: [
            {
              code: "insufficient_data_recommendation",
              text_en: "Insufficient data to produce a water-balance-based recommendation.",
              params: {},
            },
          ],
        }}
        methodologyVersion="0.3.0"
        analysisDate="2026-05-30"
      />
    );

    expect(screen.getByText("Ma'lumot yetarli emas")).toBeInTheDocument();
    expect(screen.queryByText(/mm –/)).not.toBeInTheDocument();
  });

  it("renders translated warnings when present", () => {
    render(
      <RecommendationCard
        recommendation={{
          ...baseRecommendation,
          warnings: ["Computed range (10.0-12.0mm) was clamped to this crop's practical limits (15.0-90.0mm)."],
          warning_codes: [
            {
              code: "recommendation_clamped_to_practical_limits",
              text_en:
                "Computed range (10.0-12.0mm) was clamped to this crop's practical limits (15.0-90.0mm).",
              params: {
                pre_clamp_min_mm: 10.0,
                pre_clamp_max_mm: 12.0,
                practical_min_mm: 15.0,
                practical_max_mm: 90.0,
              },
            },
          ],
        }}
        methodologyVersion="0.3.0"
        analysisDate="2026-05-30"
      />
    );

    expect(screen.getByText(/amaliy sug'orish chegaralariga/)).toBeInTheDocument();
  });
});
