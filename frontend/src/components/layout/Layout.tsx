import { Link, NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";

import "./Layout.css";
import { useHealth } from "../../api/hooks";
import { useActiveFarmer } from "../../features/farmer/ActiveFarmerContext";
import { Disclaimer } from "../disclaimer/Disclaimer";
import { DataModeBadge } from "./DataModeBadge";

export function Layout() {
  const { t } = useTranslation();
  const health = useHealth();
  const { activeFarmerId } = useActiveFarmer();

  return (
    <div className="app">
      <a className="skip-link" href="#main-content">
        {t("nav.skipToContent")}
      </a>
      <header className="app__header">
        <Link to="/" className="app__brand">
          {t("app.title")}
        </Link>
        <nav className="app__nav" aria-label={t("nav.mainLabel")}>
          <NavLink to="/dashboard">{t("nav.dashboard")}</NavLink>
          <NavLink to="/methodology">{t("nav.methodology")}</NavLink>
          {activeFarmerId === null ? (
            <NavLink to="/farmers/select">{t("nav.selectFarmer")}</NavLink>
          ) : (
            <NavLink to="/farmers/select">{t("nav.switchFarmer")}</NavLink>
          )}
        </nav>
        {health.data ? <DataModeBadge mode={health.data.data_mode} /> : null}
      </header>
      <main id="main-content" className="app__main">
        <Outlet />
      </main>
      <footer className="app__footer">
        <Disclaimer />
      </footer>
    </div>
  );
}
