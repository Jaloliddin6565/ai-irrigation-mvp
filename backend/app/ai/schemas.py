"""Typed schemas for the AI Soil Moisture Proxy feature/prediction contract.

`AIFeatureVector` (v0.1) and `AIFeatureVectorV2` (v0.2+, Phase 1.1) are the
stable input schemas referenced by CLAUDE.md's "Feature Engine" — see
app/ai/features.py for the canonical field order used to build the numeric
array XGBoost actually consumes (`FEATURE_ORDER_V0_1` / `FEATURE_ORDER_V0_2`).

v0.1 shipped with a negative held-out-location R2 (absolute volumetric
soil moisture proved too location-specific for same-day weather features
alone) — see backend/scripts/train_ai_soil_moisture.py module docstring
for the Phase 1.1 diagnosis. `AIFeatureVectorV2` adds antecedent/rolling
weather features (soil moisture depends on recent history, not just
today) and is used by two Phase-1.1 model versions that share the same
feature set but differ in target: `ai_soil_moisture_proxy_v0.2` (still
absolute m3/m3) and `ai_soil_wetness_index_v0.1` (a location-relative 0-1
index — see app/ai/features.py `wetness_index_from_value`). Both remain
PRE-CALIBRATION proxies, never measurements — see CLAUDE.md rule 3.

The optional fields on both feature vectors are reserved schema slots for
Phase 2 (farmer/crop/satellite features) — accepted here so the schema
does not need to change shape later, but no shipped v0.x model reads them:
per CLAUDE.md this schema must never be populated with fabricated values
just to look more complete.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TargetKind = Literal["volumetric_m3m3", "wetness_index_0_1"]


class AIFeatureVector(BaseModel):
    """One row of v0.1 model input: one location, one calendar day, same-day
    weather only.

    Units: mm for water depths, degrees Celsius for temperature, percent
    (0-100) for relative humidity, kPa for vapour pressure deficit, m/s for
    wind speed, MJ/m^2 for shortwave radiation, decimal degrees for
    latitude/longitude.
    """

    model_config = ConfigDict(frozen=True)

    et0_mm: float
    precipitation_mm: float
    temperature_max_c: float
    temperature_min_c: float
    temperature_mean_c: float
    relative_humidity_mean_pct: float
    vpd_kpa: float
    wind_speed_ms: float
    shortwave_radiation_mj_m2: float
    day_of_year: int = Field(ge=1, le=366)
    month: int = Field(ge=1, le=12)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)

    # --- Reserved for Phase 2. Always None in v0.1; never fabricated. ---
    crop_type: str | None = None
    crop_stage: str | None = None
    days_after_planting: int | None = None
    soil_texture: str | None = None
    fao_estimated_depletion_fraction: float | None = None
    days_since_irrigation: int | None = None
    ndvi: float | None = None
    ndmi: float | None = None


class AIFeatureVectorV2(BaseModel):
    """One row of v0.2+ model input: same-day weather PLUS antecedent
    (rolling, causal-only) weather features — see app/ai/features.py
    `build_rolling_feature_records`. Units match `AIFeatureVector`; rolling
    sums/means use the same per-day units over the stated trailing window
    (inclusive of the current day)."""

    model_config = ConfigDict(frozen=True)

    # --- Same-day features (identical to v0.1). ---
    et0_mm: float
    precipitation_mm: float
    temperature_max_c: float
    temperature_min_c: float
    temperature_mean_c: float
    relative_humidity_mean_pct: float
    vpd_kpa: float
    wind_speed_ms: float
    shortwave_radiation_mj_m2: float
    day_of_year: int = Field(ge=1, le=366)
    month: int = Field(ge=1, le=12)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)

    # --- Antecedent/rolling features (new in v0.2). ---
    precipitation_sum_3d: float
    precipitation_sum_7d: float
    precipitation_sum_14d: float
    precipitation_sum_30d: float
    et0_sum_3d: float
    et0_sum_7d: float
    et0_sum_14d: float
    et0_sum_30d: float
    vpd_mean_3d: float
    vpd_mean_7d: float
    temperature_mean_3d: float
    temperature_mean_7d: float
    shortwave_radiation_mean_7d: float
    precipitation_minus_et0_3d: float
    precipitation_minus_et0_7d: float
    precipitation_minus_et0_14d: float
    cumulative_water_deficit_30d: float

    # --- Reserved for Phase 2. Always None in v0.2/wetness-index v0.1. ---
    crop_type: str | None = None
    crop_stage: str | None = None
    days_after_planting: int | None = None
    soil_texture: str | None = None
    fao_estimated_depletion_fraction: float | None = None
    days_since_irrigation: int | None = None
    ndvi: float | None = None
    ndmi: float | None = None


class AISoilMoistureProxyPrediction(BaseModel):
    """Result of a single inference call. Always carries its own provenance
    so a caller can never mistake this for a measurement — see CLAUDE.md
    rule 3. Generic across target formulations (`target_kind`): absolute
    volumetric proxy (m3/m3) or location-relative wetness index (0-1)."""

    model_config = ConfigDict(frozen=True)

    model_version: str
    target_kind: TargetKind
    predicted_value: float
    unit: str
    clamped_to_safe_range: bool
    safe_range_min: float
    safe_range_max: float
    feature_names_used: tuple[str, ...]
    label: str
    limitation: str
