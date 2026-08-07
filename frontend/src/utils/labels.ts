// Maps backend enum string values to i18n keys. Keeping this mapping in one
// place means a new enum value fails loudly (falls back to the raw string)
// instead of silently mis-labeling.
import type {
  ConfidenceCategory,
  CropGrowthStage,
  InitializationMethod,
  QualitativeAmount,
  RecommendationStatus,
  SatelliteDataQuality,
  SatelliteQualityStatus,
  ValueSource,
  WeatherCompletenessStatus,
} from "../types/api";

export function recommendationStatusKey(status: RecommendationStatus): string {
  return `recommendation.status.${status}`;
}

export function confidenceCategoryKey(category: ConfidenceCategory): string {
  return `confidence.category.${category}`;
}

export function cropStageKey(stage: CropGrowthStage): string {
  return `cropStage.${stage}`;
}

export function initializationMethodKey(method: InitializationMethod): string {
  return `waterBalance.initMethod.${method}`;
}

export function satelliteQualityKey(quality: SatelliteDataQuality): string {
  return `satellite.quality.${quality}`;
}

export function satelliteObservationQualityKey(status: SatelliteQualityStatus): string {
  return `satellite.observationQuality.${status}`;
}

export function weatherCompletenessKey(status: WeatherCompletenessStatus): string {
  return `weather.completeness.${status}`;
}

export function qualitativeAmountKey(amount: QualitativeAmount): string {
  return `irrigation.qualitativeAmount.${amount}`;
}

export function valueSourceKey(source: ValueSource): string {
  return `irrigation.valueSource.${source}`;
}

// Confidence factor names (ConfidenceSchema.factor_scores /
// .triggered_caps / .strong_factors / .weak_factors keys) are stable
// backend strings, not farmer-facing text — this maps them the same way as
// every other enum-key mapper above.
export function confidenceFactorKey(factorName: string): string {
  return `confidence.factor.${factorName}`;
}

export function triggeredCapKey(capName: string): string {
  return `confidence.cap.${capName}`;
}

// Reason/warning message codes (MessageCode.code from RecommendationSchema
// .reason_codes/.warning_codes and InitializationSummary.warning_codes) —
// the Uzbek template lives at this i18n key and is interpolated with
// MessageCode.params via react-i18next's {{param}} syntax.
export function messageCodeKey(code: string): string {
  return `messages.${code}`;
}
