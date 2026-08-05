import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "../i18n";
import { installFetchMock } from "../testUtils/fetchMock";
import { testQueryClient } from "../testUtils/renderWithProviders";
import { IrrigationNewPage } from "./IrrigationNewPage";

function renderPage() {
  return render(
    <QueryClientProvider client={testQueryClient()}>
      <MemoryRouter initialEntries={["/fields/5/irrigations/new"]}>
        <Routes>
          <Route path="/fields/:fieldId/irrigations/new" element={<IrrigationNewPage />} />
          <Route path="/fields/:fieldId" element={<p>FIELD_MARKER</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function mockField() {
  return {
    method: "GET" as const,
    test: (path: string) => path.startsWith("/api/fields/5") && !path.includes("irrigations"),
    respond: () => ({
      status: 200,
      json: {
        id: 5,
        farmer_id: 1,
        name: "Test dala",
        geojson_polygon: { type: "Polygon", coordinates: [[[69, 41], [69.1, 41], [69.1, 41.1], [69, 41]]] },
        area_hectares: 1.5,
        centroid_latitude: 41.05,
        centroid_longitude: 69.05,
        crop_type: "cotton",
        crop_variety: null,
        planting_date: "2026-04-01",
        expected_harvest_date: null,
        crop_stage_override: null,
        irrigation_method: "drip",
        soil_texture: "loam",
        root_depth_override: null,
        field_capacity_override: null,
        wilting_point_override: null,
        notes: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    }),
  };
}

describe("IrrigationNewPage", () => {
  it("requires at least one amount field before submitting", async () => {
    const fetchMock = installFetchMock([mockField()]);
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Saqlash" }));

    expect(
      await screen.findByText(
        "Kamida bitta miqdor (davomiylik, mm, hajm, suv sarfi yoki taxminiy miqdor) kiritilishi kerak."
      )
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/irrigations"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("submits successfully once an amount is provided and navigates to the field", async () => {
    installFetchMock([
      mockField(),
      {
        method: "POST",
        test: (path) => path.startsWith("/api/fields/5/irrigations"),
        respond: () => ({
          status: 201,
          json: {
            id: 1,
            field_id: 5,
            occurred_at: "2026-05-01T10:00:00",
            duration_minutes: null,
            amount_mm: 12,
            total_volume_m3: null,
            flow_rate_m3_hour: null,
            qualitative_amount: null,
            value_source: "farmer_estimate",
            notes: null,
            created_at: "2026-05-01T10:00:00Z",
          },
        }),
      },
    ]);
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText("Miqdori, mm (ixtiyoriy)"), "12");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(await screen.findByText("FIELD_MARKER")).toBeInTheDocument();
  });
});
