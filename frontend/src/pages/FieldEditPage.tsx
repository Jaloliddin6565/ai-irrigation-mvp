import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useField, useUpdateField } from "../api/hooks";
import { ApiErrorPanel } from "../components/feedback/ApiErrorPanel";
import { Loading } from "../components/feedback/Loading";
import { FieldForm, type FieldFormSubmitValues } from "../features/field/FieldForm";

export function FieldEditPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { fieldId } = useParams<{ fieldId: string }>();
  const parsedFieldId = fieldId ? Number(fieldId) : NaN;
  const field = useField(Number.isFinite(parsedFieldId) ? parsedFieldId : null);
  const updateField = useUpdateField(parsedFieldId);

  if (!Number.isFinite(parsedFieldId)) {
    return <Navigate to="/not-found" replace />;
  }

  function handleSubmit(values: FieldFormSubmitValues) {
    // FieldUpdate has no farmer_id — ownership doesn't change via this form.
    // The extra key is harmless (pydantic ignores unknown fields) but we
    // still keep the wire payload honest about what this form can change.
    updateField.mutate(values, {
      onSuccess: () => {
        void navigate(`/fields/${parsedFieldId}`);
      },
    });
  }

  return (
    <div className="container">
      <h1>{t("field.editTitle")}</h1>
      {field.isLoading ? <Loading /> : null}
      {field.error ? <ApiErrorPanel error={field.error} /> : null}
      {field.data ? (
        <FieldForm
          initial={field.data}
          submitLabelKey="field.submitUpdate"
          isSubmitting={updateField.isPending}
          submitError={updateField.error}
          onSubmit={handleSubmit}
        />
      ) : null}
    </div>
  );
}
