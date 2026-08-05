import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { SatelliteChart } from "./SatelliteChart";
import type { ParcelObservation } from "../../types/api";

const stats = { p25: 0.1, p50: 0.2, p75: 0.3, mean: 0.2, std: 0.05, min: 0, max: 0.4 };

function observation(overrides: Partial<ParcelObservation>): ParcelObservation {
  return {
    acquisition_date: "2026-05-01",
    valid_pixel_count: 900,
    invalid_pixel_count: 100,
    valid_pixel_ratio: 0.9,
    cloud_or_invalid_percentage: 10,
    ndvi: stats,
    ndmi: stats,
    ndre: stats,
    msi: stats,
    ndwi: stats,
    nbr2: stats,
    scene_id: "S2A_TEST",
    quality_status: "usable",
    quality_warnings: [],
    ...overrides,
  };
}

describe("SatelliteChart", () => {
  it("shows an empty-state message when there are no observations, never a blank chart", () => {
    render(<SatelliteChart observations={[]} />);

    expect(screen.getByText("Bu dala uchun sun'iy yo'ldosh kuzatuvlari mavjud emas.")).toBeInTheDocument();
  });

  it("lets the user switch between spectral indices and flags a non-usable observation", () => {
    render(
      <SatelliteChart
        observations={[
          observation({ acquisition_date: "2026-05-01", quality_status: "usable" }),
          observation({ acquisition_date: "2026-05-11", quality_status: "cloud_contaminated" }),
        ]}
      />
    );

    expect(screen.getByRole("button", { name: "NDVI" })).toBeInTheDocument();
    expect(screen.getByText("Sifat bo'yicha belgilangan kuzatuvlar")).toBeInTheDocument();
  });
});
