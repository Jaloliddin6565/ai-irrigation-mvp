import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "../i18n";
import { ActiveFarmerProvider } from "../features/farmer/ActiveFarmerContext";
import { installFetchMock } from "../testUtils/fetchMock";
import { testQueryClient } from "../testUtils/renderWithProviders";
import { FarmerRegisterPage } from "./FarmerRegisterPage";

function renderPage() {
  return render(
    <QueryClientProvider client={testQueryClient()}>
      <ActiveFarmerProvider>
        <MemoryRouter initialEntries={["/farmers/new"]}>
          <FarmerRegisterPage />
        </MemoryRouter>
      </ActiveFarmerProvider>
    </QueryClientProvider>
  );
}

describe("FarmerRegisterPage", () => {
  it("shows validation errors and does not submit when required fields are missing", async () => {
    const fetchMock = installFetchMock([]);
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Ro'yxatdan o'tish" }));

    expect(await screen.findAllByText(/./)).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("submits a valid form and calls POST /api/farmers", async () => {
    installFetchMock([
      {
        method: "POST",
        test: (path) => path.startsWith("/api/farmers"),
        respond: () => ({
          status: 201,
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
    ]);
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("To'liq ism"), "Aliyev Vali");
    await user.type(screen.getByLabelText("Telefon raqami"), "+998901234567");
    await user.type(screen.getByLabelText("Viloyat"), "Toshkent");
    await user.type(screen.getByLabelText("Tuman"), "Zangiota");
    await user.click(screen.getByRole("button", { name: "Ro'yxatdan o'tish" }));

    await waitFor(() => {
      expect(screen.queryByText(/xatolik/i)).not.toBeInTheDocument();
    });
  });

  it("shows a clear conflict message on a duplicate phone number", async () => {
    installFetchMock([
      {
        method: "POST",
        test: (path) => path.startsWith("/api/farmers"),
        respond: () => ({
          status: 409,
          json: {
            code: "farmer_phone_conflict",
            message_uz: "Bu telefon raqami bilan fermer allaqachon ro'yxatdan o'tgan.",
          },
        }),
      },
    ]);
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("To'liq ism"), "Aliyev Vali");
    await user.type(screen.getByLabelText("Telefon raqami"), "+998901234567");
    await user.type(screen.getByLabelText("Viloyat"), "Toshkent");
    await user.type(screen.getByLabelText("Tuman"), "Zangiota");
    await user.click(screen.getByRole("button", { name: "Ro'yxatdan o'tish" }));

    expect(
      await screen.findByText(/allaqachon ro'yxatdan o'tgan/)
    ).toBeInTheDocument();
  });
});
