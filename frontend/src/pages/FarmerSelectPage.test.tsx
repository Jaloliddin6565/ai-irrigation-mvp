import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "../i18n";
import { ActiveFarmerProvider } from "../features/farmer/ActiveFarmerContext";
import { installFetchMock } from "../testUtils/fetchMock";
import { testQueryClient } from "../testUtils/renderWithProviders";
import { FarmerSelectPage } from "./FarmerSelectPage";

function renderPage() {
  return render(
    <QueryClientProvider client={testQueryClient()}>
      <ActiveFarmerProvider>
        <MemoryRouter initialEntries={["/farmers/select"]}>
          <Routes>
            <Route path="/farmers/select" element={<FarmerSelectPage />} />
            <Route path="/dashboard" element={<p>DASHBOARD_MARKER</p>} />
          </Routes>
        </MemoryRouter>
      </ActiveFarmerProvider>
    </QueryClientProvider>
  );
}

describe("FarmerSelectPage", () => {
  it("selects an existing farmer found by phone and continues to the dashboard", async () => {
    installFetchMock([
      {
        method: "GET",
        test: (path) => path.startsWith("/api/farmers?"),
        respond: () => ({
          status: 200,
          json: {
            id: 7,
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
    ]);
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Telefon raqami"), "+998901234567");
    await user.click(screen.getByRole("button", { name: "Qidirish va tanlash" }));

    expect(await screen.findByText("DASHBOARD_MARKER")).toBeInTheDocument();
  });

  it("shows a not-found error when no farmer matches the phone number", async () => {
    installFetchMock([
      {
        method: "GET",
        test: (path) => path.startsWith("/api/farmers?"),
        respond: () => ({
          status: 404,
          json: { code: "farmer_not_found", message_uz: "Fermer topilmadi." },
        }),
      },
    ]);
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Telefon raqami"), "+998900000000");
    await user.click(screen.getByRole("button", { name: "Qidirish va tanlash" }));

    expect(await screen.findByText("Fermer topilmadi.")).toBeInTheDocument();
  });
});
