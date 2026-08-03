import { useTranslation } from "react-i18next";

import "./App.css";
import { Disclaimer } from "./components/disclaimer/Disclaimer";
import { DataModeBadge } from "./components/layout/DataModeBadge";

export function App() {
  const { t } = useTranslation();

  return (
    <div className="app">
      <header className="app__header">
        <h1>{t("app.title")}</h1>
        <DataModeBadge />
      </header>
      <main className="app__main">
        <p>{t("app.underConstruction")}</p>
      </main>
      <Disclaimer />
    </div>
  );
}
