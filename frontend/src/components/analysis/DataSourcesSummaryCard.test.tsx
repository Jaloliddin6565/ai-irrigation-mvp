import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { DataSourcesSummaryCard } from "./DataSourcesSummaryCard";
import type { FieldSummary } from "../../types/api";

const fieldSummary: FieldSummary = {
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
};

describe("DataSourcesSummaryCard", () => {
  it("shows all required minimum sources", () => {
    render(<DataSourcesSummaryCard fieldSummary={fieldSummary} />);

    expect(screen.getByText("Copernicus Sentinel-2")).toBeInTheDocument();
    expect(screen.getByText("Open-Meteo")).toBeInTheDocument();
    expect(screen.getByText("FAO-56 uslubidagi suv balansi")).toBeInTheDocument();
    expect(screen.getByText("XGBoost — AI Soil Wetness Index v0.1")).toBeInTheDocument();
    expect(screen.getByText("Fermer kiritgan ekin / sug'orish / dala ma'lumotlari")).toBeInTheDocument();
  });

  it("shows the farmer-provided soil texture and never claims SoilGrids integration", () => {
    render(<DataSourcesSummaryCard fieldSummary={fieldSummary} />);

    expect(screen.getByText(/Fermer kiritgan tuproq turi/)).toBeInTheDocument();
    expect(screen.getByText(/O'rtacha tuproq \(qumoq-soz\)/)).toBeInTheDocument();
    expect(screen.queryByText(/SoilGrids/i)).not.toBeInTheDocument();
  });
});
