import type { ApiErrorBody } from "../types/api";

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const API_BASE_URL = configuredApiBaseUrl || window.location.origin;

/**
 * Structured error mirroring the backend's {code, message_uz, message_en,
 * details} error body (app/core/errors.py). Falls back to a generic shape
 * if the backend response isn't JSON (e.g. the backend is unreachable).
 */
export class ApiError extends Error {
  public status: number;
  public code: string;
  public messageUz: string;
  public messageEn: string | null;
  public details: Record<string, unknown> | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message_en ?? body.message_uz);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.messageUz = body.message_uz;
    this.messageEn = body.message_en ?? null;
    this.details = body.details ?? null;
  }
}

/** Raised when the backend cannot be reached at all (network failure). */
export class NetworkUnavailableError extends Error {
  constructor() {
    super("Backend unavailable");
    this.name = "NetworkUnavailableError";
  }
}

async function parseErrorBody(response: Response): Promise<ApiErrorBody> {
  try {
    const data: unknown = await response.json();
    if (
      data !== null &&
      typeof data === "object" &&
      "code" in data &&
      "message_uz" in data
    ) {
      return data as ApiErrorBody;
    }
  } catch {
    // fall through to generic body below
  }
  return {
    code: "unknown_error",
    message_uz: `So'rov bajarilmadi (${response.status}).`,
    message_en: `Request failed (${response.status}).`,
  };
}

interface RequestOptions {
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(path, `${API_BASE_URL.replace(/\/$/, "")}/`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function request<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
  options?: RequestOptions
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path, options?.query), {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: options?.signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") {
      throw cause;
    }
    throw new NetworkUnavailableError();
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorBody(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function apiGet<T>(path: string, options?: RequestOptions): Promise<T> {
  return request<T>("GET", path, undefined, options);
}

export function apiPost<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
  return request<T>("POST", path, body, options);
}

export function apiPatch<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
  return request<T>("PATCH", path, body, options);
}

export function apiDelete<T>(path: string, options?: RequestOptions): Promise<T> {
  return request<T>("DELETE", path, undefined, options);
}
