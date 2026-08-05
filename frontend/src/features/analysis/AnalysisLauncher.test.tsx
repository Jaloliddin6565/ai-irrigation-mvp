import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { installFetchMock } from "../../testUtils/fetchMock";
import { testQueryClient } from "../../testUtils/renderWithProviders";
import { AnalysisLauncher } from "./AnalysisLauncher";
import type { FieldRead } from "../../types/api";

const field: FieldRead = {
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
};

describe("AnalysisLauncher", () => {
  it("disables the run button while an analysis is in flight and prevents a duplicate submit", async () => {
    const pending: { resolve: (() => void) | null } = { resolve: null };
    installFetchMock([
      {
        method: "GET",
        test: (path) => path.startsWith("/health"),
        respond: () => ({ status: 200, json: { status: "ok", data_mode: "fixture" } }),
      },
      {
        method: "GET",
        test: (path) => path.startsWith("/api/fields/5/irrigations"),
        respond: () => ({ status: 200, json: { items: [], total: 0, limit: 200, offset: 0 } }),
      },
    ]);
    // Override fetch after installFetchMock to hang the analyze POST until
    // we resolve it manually, so we can assert on the pending UI state.
    const originalFetch = window.fetch;
    window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/analyze") && init?.method === "POST") {
        return new Promise<Response>((resolve) => {
          pending.resolve = () =>
            resolve(
              new Response(
                JSON.stringify({
                  id: 1,
                  field_id: 5,
                  requested_at: "2026-05-01T00:00:00Z",
                  analysis_date: "2026-05-01",
                  data_mode: "fixture",
                }),
                { status: 201, headers: { "Content-Type": "application/json" } }
              )
            );
        });
      }
      return originalFetch(input, init);
    }) as typeof fetch;

    const onAnalysisComplete = () => {};
    const user = userEvent.setup();

    render(
      <QueryClientProvider client={testQueryClient()}>
        <AnalysisLauncher field={field} onAnalysisComplete={onAnalysisComplete} />
      </QueryClientProvider>
    );

    const runButton = await screen.findByRole("button", { name: "Tahlil qilish" });
    await user.click(runButton);

    expect(await screen.findByRole("button", { name: "Tahlil qilinmoqda..." })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Tahlil qilish" })).not.toBeInTheDocument();

    pending.resolve?.();
    window.fetch = originalFetch;
  });
});
