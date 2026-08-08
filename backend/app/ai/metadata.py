"""Model metadata: the provenance/limitations record that must travel with
every trained AI Soil Moisture Proxy artifact (CLAUDE.md rule 3/4 spirit —
applied here to a model artifact rather than an Analysis result).

metadata.json sits alongside model.json in the artifact directory
(app/ai/artifacts/<model_version>/) and is re-read on every model load
(app/ai/model.py) so a stale or incompatible artifact fails loudly instead
of being used silently.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.ai.schemas import TargetKind


class TrainTestSplitMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: str = "location_group_holdout"
    description: str = (
        "Locations were assigned to train/test before any data was collected "
        "(backend/config/ai_bootstrap_locations.yaml `split` field). No day "
        "from a test location appears in training, so metrics measure "
        "generalization to an unseen location rather than interpolation "
        "between nearby days at the same location."
    )
    train_location_ids: list[str]
    test_location_ids: list[str]


class ModelMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    rmse: float
    mae: float
    r2: float
    note: str = (
        "Performance against PUBLIC MODELLED SOIL-MOISTURE WEAK LABELS "
        "(Open-Meteo reanalysis-derived root-zone proxy), evaluated only on "
        "held-out test locations. This is NOT accuracy against real soil "
        "sensors — no in-situ Uzbekistan ground truth exists yet."
    )


class ModelSelectionMethod(BaseModel):
    """How `hyperparameters` were chosen (Phase 1.1) — see
    backend/scripts/train_ai_soil_moisture.py `select_xgboost_hyperparameters`.
    Never tuned against the final held-out test locations; only against a
    grouped cross-validation split of the training locations."""

    model_config = ConfigDict(frozen=True)

    method: str = "grouped_cv_on_training_locations"
    description: str = (
        "A compact set of XGBoost hyperparameter candidates was scored with "
        "GroupKFold cross-validation (groups = training locations only), "
        "never touching the final held-out test locations. The candidate "
        "with the best mean CV R2 was refit on all training rows."
    )
    candidates_tried: int
    cv_folds: int
    best_candidate_mean_cv_r2: float


class BaselineComparison(BaseModel):
    """Metrics for a simpler model evaluated with the identical held-out-
    location split, for honest comparison — see CLAUDE.md "no invented
    performance values" and Phase 1.1 diagnosis."""

    model_config = ConfigDict(frozen=True)

    global_mean_baseline: ModelMetrics
    ridge_regression: ModelMetrics | None = None
    random_forest: ModelMetrics | None = None


class ModelMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_version: str
    trained_at: str  # ISO 8601 date; the training script's collection period end date
    # What this model's numeric output represents: an absolute volumetric
    # proxy (m3/m3) or a location-relative 0-1 wetness index — see
    # app/ai/features.py `wetness_index_from_value`. Defaults to the
    # original v0.1 absolute-target formulation for older metadata.json
    # files saved before this field existed.
    target_kind: TargetKind = "volumetric_m3m3"
    feature_list: list[str]
    target_definition: str
    training_samples: int
    train_test_split: TrainTestSplitMethod
    metrics: ModelMetrics
    model_selection: ModelSelectionMethod | None = None
    baseline_comparison: BaselineComparison | None = None
    weak_label_source: str
    xgboost_version: str
    hyperparameters: dict[str, object]
    limitations: list[str]


DEFAULT_LIMITATIONS: list[str] = [
    "This model estimates a MODELLED root-zone soil-moisture PROXY derived "
    "from public reanalysis data; it does not measure actual field soil "
    "moisture and has not been validated against any in-situ sensor.",
    "Training data covers a bootstrap set of ~15 representative Uzbekistan "
    "locations and one historical period; it has not been validated across "
    "multiple years, crop types, or irrigation practices.",
    "The weak-label target itself is a model output (Open-Meteo/ERA5-Land "
    "derived), not ground truth, so this model can only ever be as accurate "
    "as that upstream reanalysis product.",
    "Not yet used to alter any irrigation recommendation or water-balance "
    "calculation (Phase 1 only) — see CLAUDE.md.",
]


def save_metadata(metadata: ModelMetadata, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(metadata.model_dump(), indent=2, ensure_ascii=False)
    path.write_text(payload, encoding="utf-8")


def load_metadata(path: Path) -> ModelMetadata:
    if not path.exists():
        raise FileNotFoundError(f"Model metadata not found at {path}")
    return ModelMetadata.model_validate(json.loads(path.read_text(encoding="utf-8")))
