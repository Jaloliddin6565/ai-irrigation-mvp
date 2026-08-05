import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../i18n";
import { installFetchMock } from "../testUtils/fetchMock";
import { renderAtRoute } from "../testUtils/renderWithProviders";
import { LandingPage } from "./LandingPage";

describe("LandingPage", () => {
  it("explains the product and shows the disclaimer, without unsupported claims", () => {
    installFetchMock([
      {
        method: "GET",
        test: (path) => path.startsWith("/health"),
        respond: () => ({ status: 200, json: { status: "ok", data_mode: "fixture" } }),
      },
    ]);

    renderAtRoute(<LandingPage />, { path: "/" });

    expect(screen.getByText(/sug'orish qarorlarini qo'llab-quvvatlash/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Boshlash" })).toHaveAttribute("href", "/farmers/new");
    expect(screen.getAllByRole("link", { name: "Metodologiya" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("note")).toBeInTheDocument();

    // The copy explicitly disclaims guarantees ("...kafolatlangan suv
    // tejash/hosildorlik oshishi haqida da'volar berilmaydi") — it must
    // never assert one as fact, and must never invent an accuracy stat.
    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toMatch(/92\s*%/);
    expect(bodyText).not.toMatch(/kafolatlangan (suv tejash|hosildorlik)[^.]*(ta'minlaydi|beradi|kafolatlaymiz)/i);
  });
});
