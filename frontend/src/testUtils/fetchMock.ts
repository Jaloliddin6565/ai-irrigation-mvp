import { vi } from "vitest";

export interface MockRoute {
  method: "GET" | "POST" | "PATCH" | "DELETE";
  /** Matches against the request path + query string (no origin). */
  test: (path: string) => boolean;
  respond: (path: string, init?: RequestInit) => { status: number; json?: unknown };
}

/**
 * Installs a minimal fetch mock so component tests never touch the real
 * network (see Phase 5 spec section 27 — no real backend, no CDSE/Open-Meteo
 * calls from tests). Unmatched requests fail loudly instead of hanging.
 */
export function installFetchMock(routes: MockRoute[]) {
  const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    const method = (init?.method ?? "GET") as MockRoute["method"];

    const route = routes.find((candidate) => candidate.method === method && candidate.test(path));
    if (!route) {
      throw new Error(`Unmocked request in test: ${method} ${path}`);
    }

    const { status, json } = route.respond(path, init);
    return new Response(json === undefined ? null : JSON.stringify(json), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
