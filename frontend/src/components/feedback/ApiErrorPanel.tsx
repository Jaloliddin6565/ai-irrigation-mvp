import { useTranslation } from "react-i18next";

import { ApiError, NetworkUnavailableError } from "../../api/client";

const KNOWN_CODE_KEYS = new Set([
  "farmer_phone_conflict",
  "farmer_not_found",
  "field_not_found",
  "analysis_not_found",
  "invalid_dates",
  "invalid_override_values",
  "invalid_geometry",
  "validation_error",
  "provider_configuration_error",
  "provider_authentication_error",
  "provider_rate_limited",
  "provider_timeout",
  "provider_network_error",
  "provider_server_error",
  "provider_malformed_response",
  "unsupported_geometry",
  "invalid_date_range",
  "internal_error",
]);

/**
 * Renders a backend error safely — the structured {code, message_uz}
 * message only, never a raw stack trace or provider response body (see
 * CLAUDE.md rule 7 and docs/security.md).
 */
export function ApiErrorPanel({ error }: { error: unknown }) {
  const { t } = useTranslation();

  if (error instanceof NetworkUnavailableError) {
    return (
      <div className="alert alert--danger" role="alert">
        {t("errors.backendUnavailable")}
      </div>
    );
  }

  if (error instanceof ApiError) {
    const key = KNOWN_CODE_KEYS.has(error.code) ? `errors.code.${error.code}` : null;
    return (
      <div className="alert alert--danger" role="alert">
        <p>{key ? t(key) : error.messageUz}</p>
        {error.code === "provider_rate_limited" || error.code === "provider_timeout" ? (
          <p className="field-hint">{t("errors.retryHint")}</p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="alert alert--danger" role="alert">
      {t("errors.unexpected")}
    </div>
  );
}
