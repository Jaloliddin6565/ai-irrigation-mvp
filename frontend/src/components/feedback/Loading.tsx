import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

export function Loading({ labelKey = "common.loading" }: { labelKey?: string }) {
  const { t } = useTranslation();
  return (
    <p className="skeleton" role="status">
      {t(labelKey)}
    </p>
  );
}

export function EmptyState({
  titleKey,
  bodyKey,
  action,
}: {
  titleKey: string;
  bodyKey?: string;
  action?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="empty-state">
      <p>
        <strong>{t(titleKey)}</strong>
      </p>
      {bodyKey ? <p>{t(bodyKey)}</p> : null}
      {action}
    </div>
  );
}
