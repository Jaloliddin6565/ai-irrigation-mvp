import math
from datetime import date
from pathlib import Path

import pytest

from app.ai.features import FEATURE_ORDER_V0_1, FEATURE_ORDER_V0_2, build_feature_vector
from app.ai.metadata import ModelMetadata, ModelMetrics, TrainTestSplitMethod
from app.ai.model import (
    SAFE_RANGE_BY_TARGET_KIND,
    AISoilMoistureProxyModel,
    IncompatibleModelError,
    ModelArtifactNotFoundError,
    default_hyperparameters,
    save_artifact,
    train_model,
)
from app.ai.schemas import AIFeatureVectorV2

_TEST_MODEL_VERSION = "ai_soil_moisture_proxy_v0.1"

# A small, fixed (non-random) synthetic dataset: y is a deterministic linear
# function of two of the thirteen v0.1 features so a tiny XGBoost model can
# fit it well without needing a large sample.
_ROWS = [
    ([0.0, 0.0] + [0.0] * 11, 0.20),
    ([1.0, 0.0] + [0.0] * 11, 0.22),
    ([2.0, 0.0] + [0.0] * 11, 0.24),
    ([0.0, 1.0] + [0.0] * 11, 0.19),
    ([1.0, 1.0] + [0.0] * 11, 0.21),
    ([3.0, 2.0] + [0.0] * 11, 0.27),
    ([4.0, 1.0] + [0.0] * 11, 0.28),
    ([2.0, 3.0] + [0.0] * 11, 0.23),
]


def _train_and_save(tmp_path: Path, *, model_version: str = _TEST_MODEL_VERSION) -> Path:
    X = [row for row, _ in _ROWS]
    y = [target for _, target in _ROWS]
    regressor = train_model(X, y)
    metadata = ModelMetadata(
        model_version=model_version,
        trained_at="2025-12-31",
        target_kind="volumetric_m3m3",
        feature_list=list(FEATURE_ORDER_V0_1),
        target_definition="test",
        training_samples=len(X),
        train_test_split=TrainTestSplitMethod(train_location_ids=["a"], test_location_ids=["b"]),
        metrics=ModelMetrics(rmse=0.01, mae=0.01, r2=0.9),
        weak_label_source="test",
        xgboost_version="3.4.0",
        hyperparameters=default_hyperparameters(),
        limitations=["test limitation"],
    )
    save_artifact(regressor, metadata, artifacts_dir=tmp_path)
    return tmp_path


def _sample_feature_vector():
    return build_feature_vector(
        day=date(2025, 6, 15),
        latitude=41.0,
        longitude=69.0,
        et0_mm=5.0,
        precipitation_mm=0.0,
        temperature_max_c=28.0,
        temperature_min_c=14.0,
        temperature_mean_c=21.0,
        relative_humidity_mean_pct=40.0,
        wind_speed_ms=2.5,
        shortwave_radiation_mj_m2=20.0,
    )


def _sample_feature_vector_v2() -> AIFeatureVectorV2:
    same_day = _sample_feature_vector().model_dump(
        exclude={
            "crop_type", "crop_stage", "days_after_planting", "soil_texture",
            "fao_estimated_depletion_fraction", "days_since_irrigation", "ndvi", "ndmi",
        }
    )
    return AIFeatureVectorV2(
        **same_day,
        precipitation_sum_3d=0.0,
        precipitation_sum_7d=0.0,
        precipitation_sum_14d=0.0,
        precipitation_sum_30d=0.0,
        et0_sum_3d=0.0,
        et0_sum_7d=0.0,
        et0_sum_14d=0.0,
        et0_sum_30d=0.0,
        vpd_mean_3d=0.0,
        vpd_mean_7d=0.0,
        temperature_mean_3d=0.0,
        temperature_mean_7d=0.0,
        shortwave_radiation_mean_7d=0.0,
        precipitation_minus_et0_3d=0.0,
        precipitation_minus_et0_7d=0.0,
        precipitation_minus_et0_14d=0.0,
        cumulative_water_deficit_30d=0.0,
    )


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    artifacts_dir = _train_and_save(tmp_path)

    model = AISoilMoistureProxyModel.load(_TEST_MODEL_VERSION, artifacts_dir=artifacts_dir)

    assert model.metadata.model_version == _TEST_MODEL_VERSION
    assert model.metadata.feature_list == list(FEATURE_ORDER_V0_1)


def test_load_raises_when_artifact_missing(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactNotFoundError):
        AISoilMoistureProxyModel.load(_TEST_MODEL_VERSION, artifacts_dir=tmp_path)


def test_load_raises_on_unsupported_model_version(tmp_path: Path) -> None:
    _train_and_save(tmp_path, model_version="ai_soil_moisture_proxy_v99.9")

    with pytest.raises(IncompatibleModelError, match="does not support"):
        AISoilMoistureProxyModel.load("ai_soil_moisture_proxy_v99.9", artifacts_dir=tmp_path)


