import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import "./i18n";
import { installFetchMock } from "./testUtils/fetchMock";
import { testQueryClient } from "./testUtils/renderWithProviders";

describe("App", () => {
  it("renders the app title and the disclaimer together", () => {
    installFetchMock([
      {
        method: "GET",
        test: (path) => path.startsWith("/health"),
        respond: () => ({ status: 200, json: { status: "ok", data_mode: "fixture" } }),
      },
    ]);

    render(
      <QueryClientProvider client={testQueryClient()}>
        <App />
      </QueryClientProvider>
    );

    expect(screen.getAllByText("AI Irrigatsiya MVP").length).toBeGreaterThan(0);
    expect(screen.getByRole("note")).toBeInTheDocument();
  });
});
