import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import "./i18n";

describe("App", () => {
  it("renders the app title and the disclaimer together", () => {
    render(<App />);

    expect(screen.getByText("AI Irrigatsiya MVP")).toBeInTheDocument();
    expect(screen.getByRole("note")).toBeInTheDocument();
  });
});
