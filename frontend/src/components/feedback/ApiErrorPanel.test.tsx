import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { ApiError, NetworkUnavailableError } from "../../api/client";
import { ApiErrorPanel } from "./ApiErrorPanel";

describe("ApiErrorPanel", () => {
  it("shows the backend's own specific message, not a generic overlay", () => {
    // The backend computes case-specific detail (e.g. exactly which limit a
    // polygon's area exceeded) — the panel must show that, not a static
    // generic translation keyed only on the error code.
    render(
      <ApiErrorPanel
        error={
          new ApiError(422, {
            code: "invalid_geometry",
            message_uz: "Poligon maydoni (620.00 ga) ruxsat etilgan maksimal maydondan (500 ga) katta.",
          })
        }
      />
    );

    expect(
      screen.getByText("Poligon maydoni (620.00 ga) ruxsat etilgan maksimal maydondan (500 ga) katta.")
    ).toBeInTheDocument();
  });

  it("shows the raw backend message for an unrecognized code too, never a stack trace", () => {
    render(
      <ApiErrorPanel
        error={new ApiError(400, { code: "some_new_code", message_uz: "Yangi xatolik turi." })}
      />
    );

    expect(screen.getByText("Yangi xatolik turi.")).toBeInTheDocument();
  });

  it("shows a network-unavailable message without exposing internals", () => {
    render(<ApiErrorPanel error={new NetworkUnavailableError()} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/ulanib bo'lmadi/i);
  });

  it("suggests a retry for rate-limited and timeout errors", () => {
    render(
      <ApiErrorPanel
        error={new ApiError(503, { code: "provider_rate_limited", message_uz: "Band." })}
      />
    );

    expect(screen.getByText(/qayta urinib ko'ring/i)).toBeInTheDocument();
  });
});
