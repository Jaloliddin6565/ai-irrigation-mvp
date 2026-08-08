"""Deterministic feature construction for the AI Soil Moisture Proxy model.

No I/O and no randomness here — this module only transforms values already
retrieved by a caller (the training script, or in Phase 2 a live provider).
Mirrors the app/domain/ discipline (CLAUDE.md rule 1) even though app/ai/ is
not itself under app/domain/.

Variable names/units below were confirmed against a real Open-Meteo Archive
API response on 2026-08-08 (see backend/scripts/train_ai_soil_moisture.py
module docstring for the exact request). In particular:
  - Daily block exposes `relative_humidity_2m_mean` directly (no need to
    aggregate hourly RH ourselves).
  - Vapour pressure deficit is NOT in the daily block, so it is computed
    locally here with the standard FAO-56 saturation/actual vapour pressure
    formulas from temperature_max_c/temperature_min_c/RH mean (see
    `calculate_vpd_kpa`).
  - Soil moisture is only exposed hourly, as depth-band volumetric water
    content (m3/m3): `soil_moisture_7_to_28cm` and `soil_moisture_28_to_100cm`
    are the closest available layers to the 9-27cm/27-81cm root-zone bands
    requested for this MVP (Open-Meteo does not expose those exact
    boundaries) — see `aggregate_root_zone_soil_moisture`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.ai.schemas import AIFeatureVector, AIFeatureVectorV2

# Canonical order of the v0.1 numeric feature array fed to XGBoost. This is
# persisted verbatim in every model's metadata.json (app/ai/metadata.py) and
# re-validated on load (app/ai/model.py) so a model can never silently be
# fed a differently-ordered or differently-shaped vector.
FEATURE_ORDER_V0_1: tuple[str, ...] = (
    "et0_mm",
    "precipitation_mm",
    "temperature_max_c",
    "temperature_min_c",
    "temperature_mean_c",
    "relative_humidity_mean_pct",
    "vpd_kpa",
    "wind_speed_ms",
    "shortwave_radiation_mj_m2",
    "day_of_year",
    "month",
    "latitude",
    "longitude",
)

# Minimum fraction of a day's expected hourly readings that must be present
# for that day's hourly-to-daily aggregate to be accepted; otherwise the day
# is dropped rather than averaged over a skewed partial day (same
# never-fabricate-a-gap principle as app/providers/weather/open_meteo.py).
_MIN_HOURLY_COMPLETENESS = 1.0  # require all 24 hours; Open-Meteo archive
# (ERA5-Land reanalysis) is a complete historical record, so a partial day
# indicates a real response problem worth dropping rather than smoothing over.

# Depth-weighted blend of the two available hourly soil-moisture layers,
# approximating the 9-81cm root-zone band requested for this MVP. Weights
# are the overlap (in cm) of each Open-Meteo layer with the [9, 81]cm target
# window, normalized to sum to 1:
#   soil_moisture_7_to_28cm  overlaps [9, 28] -> 19 cm
#   soil_moisture_28_to_100cm overlaps [28, 81] -> 53 cm
#   total target window       [9, 81]          -> 72 cm
# This is a documented geometric approximation, not a measured integral —
# Open-Meteo does not expose finer-grained depth boundaries.
_SHALLOW_LAYER_WEIGHT = 19.0 / 72.0
_DEEP_LAYER_WEIGHT = 53.0 / 72.0


def calculate_vpd_kpa(
    *, temperature_max_c: float, temperature_min_c: float, relative_humidity_mean_pct: float
) -> float:
    """FAO-56 daily vapour pressure deficit (kPa) from Tmax/Tmin/RH-mean.

    Saturation vapour pressure at each extreme uses the standard Tetens-form
    FAO-56 equation e0(T) = 0.6108 * exp(17.27*T / (T+237.3)); the day's
    saturation vapour pressure is the mean of e0(Tmax) and e0(Tmin)
    (FAO-56 eq. 11/12). Actual vapour pressure is approximated as
    es * RH_mean/100 — FAO-56's preferred ea formula needs RHmax/RHmin
    separately, which Open-Meteo's daily block does not expose; using the
    daily mean RH here is a documented simplification, not a measurement.
    """
    if temperature_max_c < temperature_min_c:
        raise ValueError("temperature_max_c must be >= temperature_min_c")
    if not (0.0 <= relative_humidity_mean_pct <= 100.0):
        raise ValueError("relative_humidity_mean_pct must be in [0, 100]")

    def _saturation_vapour_pressure_kpa(temp_c: float) -> float:
        return 0.6108 * pow(2.718281828459045, (17.27 * temp_c) / (temp_c + 237.3))

    es_kpa = (
        _saturation_vapour_pressure_kpa(temperature_max_c)
        + _saturation_vapour_pressure_kpa(temperature_min_c)
    ) / 2.0
    ea_kpa = es_kpa * (relative_humidity_mean_pct / 100.0)
    return max(0.0, es_kpa - ea_kpa)


def aggregate_hourly_to_daily(
    timestamps: Sequence[datetime], values: Sequence[float], *, expected_hours_per_day: int = 24
) -> dict[date, float]:
    """Mean-aggregate hourly readings into daily values.

    A calendar day is included only if it has at least
    `expected_hours_per_day * _MIN_HOURLY_COMPLETENESS` readings; otherwise
    it is omitted (a real, reported gap — never a fabricated/partial mean).
    """
    if len(timestamps) != len(values):
        raise ValueError("timestamps and values must be the same length")

    by_day: dict[date, list[float]] = {}
    for ts, value in zip(timestamps, values, strict=True):
        by_day.setdefault(ts.date(), []).append(value)

    min_required = expected_hours_per_day * _MIN_HOURLY_COMPLETENESS
    return {
        day: sum(day_values) / len(day_values)
        for day, day_values in by_day.items()
        if len(day_values) >= min_required
    }


def aggregate_root_zone_soil_moisture(
    *, soil_moisture_7_to_28cm_m3m3: float, soil_moisture_28_to_100cm_m3m3: float
) -> float:
    """Depth-weighted root-zone soil-moisture PROXY (m3/m3) — see module
    docstring for the weighting derivation. This is the v0.1 weak-label
    target; it is a public reanalysis model output, not a sensor
    measurement."""
    return (
        _SHALLOW_LAYER_WEIGHT * soil_moisture_7_to_28cm_m3m3
        + _DEEP_LAYER_WEIGHT * soil_moisture_28_to_100cm_m3m3
    )


def build_feature_vector(
    *,
    day: date,
    latitude: float,
    longitude: float,
    et0_mm: float,
    precipitation_mm: float,
    temperature_max_c: float,
    temperature_min_c: float,
    temperature_mean_c: float,
    relative_humidity_mean_pct: float,
    wind_speed_ms: float,
    shortwave_radiation_mj_m2: float,
) -> AIFeatureVector:
    """Build one v0.1 AIFeatureVector for a single location-day from already
    fetched/validated public weather values."""
    vpd_kpa = calculate_vpd_kpa(
        temperature_max_c=temperature_max_c,
        temperature_min_c=temperature_min_c,
        relative_humidity_mean_pct=relative_humidity_mean_pct,
    )
    return AIFeatureVector(
        et0_mm=et0_mm,
        precipitation_mm=precipitation_mm,
        temperature_max_c=temperature_max_c,
        temperature_min_c=temperature_min_c,
        temperature_mean_c=temperature_mean_c,
        relative_humidity_mean_pct=relative_humidity_mean_pct,
        vpd_kpa=vpd_kpa,
        wind_speed_ms=wind_speed_ms,
        shortwave_radiation_mj_m2=shortwave_radiation_mj_m2,
        day_of_year=day.timetuple().tm_yday,
        month=day.month,
        latitude=latitude,
        longitude=longitude,
    )


def feature_vector_to_array(
    vector: AIFeatureVector | AIFeatureVectorV2, *, feature_order: Sequence[str]
) -> list[float]:
    """Flatten a feature vector into a plain list in `feature_order`, the
    exact order the model expects (see FEATURE_ORDER_V0_1/FEATURE_ORDER_V0_2)."""
    values = vector.model_dump()
    missing = [name for name in feature_order if name not in values]
    if missing:
        raise ValueError(f"feature vector is missing required field(s): {missing}")
    return [float(values[name]) for name in feature_order]


# ============================================================================
# Phase 1.1: antecedent/rolling features + location-relative wetness index.
#
# Diagnosis (see backend/scripts/train_ai_soil_moisture.py module docstring
# for the full write-up): v0.1's held-out-location R2 was negative because
# (a) same-day weather alone under-determines soil moisture, which responds
# to *recent* wetting/drying history, and (b) absolute volumetric soil
# moisture has a large location-specific baseline (soil/climate regime) that
# thirteen same-day weather + lat/lon features cannot resolve for a location
# the model never saw. FEATURE_ORDER_V0_2 addresses (a); the wetness-index
# target below addresses (b) by removing each location's own baseline before
# training, so the model only has to learn the (more transferable) relative
# wetting/drying dynamics.
# ============================================================================


@dataclass(frozen=True)
class RawDailyRecord:
    """One location-day of already-fetched public weather + the weak-label
    root-zone soil-moisture proxy — the shared input both `build_feature_vector`
    (same-day) and `build_rolling_feature_records` (antecedent) are built
    from. See app/ai/dataset.py for how this is populated from Open-Meteo."""

    location_id: str
    date: date
    latitude: float
    longitude: float
    et0_mm: float
    precipitation_mm: float
    temperature_max_c: float
    temperature_min_c: float
    temperature_mean_c: float
    relative_humidity_mean_pct: float
    wind_speed_ms: float
    shortwave_radiation_mj_m2: float
    root_zone_soil_moisture_proxy_m3m3: float


# Canonical order of the v0.2 numeric feature array (same-day + antecedent).
# Used by both `ai_soil_moisture_proxy_v0.2` (absolute target) and
# `ai_soil_wetness_index_v0.1` (location-relative target) — they share one
# feature engine and differ only in target/label/safe-range (see
# app/ai/model.py `TARGET_KIND_BY_MODEL_VERSION`).
FEATURE_ORDER_V0_2: tuple[str, ...] = FEATURE_ORDER_V0_1 + (
    "precipitation_sum_3d",
    "precipitation_sum_7d",
    "precipitation_sum_14d",
    "precipitation_sum_30d",
    "et0_sum_3d",
    "et0_sum_7d",
    "et0_sum_14d",
    "et0_sum_30d",
    "vpd_mean_3d",
    "vpd_mean_7d",
    "temperature_mean_3d",
    "temperature_mean_7d",
    "shortwave_radiation_mean_7d",
    "precipitation_minus_et0_3d",
    "precipitation_minus_et0_7d",
    "precipitation_minus_et0_14d",
    "cumulative_water_deficit_30d",
)

# Largest rolling window used below; a record needs this many contiguous
# antecedent days (including itself) present before any rolling feature can
# be computed for it — see `build_rolling_feature_records`.
_MAX_ROLLING_WINDOW_DAYS = 30


def _sum_over(window: Sequence[RawDailyRecord], field: str, n: int) -> float:
    return sum(getattr(r, field) for r in window[:n])


def _mean_over(window: Sequence[RawDailyRecord], field: str, n: int) -> float:
    return _sum_over(window, field, n) / n


def _vpd_mean_over(window: Sequence[RawDailyRecord], n: int) -> float:
    return (
        sum(
            calculate_vpd_kpa(
                temperature_max_c=r.temperature_max_c,
                temperature_min_c=r.temperature_min_c,
                relative_humidity_mean_pct=r.relative_humidity_mean_pct,
            )
            for r in window[:n]
        )
        / n
    )


def build_rolling_feature_records(
    daily_series: Sequence[RawDailyRecord],
) -> list[tuple[RawDailyRecord, AIFeatureVectorV2]]:
    """Build causal (past/current-only) antecedent features for one
    location's chronological daily series.

    A record is included only if all `_MAX_ROLLING_WINDOW_DAYS` calendar
    days up to and including its own date are present in `daily_series`
    (looked up by exact date, not by list position, so an isolated missing
    day correctly invalidates every window that spans it rather than
    silently shifting in a non-adjacent day). This means the first ~29 days
    of each location's collected history are dropped — never fabricated —
    exactly like a real deployment would have no rolling history for a
    field's first weeks of records.
    """
    by_date = {record.date: record for record in daily_series}

    results: list[tuple[RawDailyRecord, AIFeatureVectorV2]] = []
    for record in daily_series:
        window_dates = [record.date - timedelta(days=k) for k in range(_MAX_ROLLING_WINDOW_DAYS)]
        if not all(d in by_date for d in window_dates):
            continue
        window = [by_date[d] for d in window_dates]  # index 0 = today, oldest last

        cumulative_water_deficit_30d = sum(
            max(r.et0_mm - r.precipitation_mm, 0.0) for r in window
        )

        same_day = build_feature_vector(
            day=record.date,
            latitude=record.latitude,
            longitude=record.longitude,
            et0_mm=record.et0_mm,
            precipitation_mm=record.precipitation_mm,
            temperature_max_c=record.temperature_max_c,
            temperature_min_c=record.temperature_min_c,
            temperature_mean_c=record.temperature_mean_c,
            relative_humidity_mean_pct=record.relative_humidity_mean_pct,
            wind_speed_ms=record.wind_speed_ms,
            shortwave_radiation_mj_m2=record.shortwave_radiation_mj_m2,
        )

        vector = AIFeatureVectorV2(
            **same_day.model_dump(exclude={"crop_type", "crop_stage", "days_after_planting",
                                            "soil_texture", "fao_estimated_depletion_fraction",
                                            "days_since_irrigation", "ndvi", "ndmi"}),
            precipitation_sum_3d=_sum_over(window, "precipitation_mm", 3),
            precipitation_sum_7d=_sum_over(window, "precipitation_mm", 7),
            precipitation_sum_14d=_sum_over(window, "precipitation_mm", 14),
            precipitation_sum_30d=_sum_over(window, "precipitation_mm", 30),
            et0_sum_3d=_sum_over(window, "et0_mm", 3),
            et0_sum_7d=_sum_over(window, "et0_mm", 7),
            et0_sum_14d=_sum_over(window, "et0_mm", 14),
            et0_sum_30d=_sum_over(window, "et0_mm", 30),
            vpd_mean_3d=_vpd_mean_over(window, 3),
            vpd_mean_7d=_vpd_mean_over(window, 7),
            temperature_mean_3d=_mean_over(window, "temperature_mean_c", 3),
            temperature_mean_7d=_mean_over(window, "temperature_mean_c", 7),
            shortwave_radiation_mean_7d=_mean_over(window, "shortwave_radiation_mj_m2", 7),
            precipitation_minus_et0_3d=(
                _sum_over(window, "precipitation_mm", 3) - _sum_over(window, "et0_mm", 3)
            ),
            precipitation_minus_et0_7d=(
                _sum_over(window, "precipitation_mm", 7) - _sum_over(window, "et0_mm", 7)
            ),
            precipitation_minus_et0_14d=(
                _sum_over(window, "precipitation_mm", 14) - _sum_over(window, "et0_mm", 14)
            ),
            cumulative_water_deficit_30d=cumulative_water_deficit_30d,
        )
        results.append((record, vector))
    return results


def compute_location_climatology(daily_series: Sequence[RawDailyRecord]) -> tuple[float, float]:
    """(min, max) of the root-zone soil-moisture proxy observed across a
    single location's own collected series — the reference range used to
    build that location's wetness-index target. Computed independently per
    location (never mixed across locations), so a test location's index is
    always relative to its own observed range, not a training location's."""
    values = [r.root_zone_soil_moisture_proxy_m3m3 for r in daily_series]
    if not values:
        raise ValueError("daily_series must not be empty")
    return min(values), max(values)


def wetness_index_from_value(value: float, *, location_min: float, location_max: float) -> float:
    """Map an absolute root-zone soil-moisture proxy value to a 0-1
    location-relative wetness index using that location's own observed
    [location_min, location_max] range (see `compute_location_climatology`).
    A degenerate zero-range location (e.g. too little history) maps
    everything to the midpoint 0.5 rather than dividing by zero."""
    if location_max <= location_min:
        return 0.5
    return max(0.0, min(1.0, (value - location_min) / (location_max - location_min)))
