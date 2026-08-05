import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { WaterBalanceChart } from "./WaterBalanceChart";
import type { DailyWaterBalanceRow } from "../../types/api";

function row(overrides: Partial<DailyWaterBalanceRow>): DailyWaterBalanceRow {
  return {
    date: "2026-05-01",
    stage: "mid_season",
    kc: 1.1,
    root_depth_m: 0.9,
    taw_mm: 150,
    raw_mm: 75,
    et0_mm: 5,
    etc_mm: 5.5,
    precipitation_mm: 0,
    effective_precipitation_mm: 0,
    irrigation_mm: 0,
    effective_irrigation_mm: 0,
    depletion_start_mm: 30,
    depletion_end_mm: 35,
    is_missing_weather: false,
    ...overrides,
  };
}

describe("WaterBalanceChart", () => {
  it("shows an empty-state message when there is no water-balance history", () => {
    render(<WaterBalanceChart rows={[]} />);

    expect(screen.getByText("Suv balansi ma'lumotlari mavjud emas.")).toBeInTheDocument();
  });

  it("labels the chart as a modelled estimate, never measured soil moisture", () => {
    render(<WaterBalanceChart rows={[row({ date: "2026-05-01" }), row({ date: "2026-05-02" })]} />);

    expect(
      screen.getByText(
        "Chiziq — modelga asoslangan taxminiy kunlik namlik kamayishi; ustunlar — yog'ingarchilik va sug'orish."
      )
    ).toBeInTheDocument();
  });
});
