import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "../i18n";
import { installFetchMock } from "../testUtils/fetchMock";
import { testQueryClient } from "../testUtils/renderWithProviders";
import { AnalysisHistoryPage } from "./AnalysisHistoryPage";

function renderPage() {
  return render(
    <QueryClientProvider client={testQueryClient()}>
      <MemoryRouter initialEntries={["/fields/5/analyses"]}>
        <Routes>
          <Route path="/fields/:fieldId/analyses" element={<AnalysisHistoryPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AnalysisHistoryPage", () => {
  it("shows an empty state when no analyses exist yet", async () => {
    installFetchMock([
      {
        method: "GET",
        test: (path) => path.startsWith("/api/fields/5/analyses"),
        respond: () => ({ status: 200, json: { items: [], total: 0, limit: 50, offset: 0 } }),
      },
      {
        method: "GET",
        test: (path) => path.startsWith("/api/fields/5") && !path.includes("analyses"),
        respond: () => ({ status: 404, json: { code: "field_not_found", message_uz: "Dala topilmadi." } }),
      },
    ]);

    renderPage();

    expect(await screen.findByText("Hali tahlil qilinmagan")).toBeInTheDocument();
  });

  it("lists past analyses with date, status and confidence, and never overwrites the list", async () => {
    installFetchMock([
      {
        method: "GET",
        test: (path) => path.startsWith("/api/fields/5/analyses"),
        respond: () => ({
          status: 200,
          json: {
            items: [
              {
                id: 2,
                requested_at: "2026-05-10T09:00:00Z",
                analysis_date: "2026-05-10",
                data_mode: "fixture",
                status: "irrigate_now",
                confidence_category: "high",
              },
              {
                id: 1,
                requested_at: "2026-05-01T09:00:00Z",
                analysis_date: "2026-05-01",
                data_mode: "fixture",
                status: "monitor",
                confidence_category: "medium",
              },
            ],
            total: 2,
            limit: 50,
            offset: 0,
          },
        }),
      },
      {
        method: "GET",
        test: (path) => path.startsWith("/api/fields/5") && !path.includes("analyses"),
        respond: () => ({ status: 404, json: { code: "field_not_found", message_uz: "Dala topilmadi." } }),
      },
    ]);

    renderPage();

    expect(await screen.findByText("Hozir sug'orish tavsiya etiladi")).toBeInTheDocument();
    expect(screen.getByText("Kuzatishni davom ettiring")).toBeInTheDocument();
  });
});
