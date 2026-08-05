import { useTranslation } from "react-i18next";

import { ApiError, NetworkUnavailableError } from "../../api/client";

const RETRYABLE_CODES = new Set(["provider_rate_limited", "provider_timeout"]);

/**
 * Renders a backend error safely. The backend's own `message_uz` is always
 * a crafted, human-appropriate Uzbek string — never a raw traceback or
 * provider response body (see CLAUDE.md rule 7 and docs/security.md) — so
 * it is shown directly rather than routed through a second, generic
 * translation that would discard case-specific detail the backend already
 * computed (e.g. exactly which limit a polygon's area exceeded).
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
    return (
      <div className="alert alert--danger" role="alert">
        <p>{error.messageUz}</p>
        {RETRYABLE_CODES.has(error.code) ? (
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
