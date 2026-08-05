import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useCreateField } from "../api/hooks";
import { FieldForm, type FieldFormSubmitValues } from "../features/field/FieldForm";
import { useActiveFarmer } from "../features/farmer/ActiveFarmerContext";

export function FieldNewPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { activeFarmerId } = useActiveFarmer();
  const createField = useCreateField();

  function handleSubmit(values: FieldFormSubmitValues) {
    if (activeFarmerId === null) return;
    createField.mutate(
      { ...values, farmer_id: activeFarmerId },
      {
        onSuccess: (field) => {
          void navigate(`/fields/${field.id}`);
        },
      }
    );
  }

  return (
    <div className="container">
      <h1>{t("field.newTitle")}</h1>
      <FieldForm
        submitLabelKey="field.submitCreate"
        isSubmitting={createField.isPending}
        submitError={createField.error}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
