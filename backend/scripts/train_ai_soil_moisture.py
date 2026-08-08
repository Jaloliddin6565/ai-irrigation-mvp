#!/usr/bin/env python
"""Train the AI Soil Moisture Proxy v0.2 / AI Soil Wetness Index v0.1
models from PUBLIC Open-Meteo data only (Phase 1.1 model-quality iteration).

Run from backend/ (with the project's virtualenv active):

    python scripts/train_ai_soil_moisture.py

=== Why this script exists (Phase 1.1) ===
Phase 1's ai_soil_moisture_proxy_v0.1 (same-day weather only, 13 features,
one calendar year) shipped an HONEST but unusable held-out-location result:
RMSE=0.0761 MAE=0.0647 R2=-0.135. Diagnosis (reproduced by this script's
`print_diagnosis` using the same 3-year dataset it trains on):
  1. Absolute root-zone soil moisture has a large LOCATION-SPECIFIC
     baseline (different climate/soil regimes across Uzbekistan) that
     thirteen same-day weather + lat/lon features cannot resolve for a
     location the model never saw during training — the per-location mean
     target varies far more than the day-to-day variation within any one
     location.
  2. Same-day weather under-determines soil moisture, which physically
     responds to *recent* wetting/drying history, not just today.
This script addresses (2) with antecedent/rolling features
(app/ai/features.py FEATURE_ORDER_V0_2) and (1) with a second, LOCATION-
RELATIVE target formulation (`wetness_index_from_value`) alongside the
original absolute one — both are trained and reported, never silently
substituting one for the other (see CLAUDE.md rule 3).

=== Data ===
Same Open-Meteo Archive API contract verified in Phase 1 (see
app/ai/dataset.py), now over 2023-01-01..2025-12-31 (3 recent completed
years, up from 1) for the same 15 bootstrap locations
(backend/config/ai_bootstrap_locations.yaml), fetched once and cached
locally (backend/.ai_dataset_cache/, gitignored) since this script is run
repeatedly while iterating on features/models.

=== Held-out-location validation (unchanged discipline) ===
The same 11 train / 4 test locations from Phase 1 are used, assigned
before any data was collected. Model SELECTION (which XGBoost
hyperparameters to use) is done with grouped (leave-one-training-location-
out) cross-validation on the 11 training locations only; the 4 held-out
test locations are touched exactly once, for final reporting — never used
to pick a model.

=== SoilGrids (public soil texture) ===
Investigated and NOT integrated this phase: the ISRIC SoilGrids v2.0 REST
API (https://rest.isric.org/soilgrids/v2.0/properties/query) returned
`null` for every property at every one of several tested Uzbekistan
coordinates (confirmed against a working non-Uzbekistan reference
coordinate that returned real values), indicating a coverage/service gap
for this region on the live REST endpoint rather than a request mistake.
Per the "don't fight it" instruction this is deferred to Phase 2 (candidate
options: ISRIC's WCS endpoint, or a bulk-downloaded raster clipped to
Uzbekistan).

If Open-Meteo collection fails, this script prints the exact failure and
exits non-zero. It never generates synthetic replacement data.
"""

import asyncio
import sys
from dataclasses import dataclass
from datetime import date

import httpx
import xgboost
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ai.dataset import CollectionFailure, fetch_location
from app.ai.features import (
    FEATURE_ORDER_V0_2,
    RawDailyRecord,
    build_rolling_feature_records,
    compute_location_climatology,
    wetness_index_from_value,
)
from app.ai.locations import BootstrapLocation, load_bootstrap_locations
from app.ai.metadata import (
    BaselineComparison,
    ModelMetadata,
    ModelMetrics,
    ModelSelectionMethod,
    TrainTestSplitMethod,
)
from app.ai.model import save_artifact, train_model
from app.ai.schemas import AIFeatureVectorV2, TargetKind
from app.core.http_client import RetryingHttpClient
from app.core.provider_errors import ProviderError
from app.settings import BACKEND_ROOT, CONFIG_DIR, get_settings

TRAIN_PERIOD_START = date(2023, 1, 1)
TRAIN_PERIOD_END = date(2025, 12, 31)
LOCATIONS_CONFIG_PATH = CONFIG_DIR / "ai_bootstrap_locations.yaml"
CACHE_DIR = BACKEND_ROOT / ".ai_dataset_cache"
MIN_TOTAL_SAMPLES = 500

