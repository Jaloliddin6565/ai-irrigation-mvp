import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { DataModeBadge } from "./DataModeBadge";

describe("DataModeBadge", () => {
  it("shows the fixture/demo badge for mode=fixture", () => {
    render(<DataModeBadge mode="fixture" />);

    expect(screen.getByText(/DEMO/i)).toBeInTheDocument();
  });

  it("shows the live badge for mode=live", () => {
    render(<DataModeBadge mode="live" />);

    expect(screen.getByText(/JONLI/i)).toBeInTheDocument();
  });
});