def test_load_raises_on_feature_list_mismatch(tmp_path: Path) -> None:
    X = [row for row, _ in _ROWS]
    y = [target for _, target in _ROWS]
    regressor = train_model(X, y)
    metadata = ModelMetadata(
        model_version=_TEST_MODEL_VERSION,
        trained_at="2025-12-31",
        target_kind="volumetric_m3m3",
        feature_list=["only_one_feature"],
        target_definition="test",
        training_samples=len(X),
        train_test_split=TrainTestSplitMethod(train_location_ids=["a"], test_location_ids=["b"]),
        metrics=ModelMetrics(rmse=0.01, mae=0.01, r2=0.9),
        weak_label_source="test",
        xgboost_version="3.4.0",
        hyperparameters=default_hyperparameters(),
        limitations=["test limitation"],
    )
    save_artifact(regressor, metadata, artifacts_dir=tmp_path)

    with pytest.raises(IncompatibleModelError, match="feature_list"):
        AISoilMoistureProxyModel.load(_TEST_MODEL_VERSION, artifacts_dir=tmp_path)


def test_predict_returns_finite_value_within_safe_range(tmp_path: Path) -> None:
    artifacts_dir = _train_and_save(tmp_path)
    model = AISoilMoistureProxyModel.load(_TEST_MODEL_VERSION, artifacts_dir=artifacts_dir)
    safe_min, safe_max = SAFE_RANGE_BY_TARGET_KIND["volumetric_m3m3"]

    prediction = model.predict(_sample_feature_vector())

    assert math.isfinite(prediction.predicted_value)
    assert safe_min <= prediction.predicted_value <= safe_max
    assert prediction.model_version == _TEST_MODEL_VERSION
    assert prediction.target_kind == "volumetric_m3m3"
    assert prediction.unit == "m3/m3"
    assert prediction.feature_names_used == tuple(FEATURE_ORDER_V0_1)
    assert "proxy" in prediction.label.lower()
    assert "not" in prediction.limitation.lower()


def test_predict_clamps_out_of_range_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts_dir = _train_and_save(tmp_path)
    model = AISoilMoistureProxyModel.load(_TEST_MODEL_VERSION, artifacts_dir=artifacts_dir)
    _, safe_max = SAFE_RANGE_BY_TARGET_KIND["volumetric_m3m3"]

    monkeypatch.setattr(model._regressor, "predict", lambda _array: [999.0])

    prediction = model.predict(_sample_feature_vector())

    assert prediction.predicted_value == safe_max
    assert prediction.clamped_to_safe_range is True


def test_predict_raises_on_non_finite_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts_dir = _train_and_save(tmp_path)
    model = AISoilMoistureProxyModel.load(_TEST_MODEL_VERSION, artifacts_dir=artifacts_dir)

    monkeypatch.setattr(model._regressor, "predict", lambda _array: [float("nan")])

    with pytest.raises(RuntimeError, match="non-finite"):
        model.predict(_sample_feature_vector())


def test_predict_uses_wetness_index_range_for_that_target_kind(tmp_path: Path) -> None:
    # ai_soil_wetness_index_v0.1 expects the v0.2 (30-feature) schema, not v0.1's.
    extra = len(FEATURE_ORDER_V0_2) - len(FEATURE_ORDER_V0_1)
    X = [row + [0.0] * extra for row, _ in _ROWS]
    y = [target for _, target in _ROWS]
    regressor = train_model(X, y)
    metadata = ModelMetadata(
        model_version="ai_soil_wetness_index_v0.1",
        trained_at="2025-12-31",
        target_kind="wetness_index_0_1",
        feature_list=list(FEATURE_ORDER_V0_2),
        target_definition="test",
        training_samples=len(X),
        train_test_split=TrainTestSplitMethod(train_location_ids=["a"], test_location_ids=["b"]),
        metrics=ModelMetrics(rmse=0.01, mae=0.01, r2=0.9),
        weak_label_source="test",
        xgboost_version="3.4.0",
        hyperparameters=default_hyperparameters(),
        limitations=["test limitation"],
    )
    save_artifact(regressor, metadata, artifacts_dir=tmp_path)
    model = AISoilMoistureProxyModel.load("ai_soil_wetness_index_v0.1", artifacts_dir=tmp_path)

    prediction = model.predict(_sample_feature_vector_v2())

    assert prediction.target_kind == "wetness_index_0_1"
    assert prediction.unit == "index_0_1"
    assert prediction.safe_range_min == 0.0
    assert prediction.safe_range_max == 1.0
    assert "location-relative" in prediction.limitation.lower()