LIMITATIONS_BY_TARGET_KIND: dict[TargetKind, list[str]] = {
    "volumetric_m3m3": [
        "This model estimates a MODELLED root-zone soil-moisture PROXY derived "
        "from public reanalysis data; it does not measure actual field soil "
        "moisture and has not been validated against any in-situ sensor.",
        "Absolute volumetric soil moisture has a large location-specific baseline "
        "(see this script's diagnosis output); held-out-location generalization "
        "is materially weaker than the wetness-index formulation trained on the "
        "same data — see ai_soil_wetness_index_v0.1's metadata for comparison.",
        "Training data covers a bootstrap set of ~15 representative Uzbekistan "
        "locations and 2023-2025; not validated across other years, crop types, "
        "or irrigation practices.",
        "The weak-label target itself is a model output (Open-Meteo/ERA5-Land "
        "derived), not ground truth.",
        "Not yet used to alter any irrigation recommendation or water-balance "
        "calculation — see CLAUDE.md.",
    ],
    "wetness_index_0_1": [
        "This index estimates a MODELLED, LOCATION-RELATIVE soil wetness proxy "
        "(0=driest, 1=wettest observed at training locations) derived from "
        "public reanalysis data; it is not a sensor measurement and not an "
        "absolute soil-moisture value.",
        "The 0-1 scale for each training location was defined using that "
        "location's own observed min/max over 2023-2025; a real new field's "
        "true climatology may differ from every bootstrap location, so the "
        "scale is not exactly calibrated for it.",
        "Training data covers a bootstrap set of ~15 representative Uzbekistan "
        "locations and 2023-2025; not validated across other years, crop types, "
        "or irrigation practices.",
        "The weak-label target itself is a model output (Open-Meteo/ERA5-Land "
        "derived), not ground truth.",
        "Not yet used to alter any irrigation recommendation or water-balance "
        "calculation — see CLAUDE.md.",
    ],
}

# Compact, hand-picked XGBoost hyperparameter candidates (not a grid search).
_XGB_CANDIDATES: list[dict[str, object]] = [
    {  # baseline, same as Phase 1 defaults
        "n_estimators": 200, "max_depth": 4, "learning_rate": 0.05,
        "subsample": 0.8, "colsample_bytree": 0.8,
        "objective": "reg:squarederror", "random_state": 42,
    },
    {  # shallower + more regularized
        "n_estimators": 300, "max_depth": 3, "learning_rate": 0.03,
        "min_child_weight": 5, "reg_alpha": 0.1, "reg_lambda": 2.0,
        "subsample": 0.8, "colsample_bytree": 0.8,
        "objective": "reg:squarederror", "random_state": 42,
    },
    {  # deeper, less subsampling
        "n_estimators": 150, "max_depth": 6, "learning_rate": 0.05,
        "min_child_weight": 1, "subsample": 0.7, "colsample_bytree": 0.7,
        "objective": "reg:squarederror", "random_state": 42,
    },
    {  # heavily regularized
        "n_estimators": 250, "max_depth": 4, "learning_rate": 0.04,
        "min_child_weight": 3, "reg_alpha": 1.0, "reg_lambda": 5.0,
        "subsample": 0.6, "colsample_bytree": 0.6,
        "objective": "reg:squarederror", "random_state": 42,
    },
    {  # low learning rate, more trees
        "n_estimators": 500, "max_depth": 4, "learning_rate": 0.02,
        "min_child_weight": 3, "subsample": 0.8, "colsample_bytree": 0.8,
        "objective": "reg:squarederror", "random_state": 42,
    },
]


def _rmse(y_true: list[float], y_pred: list[float]) -> float:
    return (sum((t - p) ** 2 for t, p in zip(y_true, y_pred, strict=True)) / len(y_true)) ** 0.5


def _mae(y_true: list[float], y_pred: list[float]) -> float:
    return sum(abs(t - p) for t, p in zip(y_true, y_pred, strict=True)) / len(y_true)


def _r2(y_true: list[float], y_pred: list[float]) -> float:
    mean_true = sum(y_true) / len(y_true)
    ss_res = sum((t - p) ** 2 for t, p in zip(y_true, y_pred, strict=True))
    ss_tot = sum((t - mean_true) ** 2 for t in y_true)
    if ss_tot == 0:
        return 0.0
    return 1.0 - ss_res / ss_tot


