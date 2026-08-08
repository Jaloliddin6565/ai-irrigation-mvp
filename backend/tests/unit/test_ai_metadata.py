import json
from pathlib import Path

import pytest

from app.ai.metadata import (
    DEFAULT_LIMITATIONS,
    BaselineComparison,
    ModelMetadata,
    ModelMetrics,
    ModelSelectionMethod,
    TrainTestSplitMethod,
    load_metadata,
    save_metadata,
)


def _sample_metadata() -> ModelMetadata:
    return ModelMetadata(
        model_version="ai_soil_moisture_proxy_v0.1",
        trained_at="2025-12-31",
        feature_list=["et0_mm", "precipitation_mm"],
        target_definition="test target",
        training_samples=1234,
        train_test_split=TrainTestSplitMethod(
            train_location_ids=["a", "b"], test_location_ids=["c"]
        ),
        metrics=ModelMetrics(rmse=0.05, mae=0.03, r2=0.6),
        weak_label_source="Open-Meteo Archive API test",
        xgboost_version="2.1.4",
        hyperparameters={"n_estimators": 200},
        limitations=DEFAULT_LIMITATIONS,
    )


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    metadata = _sample_metadata()
    path = tmp_path / "metadata.json"

    save_metadata(metadata, path)
    loaded = load_metadata(path)

    assert loaded == metadata


def test_load_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_metadata(tmp_path / "does_not_exist.json")


def test_default_limitations_state_it_is_not_a_measurement() -> None:
    combined = " ".join(DEFAULT_LIMITATIONS).lower()
    assert "does not measure actual field soil moisture" in combined


def test_metrics_note_states_weak_label_not_sensor_ground_truth() -> None:
    note = ModelMetrics(rmse=0.1, mae=0.05, r2=0.5).note.lower()
    assert "weak label" in note
    assert "not" in note and "sensor" in note


def test_target_kind_defaults_to_volumetric() -> None:
    metadata = _sample_metadata()
    assert metadata.target_kind == "volumetric_m3m3"


def test_wetness_index_target_kind_round_trips(tmp_path: Path) -> None:
    metadata = _sample_metadata().model_copy(update={"target_kind": "wetness_index_0_1"})
    path = tmp_path / "metadata.json"

    save_metadata(metadata, path)
    loaded = load_metadata(path)

    assert loaded.target_kind == "wetness_index_0_1"


def test_loading_metadata_without_target_kind_field_defaults_backward_compatibly(
    tmp_path: Path,
) -> None:
    # Simulates a Phase 1 metadata.json saved before `target_kind` existed.
    legacy_payload = _sample_metadata().model_dump()
    del legacy_payload["target_kind"]
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    loaded = load_metadata(path)

    assert loaded.target_kind == "volumetric_m3m3"


def test_model_selection_and_baseline_comparison_are_optional_and_round_trip(
    tmp_path: Path,
) -> None:
    metadata = _sample_metadata().model_copy(
        update={
            "model_selection": ModelSelectionMethod(
                candidates_tried=5, cv_folds=11, best_candidate_mean_cv_r2=0.42
            ),
            "baseline_comparison": BaselineComparison(
                global_mean_baseline=ModelMetrics(rmse=0.08, mae=0.06, r2=0.0),
            ),
        }
    )
    path = tmp_path / "metadata.json"

    save_metadata(metadata, path)
    loaded = load_metadata(path)

    assert loaded.model_selection is not None
    assert loaded.model_selection.candidates_tried == 5
    assert loaded.baseline_comparison is not None
    assert loaded.baseline_comparison.ridge_regression is None
