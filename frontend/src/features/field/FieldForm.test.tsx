import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../i18n";
import { installFetchMock } from "../../testUtils/fetchMock";
import { testQueryClient } from "../../testUtils/renderWithProviders";
import { FieldForm } from "./FieldForm";

function renderForm(onSubmit: (values: unknown) => void) {
  return render(
    <QueryClientProvider client={testQueryClient()}>
      <FieldForm
        submitLabelKey="field.submitCreate"
        isSubmitting={false}
        submitError={null}
        onSubmit={onSubmit}
      />
    </QueryClientProvider>
  );
}

// PolygonEditor mounts a real Leaflet map, which isn't meaningful to
// exercise in jsdom. Stubbing it isolates FieldForm's own validation logic
// (a polygon is required to submit) from Leaflet/Geoman internals.
vi.mock("../../components/map/PolygonEditor", () => ({
  PolygonEditor: ({
    onChange,
  }: {
    onChange: (polygon: unknown, area: number | null) => void;
  }) => (
    <button
      type="button"
      onClick={() =>
        onChange(
          {
            type: "Polygon",
            coordinates: [
              [
                [69.0, 41.0],
                [69.1, 41.0],
                [69.1, 41.1],
                [69.0, 41.0],
              ],
            ],
          },
          1.2
        )
      }
    >
      draw-polygon-stub
    </button>
  ),
}));

function installConfigOptionsMock() {
  installFetchMock([
    {
      method: "GET",
      test: (path) => path.startsWith("/api/config/options"),
      respond: () => ({
        status: 200,
        json: {
          methodology_version: "0.2.0",
          crops: { cotton: { label_uz: "G'o'za" } },
          soils: { loam: { label_uz: "O'rtacha tuproq" } },
          irrigation_methods: { drip: { label_uz: "Tomchilatib sug'orish" } },
        },
      }),
    },
  ]);
}

describe("FieldForm", () => {
  it("requires a drawn polygon before it will submit", async () => {
    installConfigOptionsMock();
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    renderForm(onSubmit);

    await user.type(await screen.findByLabelText("Dala nomi"), "Test dala");
    await user.type(screen.getByLabelText("Ekish sanasi"), "2026-04-01");
    await user.selectOptions(screen.getByLabelText("Ekin turi"), "cotton");
    await user.selectOptions(screen.getByLabelText("Sug'orish usuli"), "drip");
    await user.selectOptions(screen.getByLabelText("Tuproq turi"), "loam");

    await user.click(screen.getByRole("button", { name: "Dalani saqlash" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(await screen.findByText("Dala chegarasini xaritada chizing.")).toBeInTheDocument();
  });

  it("submits once a polygon has been drawn", async () => {
    installConfigOptionsMock();
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    renderForm(onSubmit);

    await user.type(await screen.findByLabelText("Dala nomi"), "Test dala");
    await user.type(screen.getByLabelText("Ekish sanasi"), "2026-04-01");
    await user.selectOptions(screen.getByLabelText("Ekin turi"), "cotton");
    await user.selectOptions(screen.getByLabelText("Sug'orish usuli"), "drip");
    await user.selectOptions(screen.getByLabelText("Tuproq turi"), "loam");
    await user.click(screen.getByText("draw-polygon-stub"));

    await user.click(screen.getByRole("button", { name: "Dalani saqlash" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.geojson_polygon.type).toBe("Polygon");
    expect(submitted.name).toBe("Test dala");
  });
});
