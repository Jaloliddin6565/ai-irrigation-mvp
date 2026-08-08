import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../i18n";
import { AiSummaryCard } from "./AiSummaryCard";
import type { AISummary } from "../../types/api";

const availableSummary: AISummary = {
  model_name: "AI Soil Wetness Index",
  model_version: "ai_soil_wetness_index_v0.1",
  status: "available",
  wetness_index: 0.32,
  wetness_category: "dry",
  agreement_with_fao: "agree",
  agreement_reason_code: "fao_dry_ai_dry",
  confidence_effect: "agree_bonus",
  data_basis: "public_model_precalibration",
  validation_status: "not_sensor_validated",
  feature_timestamp: "2026-06-01",
  reasons: ["7-day cumulative precipitation: 0.0mm."],
  warnings: [],
  limitations: ["This is a LOCATION-RELATIVE index..."],
};

const unavailableSummary: AISummary = {
  model_name: "AI Soil Wetness Index",
  model_version: "unknown",
  status: "unavailable",
  wetness_index: null,
  wetness_category: null,
  agreement_with_fao: "unavailable",
  agreement_reason_code: "not_available_at_analysis_time",
  confidence_effect: "none",
  data_basis: "public_model_precalibration",
  validation_status: "not_sensor_validated",
  feature_timestamp: null,
  reasons: [],
  warnings: [],
  limitations: [],
};

describe("AiSummaryCard", () => {
  it("shows the wetness index on a 0-100 scale, clearly labeled, never as a raw percent", () => {
    render(<AiSummaryCard aiSummary={availableSummary} confidenceCategory="high" />);

    expect(screen.getByText("AI namlik indeksi:")).toBeInTheDocument();
    expect(screen.getByText("32")).toBeInTheDocument();
    expect(screen.getByText("/ 100")).toBeInTheDocument();
  });

  it("shows the Uzbek wetness category and agreement badges", () => {
    render(<AiSummaryCard aiSummary={availableSummary} confidenceCategory="high" />);

    expect(screen.getByText("Quruq")).toBeInTheDocument();
    expect(screen.getByText("Mos")).toBeInTheDocument();
  });

  it("echoes the overall confidence category using the same label as ConfidenceCard", () => {
    render(<AiSummaryCard aiSummary={availableSummary} confidenceCategory="medium" />);

    expect(screen.getByText("O'rtacha")).toBeInTheDocument();
  });

  it("always shows the pilot/validation-status disclaimer when available", () => {
    render(<AiSummaryCard aiSummary={availableSummary} confidenceCategory="high" />);

    expect(
      screen.getByText("Pilot AI modeli — dala sensorlari bilan hali kalibrlanmagan")
    ).toBeInTheDocument();
  });

  it("never claims measured or sensor-equivalent soil moisture anywhere in the card", () => {
    render(<AiSummaryCard aiSummary={availableSummary} confidenceCategory="high" />);

    const card = screen.getByText("AI tahlili").closest("section");
    expect(card?.textContent?.toLowerCase()).not.toContain("o'lchangan tuproq namligi");
    expect(card?.textContent).not.toContain("% soil moisture");
  });

  it("shows model info, held-out metrics, and the weak-label / sensor-roadmap disclaimers in the collapsed section", () => {
    render(<AiSummaryCard aiSummary={availableSummary} confidenceCategory="high" />);

    expect(screen.getByText("XGBoost — AI Soil Wetness Index v0.1")).toBeInTheDocument();
    expect(screen.getByText("R² = 0.365, RMSE = 0.191, MAE = 0.153")).toBeInTheDocument();
    expect(
      screen.getByText(/ochiq ma'lumotlar asosidagi dastlabki baholash \(weak-label validation\)/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Keyingi pilot bosqichida tanlangan dalalarga tuproq namligi/)
    ).toBeInTheDocument();

    const modelInfoDetails = screen.getByText("AI modeli haqida").closest("details");
    expect(modelInfoDetails).not.toBeNull();
    expect(modelInfoDetails).not.toHaveAttribute("open");
  });

  it("shows a plain unavailable notice instead of a broken card when status is unavailable", () => {
    render(<AiSummaryCard aiSummary={unavailableSummary} confidenceCategory="medium" />);

    expect(
      screen.getByText(
        "AI tahlili hozir mavjud emas. Sug'orish tavsiyasi FAO-56 suv balansi asosida hisoblandi."
      )
    ).toBeInTheDocument();
    expect(screen.queryByText("AI namlik indeksi:")).not.toBeInTheDocument();
    expect(screen.queryByText("Quruq")).not.toBeInTheDocument();
  });

  it("still shows the AI tahlili title even when unavailable", () => {
    render(<AiSummaryCard aiSummary={unavailableSummary} confidenceCategory="medium" />);

    expect(screen.getByText("AI tahlili")).toBeInTheDocument();
  });
});
