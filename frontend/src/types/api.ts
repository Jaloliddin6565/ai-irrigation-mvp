// Types mirror backend/app/schemas/*.py field-for-field. Keep in sync with
// the backend contract — see docs/api.md. Do not invent fields that don't
// exist server-side.

export type PreferredLanguage = "uz" | "ru" | "en";

export type CropType = "cotton" | "wheat" | "orchard" | "vineyard" | "vegetables";

export type SoilTexture = "sand" | "sandy_loam" | "loam" | "clay_loam" | "clay" | "unknown";

export type IrrigationMethod = "drip" | "sprinkler" | "furrow" | "basin" | "unknown";

export type CropStage = "initial" | "development" | "mid" | "late";

export type QualitativeAmount = "little" | "moderate" | "a_lot";

export type ValueSource = "measured" | "farmer_estimate";

export type RecommendationStatus =
  | "no_irrigation_needed"
  | "monitor"
  | "irrigate_soon"
  | "irrigate_now"
  | "delay_due_to_forecast_rain"
  | "insufficient_data";

export type ConfidenceCategory = "high" | "medium" | "low";

export type DataMode = "fixture" | "live";

export type SatelliteDataQuality = "ok" | "stale" | "low_quality" | "insufficient";

export type SatelliteQualityStatus =
  | "usable"
  | "low_valid_pixel_ratio"
  | "stale"
  | "cloud_contaminated"
  | "no_data"
  | "malformed_response"
  | "non_finite_values"
  | "insufficient_observations";

export type InitializationMethod =
  | "recent_irrigation_known_amount"
  | "recent_irrigation_duration_flow"
  | "planting_date_assumption"
  | "conservative_default"
  | "insufficient_data";

export type CropGrowthStage =
  | "pre_planting"
  | "initial"
  | "development"
  | "mid_season"
  | "late_season"
  | "post_season";

export type WeatherCompletenessStatus = "complete" | "partial" | "insufficient";

// --- GeoJSON -----------------------------------------------------------

export interface GeoJsonPolygon {
  type: "Polygon";
  coordinates: number[][][];
}

// --- Config options ------------------------------------------------------

export interface ConfigOptionEntry {
  label_uz: string;
}

export interface ConfigOptionsResponse {
  methodology_version: string;
  crops: Record<string, ConfigOptionEntry>;
  soils: Record<string, ConfigOptionEntry>;
  irrigation_methods: Record<string, ConfigOptionEntry>;
}

// --- Health ---------------------------------------------------------------

export interface HealthResponse {
  status: string;
  data_mode: DataMode;
}

// --- Farmer -----------------------------------------------------------

export interface FarmerCreate {
  full_name: string;
  phone: string;
  email?: string | null;
  region: string;
  district: string;
  preferred_language: PreferredLanguage;
}

export interface FarmerRead {
  id: number;
  full_name: string;
  phone: string;
  email: string | null;
  region: string;
  district: string;
  preferred_language: PreferredLanguage;
  created_at: string;
  updated_at: string;
}

// --- Field ------------------------------------------------------------

export interface FieldCreate {
  farmer_id: number;
  name: string;
  geojson_polygon: GeoJsonPolygon;
  crop_type: CropType;
  crop_variety?: string | null;
  planting_date: string;
  expected_harvest_date?: string | null;
  crop_stage_override?: CropStage | null;
  irrigation_method: IrrigationMethod;
  soil_texture: SoilTexture;
  root_depth_override?: number | null;
  field_capacity_override?: number | null;
  wilting_point_override?: number | null;
  notes?: string | null;
}

export type FieldUpdate = Partial<Omit<FieldCreate, "farmer_id">>;

