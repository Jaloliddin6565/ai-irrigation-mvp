import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { installFetchMock } from "../../testUtils/fetchMock";
import { testQueryClient } from "../../testUtils/renderWithProviders";
import { RecentIrrigationPrompt } from "./RecentIrrigationPrompt";
import type { IrrigationEventRead } from "../../types/api";

function renderPrompt(lastIrrigation: IrrigationEventRead | null) {
  return render(
    <QueryClientProvider client={testQueryClient()}>
      <RecentIrrigationPrompt fieldId={5} lastIrrigation={lastIrrigation} />
    </QueryClientProvider>
  );
}

function irrigationEvent(overrides: Partial<IrrigationEventRead>): IrrigationEventRead {
  return {
    id: 1,
    field_id: 5,
    occurred_at: "2026-05-01T00:00:00Z",
    duration_minutes: null,
    amount_mm: null,
    total_volume_m3: null,
    flow_rate_m3_hour: null,
    qualitative_amount: null,
    value_source: "farmer_estimate",
    notes: null,
    created_at: "2026-05-01T00:00:00Z",
    ...overrides,
  };
}

describe("RecentIrrigationPrompt", () => {
  it("renders nothing when a recent (within 30 days) irrigation record already exists", () => {
    const recent = irrigationEvent({ occurred_at: new Date().toISOString() });
    const { container } = renderPrompt(recent);
    expect(container).toBeEmptyDOMElement();
  });

  it("asks the question when there is no recent record", () => {
    renderPrompt(null);
    expect(screen.getByText("Oxirgi 30 kun ichida dala sug'orildimi?")).toBeInTheDocument();
  });

  it("shows a warning when the farmer confirms no recent irrigation happened", async () => {
    const user = userEvent.setup();
    renderPrompt(null);

    await user.click(screen.getByRole("button", { name: "Yo'q" }));

    expect(
      screen.getByText("Oxirgi 30 kun ichida sug'orish qayd etilmagan. Tizim buni hisobga oladi, lekin natija haqiqiy holatni to'liq aks ettirmasligi mumkin.")
    ).toBeInTheDocument();
  });

  it("lets the farmer log a quick qualitative amount and confirms it was saved", async () => {
    installFetchMock([
      {
        method: "POST",
        test: (path) => path.startsWith("/api/fields/5/irrigations"),
        respond: (_path, init) => {
          const body = JSON.parse(String(init?.body));
          expect(body.qualitative_amount).toBe("moderate");
          expect(body.value_source).toBe("farmer_estimate");
          return {
            status: 201,
            json: irrigationEvent({ qualitative_amount: "moderate" }),
          };
        },
      },
    ]);
    const user = userEvent.setup();
    renderPrompt(null);

    await user.click(screen.getByRole("button", { name: "Ha" }));
    await user.selectOptions(screen.getByLabelText("Taxminiy miqdor"), "moderate");
    await user.click(screen.getByRole("button", { name: "Saqlash" }));

    expect(
      await screen.findByText("Sug'orish ma'lumoti saqlandi. Rahmat — bu tavsiyaning ishonch darajasini oshiradi.")
    ).toBeInTheDocument();
  });

  it("keeps submit disabled and shows a hint when only 'bilmayman' is selected", async () => {
    const user = userEvent.setup();
    renderPrompt(null);

    await user.click(screen.getByRole("button", { name: "Ha" }));
    await user.selectOptions(screen.getByLabelText("Taxminiy miqdor"), "unknown");

    expect(screen.getByRole("button", { name: "Saqlash" })).toBeDisabled();
    expect(
      screen.getByText("Miqdorni bilmasangiz, bu ma'lumot saqlanmaydi — tizim sug'orish tarixi noma'lum deb hisoblaydi.")
    ).toBeInTheDocument();
  });
});
