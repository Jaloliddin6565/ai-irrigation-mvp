from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageCode(BaseModel):
    """Stable code + structured params for a reason/warning, so the
    frontend can translate it into Uzbek (frontend/src/utils/labels.ts,
    frontend/src/i18n/uz.json) instead of pattern-matching English prose.
    text_en is kept only for the technical/expert debug view."""

    model_config = ConfigDict(frozen=True)

    code: str
    params: dict[str, Any] = Field(default_factory=dict)
    text_en: str


DISCLAIMER_UZ = (
    "Ushbu tavsiya masofaviy ma'lumotlar, ob-havo modeli va fermer kiritgan "
    "ma'lumotlar asosidagi taxminiy qaror ko'magidir. Tizim tuproq namligini "
    "bevosita o'lchamaydi va agronom yoki suv xo'jaligi mutaxassisi xulosasini "
    "to'liq almashtirmaydi."
)


class AnalysisRequest(BaseModel):
    analysis_date: date | None = Field(
        default=None,
        description="Defaults to today (Asia/Tashkent) if omitted.",
        examples=["2026-06-01"],
    )


class FieldSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    crop_type: str
    crop_variety: str | None
    soil_texture: str
    irrigation_method: str
    area_hectares: float
    planting_date: date
    expected_harvest_date: date | None
    root_depth_override_m: float | None
    field_capacity_override: float | None
    wilting_point_override: float | None


class CropStageSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    days_after_planting: int
    stage: str
    kc: float
    root_depth_m: float
    depletion_fraction: float
    stage_overridden: bool
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WeatherSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_mode: str
    start_date: date
    end_date: date
    days_covered: int
    days_missing: int
    total_et0_mm: float
    total_precipitation_mm: float
    forecast_precipitation_mm: float
    forecast_window_hours: int
    # Provider provenance (live mode: "open-meteo"; fixture mode: "fixture").
    provider: str = "fixture"
    source: str = "DEMO / FIXTURE DATA"
    retrieved_at: datetime | None = None
    cache_hit: bool = False
    # Raw provider coverage over the requested range, independent of the
    # water-balance day count above — see docs/methodology.md "Weather gap
    # handling". Missing dates are never converted to zero values.
    missing_dates: list[date] = Field(default_factory=list)
    coverage_ratio: float = 1.0
    completeness_status: str = "complete"


class SatelliteSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_mode: str
    observations_considered: int
    valid_observations_used: int
    latest_observation_date: date | None
    latest_observation_age_days: int | None
    latest_valid_pixel_ratio: float | None
    data_quality: str
    adjustment_applied: bool
    adjustment_mm: float
    reasons: list[str] = Field(default_factory=list)
    # Provider provenance (live mode: "cdse-sentinel-hub"; fixture mode:
    # "fixture") and how many candidate acquisitions were excluded before
    # any observation reached the trend-adjustment logic above (stale
    # scenes, low valid-pixel ratio, cloud cover over threshold, etc).
    provider: str = "fixture"
    source: str = "DEMO / FIXTURE DATA"
    retrieved_at: datetime | None = None
    cache_hit: bool = False
    rejected_acquisitions_count: int = 0


class DailyWaterBalanceRowSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    stage: str
    kc: float
    root_depth_m: float
    taw_mm: float
    raw_mm: float
    et0_mm: float
    etc_mm: float
    precipitation_mm: float
    effective_precipitation_mm: float
    irrigation_mm: float
    effective_irrigation_mm: float
    depletion_start_mm: float
    depletion_end_mm: float
    is_missing_weather: bool


class InitializationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: str
    start_date: date | None
    starting_depletion_mm: float | None
    uncertainty: float
    warnings: list[str] = Field(default_factory=list)
    warning_codes: list[MessageCode] = Field(default_factory=list)


class WaterBalanceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    initialization: InitializationSummary
    taw_mm: float
    raw_mm: float
    depletion_before_satellite_adjustment_mm: float | None
    satellite_adjustment_mm: float
    depletion_mm: float | None
    start_date: date | None
    end_date: date
    daily_rows: list[DailyWaterBalanceRowSchema] = Field(default_factory=list)


class RecommendationSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    depletion_mm: float | None
    base_gross_mm: float | None
    recommended_min_mm: float
    recommended_max_mm: float
    recommended_min_m3_per_ha: float
    recommended_max_m3_per_ha: float
    total_min_volume_m3: float
    total_max_volume_m3: float
    window_start_date: date | None
    window_end_date: date | None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reason_codes: list[MessageCode] = Field(default_factory=list)
    warning_codes: list[MessageCode] = Field(default_factory=list)


class ConfidenceSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float
    category: str
    factor_scores: dict[str, float]
    weights: dict[str, float]
    triggered_caps: list[str] = Field(default_factory=list)
    strong_factors: list[str] = Field(default_factory=list)
    weak_factors: list[str] = Field(default_factory=list)


class AISummarySchema(BaseModel):
    """AI Soil Wetness Index evidence layer (Phase 2) — additive only.
    Never claims measurement (CLAUDE.md rule 3): wetness_index is a
    location-relative, pre-calibration proxy, not a soil-moisture reading,
    and nothing here alters recommended_min_mm/max_mm, the irrigation
    window, TAW, RAW, or FAO depletion — see app/domain/ai_agreement.py and
    PHASE 2 section 5. Clients that ignore this field see no behavior
    change."""

    model_config = ConfigDict(frozen=True)

    model_name: str
    model_version: str
    status: str  # "available" | "unavailable"
    wetness_index: float | None
    wetness_category: str | None  # "dry" | "moderate" | "wet" | None
    agreement_with_fao: str  # "agree" | "partial" | "disagree" | "unavailable"
    agreement_reason_code: str
    confidence_effect: str  # "agree_bonus" | "disagree_penalty" | "none"
    data_basis: str
    validation_status: str
    feature_timestamp: date | None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    id: int
    field_id: int
    requested_at: datetime
    analysis_date: date
    data_mode: str
    methodology_version: str
    field_summary: FieldSummary
    crop_stage: CropStageSummary
    weather_summary: WeatherSummary
    satellite_summary: SatelliteSummary
    water_balance_summary: WaterBalanceSummary
    recommendation: RecommendationSchema
    confidence: ConfidenceSchema
    ai_summary: AISummarySchema
    warnings: list[str] = Field(default_factory=list)
    disclaimer_uz: str = DISCLAIMER_UZ


class AnalysisListItem(BaseModel):
    id: int
    requested_at: datetime
    analysis_date: date
    data_mode: str
    status: str
    confidence_category: str


class AnalysisListResponse(BaseModel):
    items: list[AnalysisListItem]
    total: int
    limit: int
    offset: int


class SatelliteTimeseriesResponse(BaseModel):
    field_id: int
    data_mode: str
    provider: str = "fixture"
    source: str = "DEMO / FIXTURE DATA"
    retrieved_at: datetime | None = None
    cache_hit: bool = False
    rejected_acquisitions: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]]


class WeatherResponse(BaseModel):
    field_id: int
    data_mode: str
    provider: str = "fixture"
    source: str = "DEMO / FIXTURE DATA"
    retrieved_at: datetime | None = None
    cache_hit: bool = False
    coverage: dict[str, Any] | None = None
    timezone: str
    days: list[dict[str, Any]]
