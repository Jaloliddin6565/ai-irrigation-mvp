"""XGBoost wrapper for the AI Soil Moisture Proxy / AI Soil Wetness Index
models.

Loading and inference are defensive by construction (CLAUDE.md-style
provenance discipline applied to a model artifact rather than an Analysis
result): a load fails loudly on a missing/incompatible artifact rather than
silently substituting something else, and a prediction is always clamped to
a documented physically-plausible range and checked for finiteness before
it ever leaves this module.

Not wired into any API route or the water-balance/recommendation pipeline
yet — Phase 1/1.1 only produce and validate artifacts. See app/ai/__init__.py.

Three model versions share this loader (see `KNOWN_FEATURE_SCHEMAS`):
  - ai_soil_moisture_proxy_v0.1 — same-day weather only, absolute target.
    Shipped with a negative held-out-location R2; kept on disk as an honest
    historical record, no longer CURRENT.
  - ai_soil_moisture_proxy_v0.2 — same-day + antecedent/rolling weather
    (FEATURE_ORDER_V0_2), still an absolute volumetric target.
  - ai_soil_wetness_index_v0.1 — same FEATURE_ORDER_V0_2 feature set, but a
    location-relative 0-1 target (see app/ai/features.py
    `wetness_index_from_value`) instead of absolute m3/m3.
"""

import math
from pathlib import Path
from typing import Any

import xgboost as xgb

from app.ai.features import FEATURE_ORDER_V0_1, FEATURE_ORDER_V0_2, feature_vector_to_array
from app.ai.metadata import ModelMetadata, load_metadata, save_metadata
from app.ai.schemas import (
    AIFeatureVector,
    AIFeatureVectorV2,
    AISoilMoistureProxyPrediction,
    TargetKind,
)

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

# Every model version this code currently knows how to load, and the exact
# feature schema each expects. A model.json whose metadata reports a
# version outside this mapping (or whose feature_list doesn't match) is
# refused rather than guessed at.
KNOWN_FEATURE_SCHEMAS: dict[str, tuple[str, ...]] = {
    "ai_soil_moisture_proxy_v0.1": FEATURE_ORDER_V0_1,
    "ai_soil_moisture_proxy_v0.2": FEATURE_ORDER_V0_2,
    "ai_soil_wetness_index_v0.1": FEATURE_ORDER_V0_2,
}

# Physically-plausible bound for volumetric soil water content (m3/m3).
# 0.0 = bone dry; ~0.6 comfortably covers saturation for the fine-textured
# irrigated soils this MVP targets (typical saturation is nearer 0.4-0.5,
# see backend/config/soils.yaml field_capacity values) — a documented safety
# clamp, not a calibrated physical limit. The wetness index is bounded by
# construction (see `wetness_index_from_value`), so [0, 1] is exact, not a
# safety margin.
SAFE_RANGE_BY_TARGET_KIND: dict[TargetKind, tuple[float, float]] = {
    "volumetric_m3m3": (0.0, 0.60),
    "wetness_index_0_1": (0.0, 1.0),
}
UNIT_BY_TARGET_KIND: dict[TargetKind, str] = {
    "volumetric_m3m3": "m3/m3",
    "wetness_index_0_1": "index_0_1",
}
LABEL_BY_TARGET_KIND: dict[TargetKind, str] = {
    "volumetric_m3m3": "AI soil-moisture proxy (pre-calibration model)",
    "wetness_index_0_1": "AI soil wetness index (pre-calibration model)",
}
LIMITATION_BY_TARGET_KIND: dict[TargetKind, str] = {
    "volumetric_m3m3": (
        "This is a modelled proxy trained against public reanalysis-derived weak "
        "labels, not a measurement of actual field soil moisture. It has not been "
        "validated against in-situ Uzbekistan sensor data."
    ),
    "wetness_index_0_1": (
        "This is a LOCATION-RELATIVE index (0=driest, 1=wettest observed during "
        "training at locations like this one), not an absolute soil-moisture value "
        "and not a guaranteed percentile for a specific new field — a field whose "
        "true climatology differs from the bootstrap training locations will not have "
        "an exactly calibrated 0-1 scale. Derived from public reanalysis weak labels, "
        "not sensor ground truth, and not validated in-situ."
    ),
}

MODEL_FILENAME = "model.json"
METADATA_FILENAME = "metadata.json"


class ModelArtifactNotFoundError(Exception):
    """No model.json/metadata.json exists at the expected artifact path."""


class IncompatibleModelError(Exception):
    """A model artifact exists but its metadata does not match what this
    code version expects (unsupported model_version, or a feature_list that
    does not match that version's known schema)."""


