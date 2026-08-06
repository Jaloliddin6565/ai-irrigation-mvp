import { useTranslation } from "react-i18next";

import "./DataModeBadge.css";
import type { DataMode } from "../../types/api";

/**
 * Always-visible badge showing whether the UI is displaying demo/fixture
 * data or live data. The mode is always sourced from a real backend
 * response (GET /health, or an Analysis's own data_mode) — never from a
 * static client-side env var — so it can never disagree with reality.
 * Fixture results must never be mistaken for live ones (see CLAUDE.md /
 * docs/data_modes.md).
 */
export function DataModeBadge({ mode }: { mode: DataMode }) {
  const { t } = useTranslation();

  return (
    <span className={`data-mode-badge data-mode-badge--${mode}`}>
      {t(mode === "fixture" ? "dataMode.fixture" : "dataMode.live")}
    </span>
  );
}
