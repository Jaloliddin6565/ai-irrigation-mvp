"""Live AI Soil Wetness Index inference for one field analysis (Phase 2).

Builds a feature vector for the analysis date from weather data the
analysis pipeline already fetched (app/services/analysis.py), runs the
trained model (app/ai/model.py), and returns a structured, always-safe
result.

`run_ai_inference` never raises: a missing/incompatible model artifact, an
incomplete rolling-weather window, an invalid feature (e.g. a malformed
temperature/humidity combination), a non-finite prediction, or any other
unexpected failure is caught here and turned into an AIInferenceResult with
status="unavailable" plus a safely-logged (no secrets, no raw exception
text returned to the caller) technical reason code. The deterministic
FAO-56 analysis this result is attached to must be able to run to
completion regardless of what happens in here — see CLAUDE.md and PHASE 2
section 8.

No future-data leakage: only weather days at or before `analysis_date` are
ever looked up (see `_ROLLING_WINDOW_DAYS`-day window construction below),
mirroring app/ai/features.py build_rolling_feature_records's own
causal-only window.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache

from app.ai.features import (
    FEATURE_ORDER_V0_2,
    RawDailyRecord,
    build_rolling_feature_records,
)
from app.ai.model import (
    AISoilMoistureProxyModel,
    IncompatibleModelError,
    ModelArtifactNotFoundError,
)
from app.ai.schemas import AIFeatureVectorV2
from app.providers.weather.base import DailyWeather

logger = logging.getLogger("app.ai.inference")

RECOMMENDED_MODEL_VERSION = "ai_soil_wetness_index_v0.1"
MODEL_NAME = "AI Soil Wetness Index"
DATA_BASIS = "public_model_precalibration"
VALIDATION_STATUS = "not_sensor_validated"

# Must match app/ai/features.py's own _MAX_ROLLING_WINDOW_DAYS — the widest
# rolling feature (precipitation_sum_30d/et0_sum_30d/cumulative_water_deficit_30d)
# needs this many contiguous antecedent days (including the analysis date
# itself) present before a feature vector can be built at all.
ROLLING_WINDOW_DAYS = 30

_WETNESS_CATEGORIES = ("dry", "moderate", "wet")


@dataclass(frozen=True)
class AIInferenceResult:
    status: str  # "available" | "unavailable"
    model_version: str
    wetness_index: float | None
    wetness_category: str | None
    feature_timestamp: date | None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    unavailable_reason_code: str | None = None


def _unavailable(
    reason_code: str, *, model_version: str = RECOMMENDED_MODEL_VERSION
) -> AIInferenceResult:
    return AIInferenceResult(
        status="unavailable",
        model_version=model_version,
        wetness_index=None,
        wetness_category=None,
        feature_timestamp=None,
        unavailable_reason_code=reason_code,
    )


def wetness_category_from_index(index: float, *, dry_max: float, moderate_max: float) -> str:
    """Conservative, documented category thresholds — see
    backend/config/ai_evidence.yaml for the distribution analysis behind
    the default 0.33/0.66 split."""
    if index < dry_max:
        return "dry"
    if index < moderate_max:
        return "moderate"
    return "wet"


@lru_cache(maxsize=1)
def _load_model() -> AISoilMoistureProxyModel:
    """Process-lifetime cache: the artifact is small, immutable on disk
    once trained, and re-parsing it on every analysis would be wasted
    work. functools.lru_cache does not cache exceptions, so a transient
    failure (e.g. artifact briefly missing during a deploy) is retried on
    the next call rather than being permanently poisoned."""
    return AISoilMoistureProxyModel.load(RECOMMENDED_MODEL_VERSION)


def _build_raw_record(day: DailyWeather, *, latitude: float, longitude: float) -> RawDailyRecord:
    return RawDailyRecord(
        location_id="analysis",
        date=day.date,
        latitude=latitude,
        longitude=longitude,
        et0_mm=day.et0_mm,
        precipitation_mm=day.precipitation_mm,
        temperature_max_c=day.temperature_max_c,
        temperature_min_c=day.temperature_min_c,
        temperature_mean_c=day.temperature_mean_c,
        relative_humidity_mean_pct=day.relative_humidity_mean_pct,
        wind_speed_ms=day.wind_speed_ms,
        shortwave_radiation_mj_m2=day.shortwave_radiation_mj_m2,
        # Weak-label training target — unused by feature construction
        # (build_rolling_feature_records only reads the weather fields
        # above); never exposed by this inference path.
        root_zone_soil_moisture_proxy_m3m3=0.0,
    )


def _explain(vector: AIFeatureVectorV2) -> list[str]:
    """Simple, deterministic explainability signals from the feature
    vector itself (PHASE 2 section 10) — no SHAP, no model internals."""
    return [
        f"7-day cumulative precipitation: {vector.precipitation_sum_7d:.1f}mm.",
        f"7-day cumulative reference evapotranspiration (ET0): {vector.et0_sum_7d:.1f}mm.",
        (
            "30-day cumulative climatic water deficit (ET0 minus precipitation, "
            f"floored at 0 each day): {vector.cumulative_water_deficit_30d:.1f}mm."
        ),
        f"7-day mean vapour pressure deficit: {vector.vpd_mean_7d:.2f}kPa.",
        f"Seasonal context: day {vector.day_of_year} of year, month {vector.month}.",
    ]


def run_ai_inference(
    *,
    analysis_date: date,
    latitude: float,
    longitude: float,
    weather_by_date: dict[date, DailyWeather],
    dry_max: float,
    moderate_max: float,
) -> AIInferenceResult:
    try:
        model = _load_model()
    except ModelArtifactNotFoundError:
        logger.warning(
            "AI wetness model artifact not found for version %s", RECOMMENDED_MODEL_VERSION
        )
        return _unavailable("model_artifact_not_found")
    except IncompatibleModelError:
        logger.warning(
            "AI wetness model artifact incompatible for version %s", RECOMMENDED_MODEL_VERSION
        )
        return _unavailable("model_artifact_incompatible")

    model_version = model.metadata.model_version
    window_dates = [analysis_date - timedelta(days=k) for k in range(ROLLING_WINDOW_DAYS)]
    if not all(d in weather_by_date for d in window_dates):
        return _unavailable("insufficient_rolling_weather_history", model_version=model_version)

    try:
        records = [
            _build_raw_record(weather_by_date[d], latitude=latitude, longitude=longitude)
            for d in sorted(window_dates)
        ]
        rolling_rows = build_rolling_feature_records(records)
    except ValueError:
        logger.warning("AI wetness feature construction failed for analysis_date=%s", analysis_date)
        return _unavailable("feature_construction_failed", model_version=model_version)

    match = next((vec for rec, vec in rolling_rows if rec.date == analysis_date), None)
    if match is None:
        return _unavailable("insufficient_rolling_weather_history", model_version=model_version)

    missing_features = [name for name in FEATURE_ORDER_V0_2 if name not in match.model_dump()]
    if missing_features:
        logger.warning("AI wetness feature vector missing fields: %s", missing_features)
        return _unavailable("required_feature_unavailable", model_version=model_version)

    try:
        prediction = model.predict(match)
    except RuntimeError:
        logger.warning("AI wetness inference produced a non-finite prediction; discarded")
        return _unavailable("non_finite_prediction", model_version=model.metadata.model_version)
    except Exception:
        logger.exception("Unexpected AI wetness inference failure")
        return _unavailable("inference_error", model_version=model.metadata.model_version)

    category = wetness_category_from_index(
        prediction.predicted_value, dry_max=dry_max, moderate_max=moderate_max
    )
    warnings: list[str] = []
    if prediction.clamped_to_safe_range:
        warnings.append(
            "Raw AI prediction fell outside the documented safe range and was clamped to "
            f"[{prediction.safe_range_min:.2f}, {prediction.safe_range_max:.2f}]."
        )

    return AIInferenceResult(
        status="available",
        model_version=prediction.model_version,
        wetness_index=prediction.predicted_value,
        wetness_category=category,
        feature_timestamp=analysis_date,
        reasons=_explain(match),
        warnings=warnings,
        limitations=[prediction.limitation],
    )
