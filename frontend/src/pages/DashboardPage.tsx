import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useFarmer, useFields } from "../api/hooks";
import { ApiErrorPanel } from "../components/feedback/ApiErrorPanel";
import { EmptyState, Loading } from "../components/feedback/Loading";
import { FieldSummaryCard } from "../features/dashboard/FieldSummaryCard";
import { useActiveFarmer } from "../features/farmer/ActiveFarmerContext";
import "./DashboardPage.css";

export function DashboardPage() {
  const { t } = useTranslation();
  const { activeFarmerId } = useActiveFarmer();
  const farmer = useFarmer(activeFarmerId);
  const fieldsQuery = useFields(activeFarmerId);

  return (
    <div className="container">
      <div className="row dashboard__header">
        <div>
          <h1>{t("dashboard.title")}</h1>
          {farmer.data ? <p className="field-hint">{farmer.data.full_name}</p> : null}
        </div>
        <div className="row">
          <Link className="button" to="/fields/new">
            {t("dashboard.addField")}
          </Link>
        </div>
      </div>

      {fieldsQuery.isLoading ? <Loading /> : null}
      {fieldsQuery.error ? <ApiErrorPanel error={fieldsQuery.error} /> : null}

      {fieldsQuery.data && fieldsQuery.data.items.length === 0 ? (
        <EmptyState
          titleKey="dashboard.emptyFieldsTitle"
          bodyKey="dashboard.emptyFieldsBody"
          action={
            <Link className="button" to="/fields/new">
              {t("dashboard.addField")}
            </Link>
          }
        />
      ) : null}

      {fieldsQuery.data && fieldsQuery.data.items.length > 0 ? (
        <div className="dashboard__grid">
          {fieldsQuery.data.items.map((field) => (
            <FieldSummaryCard key={field.id} field={field} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