def default_hyperparameters() -> dict[str, Any]:
    """Fixed, documented default hyperparameters. `random_state` is a fixed
    seed for reproducibility, not an unbounded source of randomness
    (CLAUDE.md rule 1 concerns calculations depending on *unseeded*
    randomness at inference/analysis time; a seeded training hyperparameter
    that makes retraining reproducible is the opposite of that). Phase 1.1
    model selection (backend/scripts/train_ai_soil_moisture.py) may override
    this with a grouped-CV-selected candidate — see ModelMetadata.hyperparameters
    for what a given saved artifact actually used."""
    return {
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "objective": "reg:squarederror",
        "random_state": 42,
    }


def train_model(
    X: list[list[float]], y: list[float], *, hyperparameters: dict[str, Any] | None = None
) -> xgb.XGBRegressor:
    params = hyperparameters if hyperparameters is not None else default_hyperparameters()
    regressor = xgb.XGBRegressor(**params)
    regressor.fit(X, y)
    return regressor


def artifact_dir(model_version: str, *, artifacts_dir: Path = ARTIFACTS_DIR) -> Path:
    return artifacts_dir / model_version


def save_artifact(
    regressor: xgb.XGBRegressor,
    metadata: ModelMetadata,
    *,
    artifacts_dir: Path = ARTIFACTS_DIR,
) -> Path:
    """Persist the model in XGBoost's native JSON format (never pickle) plus
    its metadata.json, under artifacts_dir/<model_version>/."""
    out_dir = artifact_dir(metadata.model_version, artifacts_dir=artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    regressor.save_model(str(out_dir / MODEL_FILENAME))
    save_metadata(metadata, out_dir / METADATA_FILENAME)
    return out_dir


class AISoilMoistureProxyModel:
    """Loaded, ready-to-predict AI Soil Moisture Proxy / Wetness Index model."""

    def __init__(self, regressor: xgb.XGBRegressor, metadata: ModelMetadata) -> None:
        self._regressor = regressor
        self._metadata = metadata

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    @classmethod
    def load(
        cls,
        model_version: str,
        *,
        artifacts_dir: Path = ARTIFACTS_DIR,
    ) -> "AISoilMoistureProxyModel":
        out_dir = artifact_dir(model_version, artifacts_dir=artifacts_dir)
        model_path = out_dir / MODEL_FILENAME
        metadata_path = out_dir / METADATA_FILENAME

        if not model_path.exists() or not metadata_path.exists():
            raise ModelArtifactNotFoundError(
                f"No model artifact for version '{model_version}' at {out_dir}. "
                "Run backend/scripts/train_ai_soil_moisture.py first."
            )

        metadata = load_metadata(metadata_path)

        expected_features = KNOWN_FEATURE_SCHEMAS.get(metadata.model_version)
        if expected_features is None:
            raise IncompatibleModelError(
                f"Model artifact reports version '{metadata.model_version}', which this "
                f"code does not support (supported: {sorted(KNOWN_FEATURE_SCHEMAS)})."
            )
        if tuple(metadata.feature_list) != expected_features:
            raise IncompatibleModelError(
                "Model artifact's feature_list does not match the feature schema this "
                f"code expects for '{metadata.model_version}'.\nartifact:  "
                f"{metadata.feature_list}\nexpected:  {list(expected_features)}"
            )

        regressor = xgb.XGBRegressor()
        regressor.load_model(str(model_path))
        return cls(regressor, metadata)

    def predict(
        self, feature_vector: AIFeatureVector | AIFeatureVectorV2
    ) -> AISoilMoistureProxyPrediction:
        array = feature_vector_to_array(feature_vector, feature_order=self._metadata.feature_list)
        raw_prediction = float(self._regressor.predict([array])[0])

        if not math.isfinite(raw_prediction):
            raise RuntimeError(
                "AI Soil Moisture Proxy model produced a non-finite prediction; refusing "
                "to return it."
            )

        target_kind = self._metadata.target_kind
        safe_min, safe_max = SAFE_RANGE_BY_TARGET_KIND[target_kind]
        clamped_value = max(safe_min, min(safe_max, raw_prediction))
        return AISoilMoistureProxyPrediction(
            model_version=self._metadata.model_version,
            target_kind=target_kind,
            predicted_value=clamped_value,
            unit=UNIT_BY_TARGET_KIND[target_kind],
            clamped_to_safe_range=clamped_value != raw_prediction,
            safe_range_min=safe_min,
            safe_range_max=safe_max,
            feature_names_used=tuple(self._metadata.feature_list),
            label=LABEL_BY_TARGET_KIND[target_kind],
            limitation=LIMITATION_BY_TARGET_KIND[target_kind],
        )
