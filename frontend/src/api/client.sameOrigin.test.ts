import { afterEach, describe, expect, it, vi } from "vitest";

describe("API client deployment URL handling", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("uses the browser origin when VITE_API_BASE_URL is blank", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { apiGet } = await import("./client");
    await apiGet<{ status: string }>("/health");

    const requestedUrl = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(requestedUrl.origin).toBe(window.location.origin);
    expect(requestedUrl.pathname).toBe("/health");
  });

  it("uses an explicitly configured backend origin", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { apiGet } = await import("./client");
    await apiGet<{ status: string }>("/health");

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe("https://api.example.test/health");
  });
});
