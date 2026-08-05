import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { ApiError, NetworkUnavailableError } from "../../api/client";
import { ApiErrorPanel } from "./ApiErrorPanel";

describe("ApiErrorPanel", () => {
  it("shows a friendly message for a known structured backend error code", () => {
    render(
      <ApiErrorPanel
        error={new ApiError(404, { code: "field_not_found", message_uz: "Dala topilmadi (raw)." })}
      />
    );

    expect(screen.getByText("Dala topilmadi.")).toBeInTheDocument();
  });

  it("falls back to the raw backend message for an unrecognized code, never a stack trace", () => {
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
