import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../../i18n";
import { DataModeBadge } from "./DataModeBadge";

describe("DataModeBadge", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("defaults to the fixture/demo badge when VITE_DATA_MODE is unset", () => {
    render(<DataModeBadge />);

    expect(screen.getByText(/DEMO/i)).toBeInTheDocument();
  });

  it("shows the live badge when VITE_DATA_MODE=live", () => {
    vi.stubEnv("VITE_DATA_MODE", "live");

    render(<DataModeBadge />);

    expect(screen.getByText(/JONLI/i)).toBeInTheDocument();
  });
});
