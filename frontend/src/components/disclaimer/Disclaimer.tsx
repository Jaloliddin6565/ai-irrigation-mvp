import { useTranslation } from "react-i18next";

import "./Disclaimer.css";

/**
 * Persistent disclaimer required on every analysis-facing screen (see
 * CLAUDE.md). Must remain visible, not tucked behind a tooltip or modal.
 */
export function Disclaimer() {
  const { t } = useTranslation();

  return (
    <p className="disclaimer" role="note">
      {t("disclaimer.text")}
    </p>
  );
}
