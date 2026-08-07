import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { installFetchMock } from "../../testUtils/fetchMock";
import { testQueryClient } from "../../testUtils/renderWithProviders";
import { AnalysisResultView } from "./AnalysisResultView";
import type { AnalysisResponse } from "../../types/api";

const analysis: AnalysisResponse = {
  id: 1,
  field_id: 5,
  requested_at: "2026-06-01T08:00:00Z",
  analysis_date: "2026-06-01",
  data_mode: "fixture",
  methodology_version: "0.3.0",
  field_summary: {
    id: 5,
    name: "Test dala",
    crop_type: "cotton",
    crop_variety: null,
    soil_texture: "loam",
    irrigation_method: "drip",
    area_hectares: 2.0,
    planting_date: "2026-04-01",
    expected_harvest_date: null,
    root_depth_override_m: null,
    field_capacity_override: null,
    wilting_point_override: null,
  },
  crop_stage: {
    days_after_planting: 61,
    stage: "development",
    kc: 0.75,
    root_depth_m: 0.75,
    depletion_fraction: 0.55,
    stage_overridden: false,
    assumptions: [],
    warnings: [],
  },
  weather_summary: {
    data_mode: "fixture",
    start_date: "2026-04-01",
    end_date: "2026-06-01",
    days_covered: 62,
    days_missing: 0,
    total_et0_mm: 232.1,
    total_precipitation_mm: 14.0,
    forecast_precipitation_mm: 3.5,
    forecast_window_hours: 60,
    provider: "fixture",
    source: "DEMO / FIXTURE DATA",
    retrieved_at: null,
    cache_hit: false,
    missing_dates: [],
    coverage_ratio: 1.0,
    completeness_status: "complete",
  },
  satellite_summary: {
    data_mode: "fixture",
    observations_considered: 13,
    valid_observations_used: 3,
    latest_observation_date: "2026-05-26",
    latest_observation_age_days: 6,
    latest_valid_pixel_ratio: 0.93,
    data_quality: "ok",
    adjustment_applied: true,
    adjustment_mm: 4.2,
    reasons: ["Satellite trend confirms drying."],
    provider: "fixture",
    source: "DEMO / FIXTURE DATA",
    retrieved_at: null,
    cache_hit: false,
    rejected_acquisitions_count: 0,
  },
  water_balance_summary: {
    initialization: {
      method: "recent_irrigation_known_amount",
      start_date: "2026-05-29",
      starting_depletion_mm: 82.0,
      uncertainty: 0.2,
      warnings: [],
      warning_codes: [],
    },
    taw_mm: 150.0,
    raw_mm: 82.5,
    depletion_before_satellite_adjustment_mm: 76.2,
    satellite_adjustment_mm: 4.2,
    depletion_mm: 55.0,
    start_date: "2026-05-29",
    end_date: "2026-06-01",
    daily_rows: [],
  },
  recommendation: {
    status: "irrigate_soon",
    depletion_mm: 55.0,
    base_gross_mm: 61.1,
    recommended_min_mm: 20,
    recommended_max_mm: 26,
    recommended_min_m3_per_ha: 200,
    recommended_max_m3_per_ha: 260,
    total_min_volume_m3: 400,
    total_max_volume_m3: 520,
    window_start_date: "2026-06-02",
    window_end_date: "2026-06-04",
    reasons: ["Estimated depletion is 55.0mm."],
    warnings: [],
    reason_codes: [
      {
        code: "depletion_summary",
        text_en: "Estimated depletion is 55.0mm.",
        params: { depletion_mm: 55, raw_mm: 82.5, taw_mm: 150, raw_percent: 67, taw_percent: 37 },
      },
    ],
    warning_codes: [],
  },
  confidence: {
    score: 0.72,
    category: "high",
    factor_scores: { weather_data_availability: 0.9 },
    weights: { weather_data_availability: 0.1 },
    triggered_caps: [],
    strong_factors: ["weather_data_availability"],
    weak_factors: [],
  },
  warnings: ["Some raw English technical warning aggregated from a sub-stage."],
  disclaimer_uz: "Ushbu tavsiya masofaviy ma'lumotlar...",
};

function renderView() {
  installFetchMock([
    {
      method: "GET",
      test: (path) => path.startsWith("/api/fields/5/satellite"),
      respond: () => ({
        status: 200,
        json: { field_id: 5, data_mode: "fixture", observations: [], rejected_acquisitions: [] },
      }),
    },
    {
      method: "GET",
      test: (path) => path.startsWith("/api/fields/5/weather"),
      respond: () => ({ status: 200, json: { field_id: 5, data_mode: "fixture", days: [] } }),
    },
  ]);
  return render(
    <QueryClientProvider client={testQueryClient()}>
      <AnalysisResultView analysis={analysis} />
    </QueryClientProvider>
  );
}

describe("AnalysisResultView", () => {
  it("shows the primary facts (satellite date, forecast rain) outside any collapsed section", () => {
    renderView();

    const satelliteDateRow = screen.getByText("Oxirgi sun'iy yo'ldosh kuzatuvi").closest("div");
    expect(satelliteDateRow?.closest("details")).toBeNull();
    expect(satelliteDateRow?.textContent).toContain("2026");

    const rainRow = screen.getByText("Kutilayotgan yog'ingarchilik").closest("div");
    expect(rainRow?.closest("details")).toBeNull();
  });

  it("keeps expert sections (water balance, satellite, weather, data sources, raw warnings) collapsed by default", () => {
    renderView();

    for (const title of [
      "Suv balansi",
      "Sun'iy yo'ldosh ko'rsatkichlari",
      "Ob-havo ko'rsatkichlari",
      "Ma'lumot manbalari",
      "Texnik ogohlantirishlar (asl matn)",
    ]) {
      const details = screen.getByText(title).closest("details");
      expect(details).not.toBeNull();
      expect(details).not.toHaveAttribute("open");
    }
  });

  it("never shows the raw top-level English warning outside its collapsed technical section", () => {
    renderView();

    const rawWarningText = "Some raw English technical warning aggregated from a sub-stage.";
    const element = screen.getByText(rawWarningText);
    expect(element.closest("details")).not.toBeNull();
  });
});
