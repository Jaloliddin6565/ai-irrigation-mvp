import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { WhyCard } from "./WhyCard";
import type { AISummary, RecommendationSchema, WeatherSummary } from "../../types/api";

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
  reasons: [],
  warnings: [],
  reason_codes: [],
  warning_codes: [],
};

const baseWeather: WeatherSummary = {
  data_mode: "fixture",
  start_date: "2026-04-01",
  end_date: "2026-06-01",
  days_covered: 62,
  days_missing: 0,
  total_et0_mm: 232.1,
  total_precipitation_mm: 14.0,
  forecast_precipitation_mm: 0.0,
  forecast_window_hours: 60,
  provider: "fixture",
  source: "DEMO / FIXTURE DATA",
  retrieved_at: null,
  cache_hit: false,
  missing_dates: [],
  coverage_ratio: 1.0,
  completeness_status: "complete",
};

const availableAgree: AISummary = {
  model_name: "AI Soil Wetness Index",
  model_version: "ai_soil_wetness_index_v0.1",
  status: "available",
  wetness_index: 0.2,
  wetness_category: "dry",
  agreement_with_fao: "agree",
  agreement_reason_code: "fao_dry_ai_dry",
  confidence_effect: "agree_bonus",
  data_basis: "public_model_precalibration",
  validation_status: "not_sensor_validated",
  feature_timestamp: "2026-06-01",
  reasons: [],
  warnings: [],
  limitations: [],
};

describe("WhyCard", () => {
  it("shows the AI wetness category line and the FAO/AI agreement line when they agree", () => {
    render(<WhyCard recommendation={baseRecommendation} aiSummary={availableAgree} weatherSummary={baseWeather} />);

    expect(screen.getByText("AI namlik indeksi dalaning quruqlashganini ko'rsatmoqda.")).toBeInTheDocument();
    expect(screen.getByText("FAO-56 suv balansi va AI signali bir-biriga mos.")).toBeInTheDocument();
  });

  it("shows the no-significant-rain line only when the forecast is low and irrigation is relevant", () => {
    render(<WhyCard recommendation={baseRecommendation} aiSummary={availableAgree} weatherSummary={baseWeather} />);

    expect(screen.getByText("Kelgusi kunlarda sezilarli yog'ingarchilik kutilmayapti.")).toBeInTheDocument();
  });

  it("omits the no-rain line when meaningful rain is forecast", () => {
    render(
      <WhyCard
        recommendation={baseRecommendation}
        aiSummary={availableAgree}
        weatherSummary={{ ...baseWeather, forecast_precipitation_mm: 12.0 }}
      />
    );

    expect(screen.queryByText("Kelgusi kunlarda sezilarli yog'ingarchilik kutilmayapti.")).not.toBeInTheDocument();
  });

  it("shows the confidence-lowered notice when AI and FAO disagree", () => {
    render(
      <WhyCard
        recommendation={baseRecommendation}
        aiSummary={{ ...availableAgree, agreement_with_fao: "disagree" }}
        weatherSummary={baseWeather}
      />
    );

    expect(
      screen.getByText("AI va suv balansi natijalari to'liq mos emas. Shu sababli ishonch darajasi pasaytirildi.")
    ).toBeInTheDocument();
  });

  it("shows the partial-agreement line when they only partially agree", () => {
    render(
      <WhyCard
        recommendation={baseRecommendation}
        aiSummary={{ ...availableAgree, agreement_with_fao: "partial" }}
        weatherSummary={baseWeather}
      />
    );

    expect(screen.getByText("FAO-56 suv balansi va AI signali qisman mos keladi.")).toBeInTheDocument();
  });

  it("renders nothing when AI is unavailable and no rain-forecast condition applies", () => {
    const { container } = render(
      <WhyCard
        recommendation={{ ...baseRecommendation, status: "no_irrigation_needed" }}
        aiSummary={{
          ...availableAgree,
          status: "unavailable",
          wetness_category: null,
          agreement_with_fao: "unavailable",
        }}
        weatherSummary={{ ...baseWeather, forecast_precipitation_mm: 20.0 }}
      />
    );

    expect(container.firstChild).toBeNull();
  });
});
