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

  it("provides an accessible tabular alternative to the visual chart", () => {
    render(<WaterBalanceChart rows={[row({ date: "2026-05-01" })]} />);

    expect(screen.getByRole("img", { name: /namlik kamayishi/ })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("warns when depletion has been at/near TAW for an extended stretch", () => {
    const rows = Array.from({ length: 6 }, (_, i) =>
      row({ date: `2026-05-0${i + 1}`, taw_mm: 150, depletion_end_mm: 148 })
    );
    render(<WaterBalanceChart rows={rows} />);

    expect(screen.getByText(/so'nggi 6 kun davomida TAW/)).toBeInTheDocument();
  });

  it("does not warn when depletion only briefly touches TAW", () => {
    const rows = [
      row({ date: "2026-05-01", taw_mm: 150, depletion_end_mm: 148 }),
      row({ date: "2026-05-02", taw_mm: 150, depletion_end_mm: 40 }),
      row({ date: "2026-05-03", taw_mm: 150, depletion_end_mm: 35 }),
    ];
    render(<WaterBalanceChart rows={rows} />);

    expect(screen.queryByText(/TAW.*darajasida yoki unga yaqin/)).not.toBeInTheDocument();
  });
});
