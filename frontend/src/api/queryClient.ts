import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./client";

/** Retry transient failures (network/5xx) a couple of times; never retry a
 * request the server has already told us is invalid (4xx). */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false;
  if (error instanceof ApiError) {
    return error.status >= 500;
  }
  return true;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetry,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});
