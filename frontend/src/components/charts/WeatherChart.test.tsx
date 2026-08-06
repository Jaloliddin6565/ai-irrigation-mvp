import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { WeatherChart } from "./WeatherChart";
import type { DailyWeather } from "../../types/api";

function day(overrides: Partial<DailyWeather>): DailyWeather {
  return {
    date: "2026-05-01",
    is_forecast: false,
    et0_mm: 4.2,
    precipitation_mm: 0,
    precipitation_probability_pct: 10,
    temperature_max_c: 30,
    temperature_min_c: 18,
    wind_speed_ms: 2,
    shortwave_radiation_mj_m2: 20,
    ...overrides,
  };
}

describe("WeatherChart", () => {
  it("shows an empty-state message when there are no weather days", () => {
    render(<WeatherChart days={[]} />);

    expect(screen.getByText("Bu dala uchun ob-havo ma'lumotlari mavjud emas.")).toBeInTheDocument();
  });

  it("distinguishes historical from forecast days without fabricating missing values", () => {
    render(
      <WeatherChart
        days={[day({ date: "2026-05-01", is_forecast: false }), day({ date: "2026-05-02", is_forecast: true })]}
      />
    );

    expect(screen.getByText("Uzuq chiziq — prognoz qilingan qiymatlarni bildiradi.")).toBeInTheDocument();
  });

  it("provides an accessible tabular alternative to the visual chart", () => {
    render(<WeatherChart days={[day({ date: "2026-05-01" })]} />);

    expect(screen.getByRole("img", { name: /Yog'ingarchilik/ })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});