def _metrics(y_true: list[float], y_pred: list[float]) -> ModelMetrics:
    return ModelMetrics(
        rmse=_rmse(y_true, y_pred), mae=_mae(y_true, y_pred), r2=_r2(y_true, y_pred)
    )


@dataclass
class LocationDataset:
    location: BootstrapLocation
    rows: list[tuple[RawDailyRecord, AIFeatureVectorV2]]


async def collect_all(locations: list[BootstrapLocation]) -> list[LocationDataset]:
    settings = get_settings()
    results: list[LocationDataset] = []
    async with RetryingHttpClient(
        provider="open-meteo-ai-bootstrap",
        timeout_seconds=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
        retry_base_delay_seconds=settings.http_retry_base_delay_seconds,
        retry_max_delay_seconds=settings.http_retry_max_delay_seconds,
    ) as client:
        for location in locations:
            print(f"  fetching {location.id} ({location.latitude}, {location.longitude}) ...")
            records = await fetch_location(
                client,
                settings.open_meteo_archive_url,
                location,
                TRAIN_PERIOD_START,
                TRAIN_PERIOD_END,
                cache_dir=CACHE_DIR,
            )
            rows = build_rolling_feature_records(records)
            print(f"    -> {len(records)} raw days -> {len(rows)} rows with full 30d history")
            results.append(LocationDataset(location=location, rows=rows))
    return results


def _feature_arrays(rows: list[tuple[RawDailyRecord, AIFeatureVectorV2]]) -> list[list[float]]:
    dumped = [vec.model_dump() for _, vec in rows]
    return [[float(values[name]) for name in FEATURE_ORDER_V0_2] for values in dumped]


def print_diagnosis(datasets: list[LocationDataset]) -> None:
    print("\n=== Diagnosis: per-location target statistics (absolute m3/m3) ===")
    print(
        f"{'location':24s} {'split':6s} {'n':>5s} {'mean':>8s} {'std':>8s} "
        f"{'min':>8s} {'max':>8s}"
    )
    all_means = []
    for ds in datasets:
        values = [r.root_zone_soil_moisture_proxy_m3m3 for r, _ in ds.rows]
        n = len(values)
        mean = sum(values) / n
        var = sum((v - mean) ** 2 for v in values) / n
        std = var**0.5
        all_means.append((ds.location.split, mean))
        print(
            f"{ds.location.id:24s} {ds.location.split:6s} {n:5d} {mean:8.4f} {std:8.4f} "
            f"{min(values):8.4f} {max(values):8.4f}"
        )

    train_location_means = [m for split, m in all_means if split == "train"]
    test_location_means = [m for split, m in all_means if split == "test"]
    between_location_std_train = (
        sum(
            (m - sum(train_location_means) / len(train_location_means)) ** 2
            for m in train_location_means
        )
        / len(train_location_means)
    ) ** 0.5
    print(
        f"\nBetween-location std of per-location MEAN (train locations): "
        f"{between_location_std_train:.4f} m3/m3"
    )
    train_mean_of_means = sum(train_location_means) / len(train_location_means)
    test_mean_of_means = sum(test_location_means) / len(test_location_means)
    print(
        f"Train-location mean of means: {train_mean_of_means:.4f} "
        f"| Test-location mean of means: {test_mean_of_means:.4f}"
    )
    print(
        "-> If this between-location gap is large relative to typical within-location "
        "day-to-day variation (std column above), the target's absolute level is "
        "dominated by WHICH location, not by weather -- exactly what thirteen/thirty "
        "weather+lat/lon features struggle to infer for an unseen location."
    )


def select_xgboost_hyperparameters(
    X: list[list[float]], y: list[float], groups: list[str]
) -> tuple[dict[str, object], float, int, int]:
    """Grouped (leave-one-training-location-out) CV over `_XGB_CANDIDATES`.
    Never touches the final held-out test locations. Returns
    (best_params, best_mean_cv_r2, n_candidates, n_folds)."""
    unique_groups = sorted(set(groups))
    n_folds = len(unique_groups)
    group_indices = {g: i for i, g in enumerate(unique_groups)}
    group_ids = [group_indices[g] for g in groups]
    splitter = GroupKFold(n_splits=n_folds)

    best_params: dict[str, object] | None = None
    best_score = float("-inf")
    for params in _XGB_CANDIDATES:
        fold_r2: list[float] = []
        for train_idx, val_idx in splitter.split(X, y, groups=group_ids):
            X_train = [X[i] for i in train_idx]
            y_train = [y[i] for i in train_idx]
            X_val = [X[i] for i in val_idx]
            y_val = [y[i] for i in val_idx]
            model = train_model(X_train, y_train, hyperparameters=params)
            y_pred = [float(p) for p in model.predict(X_val)]
            fold_r2.append(_r2(y_val, y_pred))
        mean_r2 = sum(fold_r2) / len(fold_r2)
        print(f"    candidate {params} -> mean CV R2 = {mean_r2:.4f}")
        if mean_r2 > best_score:
            best_score = mean_r2
            best_params = params

    assert best_params is not None
    return best_params, best_score, len(_XGB_CANDIDATES), n_folds