export interface FieldRead {
  id: number;
  farmer_id: number;
  name: string;
  geojson_polygon: GeoJsonPolygon;
  area_hectares: number;
  centroid_latitude: number;
  centroid_longitude: number;
  crop_type: CropType;
  crop_variety: string | null;
  planting_date: string;
  expected_harvest_date: string | null;
  crop_stage_override: CropStage | null;
  irrigation_method: IrrigationMethod;
  soil_texture: SoilTexture;
  root_depth_override: number | null;
  field_capacity_override: number | null;
  wilting_point_override: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface FieldListResponse {
  items: FieldRead[];
  total: number;
  limit: number;
  offset: number;
}

// --- Irrigation event ---------------------------------------------------

export interface IrrigationEventCreate {
  occurred_at: string;
  duration_minutes?: number | null;
  amount_mm?: number | null;
  total_volume_m3?: number | null;
  flow_rate_m3_hour?: number | null;
  qualitative_amount?: QualitativeAmount | null;
  value_source: ValueSource;
  notes?: string | null;
}

export interface IrrigationEventRead {
  id: number;
  field_id: number;
  occurred_at: string;
  duration_minutes: number | null;
  amount_mm: number | null;
  total_volume_m3: number | null;
  flow_rate_m3_hour: number | null;
  qualitative_amount: QualitativeAmount | null;
  value_source: ValueSource;
  notes: string | null;
  created_at: string;
}

export interface IrrigationEventListResponse {
  items: IrrigationEventRead[];
  total: number;
  limit: number;
  offset: number;
}

// --- Analysis -----------------------------------------------------------

export interface AnalysisRequest {
  analysis_date?: string | null;
}

export interface FieldSummary {
  id: number;
  name: string;
  crop_type: string;
  crop_variety: string | null;
  soil_texture: string;
  irrigation_method: string;
  area_hectares: number;
  planting_date: string;
  expected_harvest_date: string | null;
  root_depth_override_m: number | null;
  field_capacity_override: number | null;
  wilting_point_override: number | null;
}

export interface CropStageSummary {
  days_after_planting: number;
  stage: CropGrowthStage;
  kc: number;
  root_depth_m: number;
  depletion_fraction: number;
  stage_overridden: boolean;
  assumptions: string[];
  warnings: string[];
}

export interface WeatherSummary {
  data_mode: DataMode;
  start_date: string;
  end_date: string;
  days_covered: number;
  days_missing: number;
  total_et0_mm: number;
  total_precipitation_mm: number;
  forecast_precipitation_mm: number;
  forecast_window_hours: number;
  provider: string;
  source: string;
  retrieved_at: string | null;
  cache_hit: boolean;
  missing_dates: string[];
  coverage_ratio: number;
  completeness_status: WeatherCompletenessStatus;
}

export interface SatelliteSummary {
  data_mode: DataMode;
  observations_considered: number;
  valid_observations_used: number;
  latest_observation_date: string | null;
  latest_observation_age_days: number | null;
  latest_valid_pixel_ratio: number | null;
  data_quality: SatelliteDataQuality;
  adjustment_applied: boolean;
  adjustment_mm: number;
  reasons: string[];
  provider: string;
  source: string;
  retrieved_at: string | null;
  cache_hit: boolean;
  rejected_acquisitions_count: number;
}

export interface MessageCode {
  code: string;
  params: Record<string, string | number | boolean>;
  text_en: string;
}

export interface InitializationSummary {
  method: InitializationMethod;
  start_date: string | null;
  starting_depletion_mm: number | null;
  uncertainty: number;
  warnings: string[];
  warning_codes: MessageCode[];
}

export interface DailyWaterBalanceRow {
  date: string;
  stage: CropGrowthStage;
  kc: number;
  root_depth_m: number;
  taw_mm: number;
  raw_mm: number;
  et0_mm: number;
  etc_mm: number;
  precipitation_mm: number;
  effective_precipitation_mm: number;
  irrigation_mm: number;
  effective_irrigation_mm: number;
  depletion_start_mm: number;
  depletion_end_mm: number;
  is_missing_weather: boolean;
}

export interface WaterBalanceSummary {
  initialization: InitializationSummary;
  taw_mm: number;
  raw_mm: number;
  depletion_before_satellite_adjustment_mm: number | null;
  satellite_adjustment_mm: number;
  depletion_mm: number | null;
  start_date: string | null;
  end_date: string;
  daily_rows: DailyWaterBalanceRow[];
}

export interface RecommendationSchema {
  status: RecommendationStatus;
  depletion_mm: number | null;
  base_gross_mm: number | null;
  recommended_min_mm: number;
  recommended_max_mm: number;
  recommended_min_m3_per_ha: number;
  recommended_max_m3_per_ha: number;
  total_min_volume_m3: number;
  total_max_volume_m3: number;
  window_start_date: string | null;
  window_end_date: string | null;
  reasons: string[];
  warnings: string[];
  reason_codes: MessageCode[];
  warning_codes: MessageCode[];
}

export interface ConfidenceSchema {
  score: number;
  category: ConfidenceCategory;
  factor_scores: Record<string, number>;
  weights: Record<string, number>;
  triggered_caps: string[];
  strong_factors: string[];
  weak_factors: string[];
}

// --- AI Soil Wetness Index evidence layer (Phase 2/3) ----------------------
// Mirrors backend/app/schemas/analysis.py AISummarySchema field-for-field.
// wetness_index is a LOCATION-RELATIVE 0-1 proxy, never volumetric soil
// moisture — never render it as "% soil moisture" (CLAUDE.md rule 3).

export type AIAvailabilityStatus = "available" | "unavailable";

export type WetnessCategory = "dry" | "moderate" | "wet";

export type AgreementWithFao = "agree" | "partial" | "disagree" | "unavailable";

export type AIConfidenceEffect = "agree_bonus" | "disagree_penalty" | "none";

export interface AISummary {
  model_name: string;
  model_version: string;
  status: AIAvailabilityStatus;
  wetness_index: number | null;
  wetness_category: WetnessCategory | null;
  agreement_with_fao: AgreementWithFao;
  agreement_reason_code: string;
  confidence_effect: AIConfidenceEffect;
  data_basis: string;
  validation_status: string;
  feature_timestamp: string | null;
  reasons: string[];
  warnings: string[];
  limitations: string[];
}

export interface AnalysisResponse {
  id: number;
  field_id: number;
  requested_at: string;
  analysis_date: string;
  data_mode: DataMode;
  methodology_version: string;
  field_summary: FieldSummary;
  crop_stage: CropStageSummary;
  weather_summary: WeatherSummary;
  satellite_summary: SatelliteSummary;
  water_balance_summary: WaterBalanceSummary;
  recommendation: RecommendationSchema;
  confidence: ConfidenceSchema;
  ai_summary: AISummary;
  warnings: string[];
  disclaimer_uz: string;
}

export interface AnalysisListItem {
  id: number;
  requested_at: string;
  analysis_date: string;
  data_mode: DataMode;
  status: RecommendationStatus;
  confidence_category: ConfidenceCategory;
}

export interface AnalysisListResponse {
  items: AnalysisListItem[];
  total: number;
  limit: number;
  offset: number;
}

// --- Satellite timeseries -------------------------------------------------

export interface IndexStatistics {
  p25: number;
  p50: number;
  p75: number;
  mean: number;
  std: number;
  min: number;
  max: number;
}

export interface ParcelObservation {
  acquisition_date: string;
  valid_pixel_count: number;
  invalid_pixel_count: number;
  valid_pixel_ratio: number;
  cloud_or_invalid_percentage: number;
  ndvi: IndexStatistics;
  ndmi: IndexStatistics;
  ndre: IndexStatistics;
  msi: IndexStatistics;
  ndwi: IndexStatistics;
  nbr2: IndexStatistics;
  scene_id: string | null;
  quality_status: SatelliteQualityStatus;
  quality_warnings: string[];
}

export interface RejectedAcquisition {
  acquisition_date: string;
  reason: string;
}

export interface SatelliteTimeseriesResponse {
  field_id: number;
  data_mode: DataMode;
  provider: string;
  source: string;
  retrieved_at: string | null;
  cache_hit: boolean;
  rejected_acquisitions: RejectedAcquisition[];
  observations: ParcelObservation[];
}

// --- Weather --------------------------------------------------------------

export interface DailyWeather {
  date: string;
  is_forecast: boolean;
  et0_mm: number;
  precipitation_mm: number;
  precipitation_probability_pct: number;
  temperature_max_c: number;
  temperature_min_c: number;
  wind_speed_ms: number;
  shortwave_radiation_mj_m2: number;
}

export interface WeatherCoverage {
  requested_start_date: string;
  requested_end_date: string;
  received_start_date: string | null;
  received_end_date: string | null;
  missing_dates: string[];
  coverage_ratio: number;
  completeness_status: WeatherCompletenessStatus;
}

export interface WeatherResponse {
  field_id: number;
  data_mode: DataMode;
  provider: string;
  source: string;
  retrieved_at: string | null;
  cache_hit: boolean;
  coverage: WeatherCoverage | null;
  timezone: string;
  days: DailyWeather[];
}

// --- Errors -----------------------------------------------------------

export interface ApiFieldError {
  field: string;
  code: string;
  message_uz: string;
}

export interface ApiErrorBody {
  code: string;
  message_uz: string;
  message_en?: string | null;
  details?: Record<string, unknown> | null;
  field_errors?: ApiFieldError[] | null;
}
