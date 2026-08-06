import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../i18n";
import { installFetchMock } from "../testUtils/fetchMock";
import { renderWithActiveFarmer } from "../testUtils/renderWithProviders";
import { DashboardPage } from "./DashboardPage";

function renderPage() {
  return renderWithActiveFarmer(<DashboardPage />, {
    path: "/dashboard",
    farmerId: 1,
    withLayout: false,
  });
}

describe("DashboardPage", () => {
  it("shows an empty state and does not fabricate metrics when the farmer has no fields", async () => {
    installFetchMock([
      {
        method: "GET",
        test: (path) => path.startsWith("/api/farmers/1"),
        respond: () => ({
          status: 200,
          json: {
            id: 1,
            full_name: "Aliyev Vali",
            phone: "+998901234567",
            email: null,
            region: "Toshkent",
            district: "Zangiota",
            preferred_language: "uz",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        }),
      },
      {
        method: "GET",
        test: (path) => path.startsWith("/api/fields"),
        respond: () => ({ status: 200, json: { items: [], total: 0, limit: 50, offset: 0 } }),
      },
    ]);

    renderPage();

    expect(await screen.findByText("Hozircha dalalar yo'q")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Yangi dala qo'shish" }).length).toBeGreaterThan(0);
  });
});