def run_baselines(
    X_train: list[list[float]], y_train: list[float], X_test: list[list[float]], y_test: list[float]
) -> BaselineComparison:
    global_mean = sum(y_train) / len(y_train)
    mean_pred = [global_mean] * len(y_test)

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    ridge.fit(X_train, y_train)
    ridge_pred = [float(p) for p in ridge.predict(X_test)]

    forest = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42, n_jobs=-1)
    forest.fit(X_train, y_train)
    forest_pred = [float(p) for p in forest.predict(X_test)]

    return BaselineComparison(
        global_mean_baseline=_metrics(y_test, mean_pred),
        ridge_regression=_metrics(y_test, ridge_pred),
        random_forest=_metrics(y_test, forest_pred),
    )


def train_and_report(
    *,
    target_kind: TargetKind,
    model_version: str,
    target_definition: str,
    train_rows: list[tuple[RawDailyRecord, AIFeatureVectorV2]],
    test_rows: list[tuple[RawDailyRecord, AIFeatureVectorV2]],
    train_groups: list[str],
    train_location_ids: list[str],
    test_location_ids: list[str],
    y_train: list[float],
    y_test: list[float],
) -> ModelMetadata:
    X_train = _feature_arrays(train_rows)
    X_test = _feature_arrays(test_rows)

    print(f"\n--- {model_version} ({target_kind}) ---")
    print("Baselines (fit on train locations, evaluated on held-out test locations):")
    baselines = run_baselines(X_train, y_train, X_test, y_test)
    print(f"  global mean : {baselines.global_mean_baseline}")
    print(f"  ridge       : {baselines.ridge_regression}")
    print(f"  random forest: {baselines.random_forest}")

    print("Selecting XGBoost hyperparameters via grouped (leave-one-location-out) CV...")
    best_params, best_cv_r2, n_candidates, n_folds = select_xgboost_hyperparameters(
        X_train, y_train, train_groups
    )
    print(f"  selected: {best_params} (mean CV R2={best_cv_r2:.4f})")

    print("Refitting selected XGBoost on all training rows...")
    final_model = train_model(X_train, y_train, hyperparameters=best_params)
    y_pred = [float(p) for p in final_model.predict(X_test)]
    final_metrics = _metrics(y_test, y_pred)
    print(f"  FINAL held-out-location metrics: {final_metrics}")

    metadata = ModelMetadata(
        model_version=model_version,
        trained_at=TRAIN_PERIOD_END.isoformat(),
        target_kind=target_kind,
        feature_list=list(FEATURE_ORDER_V0_2),
        target_definition=target_definition,
        training_samples=len(X_train),
        train_test_split=TrainTestSplitMethod(
            train_location_ids=train_location_ids, test_location_ids=test_location_ids
        ),
        metrics=final_metrics,
        model_selection=ModelSelectionMethod(
            candidates_tried=n_candidates, cv_folds=n_folds, best_candidate_mean_cv_r2=best_cv_r2
        ),
        baseline_comparison=baselines,
        weak_label_source=(
            "Open-Meteo Archive API (ERA5-Land reanalysis-derived hourly soil moisture), "
            f"{TRAIN_PERIOD_START.isoformat()} to {TRAIN_PERIOD_END.isoformat()}, "
            "15 bootstrap Uzbekistan locations (backend/config/ai_bootstrap_locations.yaml)."
        ),
        xgboost_version=xgboost.__version__,
        hyperparameters=best_params,
        limitations=LIMITATIONS_BY_TARGET_KIND[target_kind],
    )
    out_dir = save_artifact(final_model, metadata)
    print(f"Saved to {out_dir}")
    return metadata


