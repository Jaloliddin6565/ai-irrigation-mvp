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
