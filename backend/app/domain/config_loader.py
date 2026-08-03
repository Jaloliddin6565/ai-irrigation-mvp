"""Loads and validates the YAML agronomic configuration.

Agronomic values (Kc curves, soil parameters, irrigation efficiencies,
confidence weights) live in backend/config/*.yaml, never hardcoded in
Python — see CLAUDE.md. This module is the single place that reads those
files and validates them into typed, immutable Pydantic models, failing
fast (at startup) on malformed config rather than at request time.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class StageValues(BaseModel):
    model_config = ConfigDict(frozen=True)

    initial: float
    development: float
    mid: float
    late: float


class CropKc(BaseModel):
    model_config = ConfigDict(frozen=True)

    initial: float
    mid: float
    late: float


class CropProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    label_uz: str
    stage_lengths_days: StageValues
    kc: CropKc
    root_depth_m: StageValues


class CropsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    crops: dict[str, CropProfile]


class SoilProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    label_uz: str
    field_capacity: float
    wilting_point: float
    depletion_fraction: float
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
    trend_adjustment_cap_fraction_of_raw: float


class InitialDepletionDefaults(BaseModel):
    model_config = ConfigDict(frozen=True)

    recent_irrigation_lookback_days: int
    assume_field_capacity_at_planting: bool
    conservative_default_fraction_of_raw: float


class WaterBalanceDefaultsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    effective_precipitation_factor: float
    satellite: SatelliteDefaults
    initial_depletion: InitialDepletionDefaults


class ConfidenceThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    high: float
    medium: float


class ConfidenceWeightsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    weights: dict[str, float]
    thresholds: ConfidenceThresholds


class AgronomicConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    crops: CropsConfig
    soils: SoilsConfig
    irrigation_methods: IrrigationMethodsConfig
    water_balance_defaults: WaterBalanceDefaultsConfig
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
        confidence_weights=ConfidenceWeightsConfig.model_validate(
            _read_yaml(config_dir / "confidence_weights.yaml")
        ),
    )


@lru_cache
def get_agronomic_config() -> AgronomicConfig:
    from app.settings import CONFIG_DIR

    return load_agronomic_config(CONFIG_DIR)