def main() -> int:
    print(f"Loading bootstrap locations from {LOCATIONS_CONFIG_PATH}")
    config = load_bootstrap_locations(LOCATIONS_CONFIG_PATH)
    print(
        f"  {len(config.locations)} locations "
        f"({len(config.train_locations)} train / {len(config.test_locations)} test)"
    )

    print(
        f"Collecting Open-Meteo data for {TRAIN_PERIOD_START} .. {TRAIN_PERIOD_END} "
        "(cached locally after first fetch)..."
    )
    try:
        datasets = asyncio.run(collect_all(config.locations))
    except CollectionFailure as exc:
        print(f"\nSTOP: public data collection failed.\n{exc}", file=sys.stderr)
        return 1
    except ProviderError as exc:
        print(f"\nSTOP: public data collection failed.\n{exc.message_en}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(
            f"\nSTOP: public data collection failed.\n{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    total_rows = sum(len(ds.rows) for ds in datasets)
    print(f"\nTotal rows with full 30-day antecedent history: {total_rows}")
    if total_rows < MIN_TOTAL_SAMPLES:
        print(
            f"STOP: only {total_rows} usable rows (< {MIN_TOTAL_SAMPLES} minimum).",
            file=sys.stderr,
        )
        return 1

    print_diagnosis(datasets)

    train_datasets = [ds for ds in datasets if ds.location.split == "train"]
    test_datasets = [ds for ds in datasets if ds.location.split == "test"]
    if not test_datasets:
        print("STOP: no rows from any test-split location.", file=sys.stderr)
        return 1

    train_rows = [row for ds in train_datasets for row in ds.rows]
    test_rows = [row for ds in test_datasets for row in ds.rows]
    train_groups = [record.location_id for record, _ in train_rows]
    train_location_ids = [ds.location.id for ds in train_datasets]
    test_location_ids = [ds.location.id for ds in test_datasets]

    # --- Target A: absolute volumetric proxy (m3/m3), unchanged definition. ---
    y_train_abs = [record.root_zone_soil_moisture_proxy_m3m3 for record, _ in train_rows]
    y_test_abs = [record.root_zone_soil_moisture_proxy_m3m3 for record, _ in test_rows]
    train_and_report(
        target_kind="volumetric_m3m3",
        model_version="ai_soil_moisture_proxy_v0.2",
        target_definition=(
            "Depth-weighted blend of Open-Meteo's modelled hourly soil_moisture_7_to_28cm "
            "and soil_moisture_28_to_100cm layers (weights 19/72 and 53/72), aggregated to "
            "a daily mean. A public reanalysis-derived weak label, not a sensor measurement."
        ),
        train_rows=train_rows,
        test_rows=test_rows,
        train_groups=train_groups,
        train_location_ids=train_location_ids,
        test_location_ids=test_location_ids,
        y_train=y_train_abs,
        y_test=y_test_abs,
    )

    # --- Target B: location-relative wetness index (0-1). Each location's
    # own [min, max] is computed from ITS OWN full collected series only. ---
    climatology_by_location = {
        ds.location.id: compute_location_climatology([r for r, _ in ds.rows]) for ds in datasets
    }
    y_train_wetness = [
        wetness_index_from_value(
            record.root_zone_soil_moisture_proxy_m3m3,
            location_min=climatology_by_location[record.location_id][0],
            location_max=climatology_by_location[record.location_id][1],
        )
        for record, _ in train_rows
    ]
    y_test_wetness = [
        wetness_index_from_value(
            record.root_zone_soil_moisture_proxy_m3m3,
            location_min=climatology_by_location[record.location_id][0],
            location_max=climatology_by_location[record.location_id][1],
        )
        for record, _ in test_rows
    ]
    train_and_report(
        target_kind="wetness_index_0_1",
        model_version="ai_soil_wetness_index_v0.1",
        target_definition=(
            "Depth-weighted root-zone soil-moisture proxy (see ai_soil_moisture_proxy_v0.2 "
            "target_definition), min-max normalized to [0, 1] using EACH location's own "
            "observed min/max over its collected 2023-2025 series (app/ai/features.py "
            "wetness_index_from_value). A location-relative index, not an absolute value."
        ),
        train_rows=train_rows,
        test_rows=test_rows,
        train_groups=train_groups,
        train_location_ids=train_location_ids,
        test_location_ids=test_location_ids,
        y_train=y_train_wetness,
        y_test=y_test_wetness,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
