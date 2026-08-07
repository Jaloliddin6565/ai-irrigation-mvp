import { ApiError } from "./client";

/**
 * Flattens the backend's field_errors array (app/core/errors.py) into a
 * simple {fieldName: message} map, keyed by backend field name. Callers
 * decide how to route each key to their own form (RHF setError for a
 * registered field, or a dedicated state slot for something like the map
 * polygon that isn't an RHF-registered input).
 */
export function mapFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || !error.fieldErrors) return {};
  const mapped: Record<string, string> = {};
  for (const entry of error.fieldErrors) {
    if (!(entry.field in mapped)) {
      mapped[entry.field] = entry.message_uz;
    }
  }
  return mapped;
}
