import { useTranslation } from "react-i18next";

import "./DataModeBadge.css";

export type DataMode = "fixture" | "live";

function resolveDataMode(): DataMode {
  return import.meta.env.VITE_DATA_MODE === "live" ? "live" : "fixture";
}

/**
 * Always-visible badge showing whether the UI is displaying demo/fixture
 * data or live data. Fixture results must never be mistaken for live ones
 * (see CLAUDE.md / docs/data_modes.md).
 */
export function DataModeBadge() {
  const { t } = useTranslation();
  const mode = resolveDataMode();

  return (
    <span className={`data-mode-badge data-mode-badge--${mode}`}>
      {t(mode === "fixture" ? "dataMode.fixture" : "dataMode.live")}
    </span>
  );
}
