import math
from datetime import date, timedelta

import pytest

from app.ai import inference
from app.ai.inference import (
    RECOMMENDED_MODEL_VERSION,
    ROLLING_WINDOW_DAYS,
    run_ai_inference,
    wetness_category_from_index,
)
from app.ai.model import IncompatibleModelError, ModelArtifactNotFoundError
from app.providers.weather.base import DailyWeather

ANALYSIS_DATE = date(2026, 6, 1)
LATITUDE = 41.3
LONGITUDE = 69.3
DRY_MAX = 0.33
MODERATE_MAX = 0.66


def _daily(
    d: date,
    *,
    et0_mm: float = 4.0,
    precipitation_mm: float = 0.0,
    temperature_max_c: float = 28.0,
    temperature_min_c: float = 14.0,
    temperature_mean_c: float = 21.0,
    relative_humidity_mean_pct: float = 45.0,
    wind_speed_ms: float = 2.0,
    shortwave_radiation_mj_m2: float = 20.0,
    is_forecast: bool = False,
) -> DailyWeather:
    return DailyWeather(
        date=d,
        is_forecast=is_forecast,
        et0_mm=et0_mm,
        precipitation_mm=precipitation_mm,
        precipitation_probability_pct=10.0,
        temperature_max_c=temperature_max_c,
        temperature_min_c=temperature_min_c,
        temperature_mean_c=temperature_mean_c,
        relative_humidity_mean_pct=relative_humidity_mean_pct,
        wind_speed_ms=wind_speed_ms,
        shortwave_radiation_mj_m2=shortwave_radiation_mj_m2,
    )


def _full_window(
    analysis_date: date = ANALYSIS_DATE, **overrides: float
) -> dict[date, DailyWeather]:
    return {
        analysis_date - timedelta(days=k): _daily(analysis_date - timedelta(days=k), **overrides)
        for k in range(ROLLING_WINDOW_DAYS)
    }


def _run(weather_by_date: dict[date, DailyWeather], analysis_date: date = ANALYSIS_DATE):
    return run_ai_inference(
        analysis_date=analysis_date,
        latitude=LATITUDE,
        longitude=LONGITUDE,
        weather_by_date=weather_by_date,
        dry_max=DRY_MAX,
        moderate_max=MODERATE_MAX,
    )


class _FakeMetadata:
    model_version = "fake_v1"


class _FakeModel:
    def __init__(self, predict_fn) -> None:
        self.metadata = _FakeMetadata()
        self._predict_fn = predict_fn

    def predict(self, vector):
        return self._predict_fn(vector)


# --- Happy path: uses the real, committed ai_soil_wetness_index_v0.1 artifact. ---


def test_successful_inference_returns_available_result() -> None:
    result = _run(_full_window())

    assert result.status == "available"
    assert result.model_version == RECOMMENDED_MODEL_VERSION
    assert result.wetness_index is not None
    assert math.isfinite(result.wetness_index)
    assert 0.0 <= result.wetness_index <= 1.0
    assert result.wetness_category in {"dry", "moderate", "wet"}
    assert result.feature_timestamp == ANALYSIS_DATE
    assert result.reasons
    assert result.limitations
    assert result.unavailable_reason_code is None


def test_explainability_reasons_mention_key_signals() -> None:
    result = _run(_full_window())
    joined = " ".join(result.reasons).lower()
    assert "precipitation" in joined
    assert "evapotranspiration" in joined
    assert "vapour pressure deficit" in joined


# --- No future-data leakage. ---


def test_future_weather_never_affects_the_prediction() -> None:
    baseline = _run(_full_window())

    poisoned = dict(_full_window())
    future_day = ANALYSIS_DATE + timedelta(days=1)
    poisoned[future_day] = _daily(
        future_day,
        et0_mm=999.0,
        precipitation_mm=999.0,
        temperature_max_c=55.0,
        temperature_min_c=40.0,
        temperature_mean_c=48.0,
        relative_humidity_mean_pct=1.0,
        wind_speed_ms=99.0,
        shortwave_radiation_mj_m2=999.0,
    )
    poisoned_result = _run(poisoned)

    assert poisoned_result.wetness_index == baseline.wetness_index
    assert poisoned_result.wetness_category == baseline.wetness_category


# --- Insufficient rolling history. ---


def test_insufficient_rolling_history_returns_unavailable() -> None:
    short_window = {
        ANALYSIS_DATE - timedelta(days=k): _daily(ANALYSIS_DATE - timedelta(days=k))
        for k in range(10)  # fewer than ROLLING_WINDOW_DAYS
    }
    result = _run(short_window)

    assert result.status == "unavailable"
    assert result.unavailable_reason_code == "insufficient_rolling_weather_history"
    assert result.wetness_index is None
    assert result.wetness_category is None


def test_a_single_missing_day_inside_the_window_still_returns_unavailable() -> None:
    window = _full_window()
    del window[ANALYSIS_DATE - timedelta(days=15)]
    result = _run(window)

    assert result.status == "unavailable"
    assert result.unavailable_reason_code == "insufficient_rolling_weather_history"


# --- Category thresholds. ---


@pytest.mark.parametrize(
    "index,expected",
    [
        (0.0, "dry"),
        (0.32, "dry"),
        (0.33, "moderate"),
        (0.65, "moderate"),
        (0.66, "wet"),
        (1.0, "wet"),
    ],
)
def test_wetness_category_thresholds(index: float, expected: str) -> None:
    assert (
        wetness_category_from_index(index, dry_max=DRY_MAX, moderate_max=MODERATE_MAX) == expected
    )


# --- Failure / fallback behavior (never raises, never fails the analysis). ---


def test_missing_model_artifact_returns_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise() -> None:
        raise ModelArtifactNotFoundError("no artifact on disk")

    monkeypatch.setattr(inference, "_load_model", _raise)
    result = _run(_full_window())

    assert result.status == "unavailable"
    assert result.unavailable_reason_code == "model_artifact_not_found"
    assert result.wetness_index is None


def test_incompatible_model_artifact_returns_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise() -> None:
        raise IncompatibleModelError("feature schema mismatch")

    monkeypatch.setattr(inference, "_load_model", _raise)
    result = _run(_full_window())

    assert result.status == "unavailable"
    assert result.unavailable_reason_code == "model_artifact_incompatible"


def test_non_finite_prediction_returns_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _predict(_vector):
        raise RuntimeError("AI Soil Moisture Proxy model produced a non-finite prediction")

    monkeypatch.setattr(inference, "_load_model", lambda: _FakeModel(_predict))
    result = _run(_full_window())

    assert result.status == "unavailable"
    assert result.unavailable_reason_code == "non_finite_prediction"


def test_unexpected_inference_exception_returns_unavailable_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _predict(_vector):
        raise ValueError("boom")

    monkeypatch.setattr(inference, "_load_model", lambda: _FakeModel(_predict))
    result = _run(_full_window())

    assert result.status == "unavailable"
    assert result.unavailable_reason_code == "inference_error"


def test_unavailable_result_never_exposes_exception_internals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_looking_message = "Authorization: Bearer super-secret-token-should-never-leak"

    def _predict(_vector):
        raise ValueError(secret_looking_message)

    monkeypatch.setattr(inference, "_load_model", lambda: _FakeModel(_predict))
    result = _run(_full_window())

    assert result.status == "unavailable"
    for value in (
        result.model_version,
        result.unavailable_reason_code,
        *result.reasons,
        *result.warnings,
        *result.limitations,
    ):
        assert "secret" not in str(value).lower()
        assert "Bearer" not in str(value)
