"""Loads and validates the YAML agronomic configuration.

Agronomic values (Kc curves, soil parameters, irrigation efficiencies,
water-balance/recommendation/confidence defaults) live in
backend/config/*.yaml, never hardcoded in Python — see CLAUDE.md. This
module is the single place that reads those files and validates them into
typed, immutable Pydantic models, failing fast (at startup) on malformed
config rather than at request time.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class StageLengthsDays(BaseModel):
    model_config = ConfigDict(frozen=True)

    initial: float
    development: float
    mid: float
    late: float


class CropKc(BaseModel):
    """FAO-56 notation: Kc_ini, Kc_mid, Kc_end."""

    model_config = ConfigDict(frozen=True)

    initial: float
    mid: float
    end: float


class MinMax(BaseModel):
    model_config = ConfigDict(frozen=True)

    min: float
    max: float


class CropProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    label_uz: str
    stage_lengths_days: StageLengthsDays
    kc: CropKc
    root_depth_initial_m: float
    root_depth_max_m: float
    depletion_fraction: float
    practical_application_mm: MinMax
    uncertainty_factor: float


class CropsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    crops: dict[str, CropProfile]


class SoilProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    label_uz: str
    field_capacity: float
    wilting_point: float
    uncertainty_factor: float
    requires_field_survey: bool = False


class SoilsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    soils: dict[str, SoilProfile]


class IrrigationMethodProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    label_uz: str
    efficiency: float
    requires_field_survey: bool = False


class IrrigationMethodsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    irrigation_methods: dict[str, IrrigationMethodProfile]


class SatelliteDefaults(BaseModel):
    model_config = ConfigDict(frozen=True)

    lookback_days: int
    min_valid_observations_for_trend: int
    max_observation_age_days_for_trend: int
    low_valid_pixel_ratio_threshold: float
    trend_adjustment_cap_fraction_of_raw: float


class InitializationDefaults(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_anchor_age_days: int
    conservative_default_fraction_of_raw: float


class QualitativeIrrigationMm(BaseModel):
    model_config = ConfigDict(frozen=True)

    little: float
    moderate: float
    a_lot: float


class WaterBalanceDefaultsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    effective_precipitation_factor: float
    satellite: SatelliteDefaults
    initialization: InitializationDefaults
    qualitative_irrigation_mm: QualitativeIrrigationMm


class RecommendationStatusThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    monitor_depletion_raw_ratio: float
    irrigate_soon_depletion_raw_ratio: float
    irrigate_now_depletion_raw_ratio: float


class ForecastRainDefaults(BaseModel):
    model_config = ConfigDict(frozen=True)

    window_hours: int
    delay_threshold_mm: float


class RecommendedRangeDefaults(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_replacement_fraction: float
    max_replacement_fraction: float


class RecommendationDefaultsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    status_thresholds: RecommendationStatusThresholds
    forecast_rain: ForecastRainDefaults
    recommended_range: RecommendedRangeDefaults
    uncertainty_range_padding_fraction: float


class ConfidenceThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    high: float
    medium: float


class ConfidenceCaps(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_score_if_irrigation_amount_unknown: float
    max_score_if_soil_unknown: float
    max_score_if_initialization_weak: float
    max_score_if_satellite_stale_or_low_quality: float
    max_score_if_weather_missing: float


class ConfidenceWeightsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    weights: dict[str, float]
    thresholds: ConfidenceThresholds
    caps: ConfidenceCaps


class AgronomicConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    crops: CropsConfig
    soils: SoilsConfig
    irrigation_methods: IrrigationMethodsConfig
    water_balance_defaults: WaterBalanceDefaultsConfig
    recommendation_defaults: RecommendationDefaultsConfig
    confidence_weights: ConfidenceWeightsConfig


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_agronomic_config(config_dir: Path) -> AgronomicConfig:
    return AgronomicConfig(
        crops=CropsConfig.model_validate(_read_yaml(config_dir / "crops.yaml")),
        soils=SoilsConfig.model_validate(_read_yaml(config_dir / "soils.yaml")),
        irrigation_methods=IrrigationMethodsConfig.model_validate(
            _read_yaml(config_dir / "irrigation_methods.yaml")
        ),
        water_balance_defaults=WaterBalanceDefaultsConfig.model_validate(
            _read_yaml(config_dir / "water_balance_defaults.yaml")
        ),
        recommendation_defaults=RecommendationDefaultsConfig.model_validate(
            _read_yaml(config_dir / "recommendation_defaults.yaml")
        ),
        confidence_weights=ConfidenceWeightsConfig.model_validate(
            _read_yaml(config_dir / "confidence_weights.yaml")
        ),
    )


@lru_cache
def get_agronomic_config() -> AgronomicConfig:
    from app.settings import CONFIG_DIR

    return load_agronomic_config(CONFIG_DIR)
