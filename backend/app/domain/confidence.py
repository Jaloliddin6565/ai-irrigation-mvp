"""Deterministic, explainable confidence scoring.

Produces a 0-1 score from a weighted sum of independently-scored 0-1
factors, then applies hard caps that can only lower the score (never raise
it) when a specific condition holds (e.g. irrigation amount unknown). This
is a documented heuristic scoring formula — see docs/methodology.md — never
a trained model's probability estimate, and never described as one.
"""

from dataclasses import dataclass, field, replace

from app.domain.initialization import InitializationMethod, InitializationResult
from app.domain.satellite_adjustment import SatelliteAdjustmentResult, SatelliteDataQuality
from app.domain.water_balance import clamp

_HIGH_SCORE_THRESHOLD_FOR_NARRATIVE = 0.7
_LOW_SCORE_THRESHOLD_FOR_NARRATIVE = 0.4
_WEATHER_MISSING_CAP_TRIGGER_FRACTION = 0.9
_INITIALIZATION_WEAK_UNCERTAINTY_TRIGGER = 0.7

_QUANTITATIVE_INIT_METHODS = (
    InitializationMethod.RECENT_IRRIGATION_KNOWN_AMOUNT,
    InitializationMethod.RECENT_IRRIGATION_DURATION_FLOW,
)
_WEAK_INIT_METHODS = (
    InitializationMethod.CONSERVATIVE_DEFAULT,
    InitializationMethod.INSUFFICIENT_DATA,
)
_POOR_SATELLITE_QUALITY = (
    SatelliteDataQuality.STALE,
    SatelliteDataQuality.LOW_QUALITY,
    SatelliteDataQuality.INSUFFICIENT,
)


@dataclass(frozen=True)
class ConfidenceFactorScores:
    field_data_completeness: float
    crop_profile_quality: float
    soil_profile_quality: float
    planting_date_availability: float
    last_irrigation_availability: float
    irrigation_amount_quality: float
    initialization_certainty: float
    weather_data_availability: float
    satellite_freshness: float
    valid_pixel_ratio: float
    observation_count: float

    def as_dict(self) -> dict[str, float]:
        return {
            "field_data_completeness": self.field_data_completeness,
            "crop_profile_quality": self.crop_profile_quality,
            "soil_profile_quality": self.soil_profile_quality,
            "planting_date_availability": self.planting_date_availability,
            "last_irrigation_availability": self.last_irrigation_availability,
            "irrigation_amount_quality": self.irrigation_amount_quality,
            "initialization_certainty": self.initialization_certainty,
            "weather_data_availability": self.weather_data_availability,
            "satellite_freshness": self.satellite_freshness,
            "valid_pixel_ratio": self.valid_pixel_ratio,
            "observation_count": self.observation_count,
        }


@dataclass(frozen=True)
class ConfidenceResult:
    score: float
    raw_weighted_score: float
    category: str
    factor_scores: ConfidenceFactorScores
    weights: dict[str, float]
    triggered_caps: list[str] = field(default_factory=list)
    # Plain factor-name keys (same keys as ConfidenceFactorScores.as_dict()),
    # not narrative sentences — the frontend already needs a stable-key ->
    # Uzbek-label mapping for factor_scores/triggered_caps, so this stays
    # consistent with that rather than duplicating English prose that would
    # need its own translation path.
    strong_factors: list[str] = field(default_factory=list)
    weak_factors: list[str] = field(default_factory=list)


def _score_field_data_completeness(
    *,
    crop_variety_present: bool,
    expected_harvest_date_present: bool,
    irrigation_method_known: bool,
    notes_present: bool,
) -> float:
    checks = [
        crop_variety_present,
        expected_harvest_date_present,
        irrigation_method_known,
        notes_present,
    ]
    return sum(1 for c in checks if c) / len(checks)


def _score_satellite_freshness(
    latest_observation_age_days: int | None, max_observation_age_days_for_trend: int
) -> float:
    if latest_observation_age_days is None:
        return 0.0
    return clamp(
        1.0 - (latest_observation_age_days / (2.0 * max_observation_age_days_for_trend)), 0.0, 1.0
    )


def compute_confidence(
    *,
    crop_variety_present: bool,
    expected_harvest_date_present: bool,
    irrigation_method_known: bool,
    notes_present: bool,
    crop_stage_is_edge_case: bool,
    crop_profile_uncertainty_factor: float,
    soil_profile_uncertainty_factor: float,
    soil_requires_field_survey: bool,
    initialization: InitializationResult,
    weather_available_fraction: float,
    satellite: SatelliteAdjustmentResult,
    max_observation_age_days_for_trend: int,
    min_valid_observations_for_trend: int,
    weights: dict[str, float],
    high_threshold: float,
    medium_threshold: float,
    cap_irrigation_amount_unknown: float,
    cap_soil_unknown: float,
    cap_initialization_weak: float,
    cap_satellite_stale_or_low_quality: float,
    cap_weather_missing: float,
) -> ConfidenceResult:
    is_quantitative_init = initialization.method in _QUANTITATIVE_INIT_METHODS

    factor_scores = ConfidenceFactorScores(
        field_data_completeness=_score_field_data_completeness(
            crop_variety_present=crop_variety_present,
            expected_harvest_date_present=expected_harvest_date_present,
            irrigation_method_known=irrigation_method_known,
            notes_present=notes_present,
        ),
        crop_profile_quality=clamp(1.0 - crop_profile_uncertainty_factor, 0.0, 1.0),
        soil_profile_quality=clamp(1.0 - soil_profile_uncertainty_factor, 0.0, 1.0),
        planting_date_availability=0.5 if crop_stage_is_edge_case else 1.0,
        last_irrigation_availability=(
            1.0
            if is_quantitative_init
            else (0.3 if initialization.method != InitializationMethod.INSUFFICIENT_DATA else 0.0)
        ),
        irrigation_amount_quality=(
            1.0
            if initialization.method == InitializationMethod.RECENT_IRRIGATION_KNOWN_AMOUNT
            else (
                0.6
                if initialization.method == InitializationMethod.RECENT_IRRIGATION_DURATION_FLOW
                else 0.2
            )
        ),
        initialization_certainty=clamp(1.0 - initialization.uncertainty, 0.0, 1.0),
        weather_data_availability=clamp(weather_available_fraction, 0.0, 1.0),
        satellite_freshness=_score_satellite_freshness(
            satellite.latest_observation_age_days, max_observation_age_days_for_trend
        ),
        valid_pixel_ratio=satellite.latest_valid_pixel_ratio or 0.0,
        observation_count=clamp(
            satellite.valid_observations_used / max(min_valid_observations_for_trend, 1), 0.0, 1.0
        ),
    )

    scores = factor_scores.as_dict()
    weighted_score = sum(weights.get(name, 0.0) * value for name, value in scores.items())

    triggered_caps: list[str] = []
    final_score = weighted_score

    if not is_quantitative_init:
        final_score = min(final_score, cap_irrigation_amount_unknown)
        triggered_caps.append("max_score_if_irrigation_amount_unknown")
    if soil_requires_field_survey:
        final_score = min(final_score, cap_soil_unknown)
        triggered_caps.append("max_score_if_soil_unknown")
    if (
        initialization.method in _WEAK_INIT_METHODS
        or initialization.uncertainty >= _INITIALIZATION_WEAK_UNCERTAINTY_TRIGGER
    ):
        final_score = min(final_score, cap_initialization_weak)
        triggered_caps.append("max_score_if_initialization_weak")
    if satellite.data_quality in _POOR_SATELLITE_QUALITY:
        final_score = min(final_score, cap_satellite_stale_or_low_quality)
        triggered_caps.append("max_score_if_satellite_stale_or_low_quality")
    if weather_available_fraction < _WEATHER_MISSING_CAP_TRIGGER_FRACTION:
        final_score = min(final_score, cap_weather_missing)
        triggered_caps.append("max_score_if_weather_missing")

    final_score = clamp(final_score, 0.0, 1.0)

    if final_score >= high_threshold:
        category = "high"
    elif final_score >= medium_threshold:
        category = "medium"
    else:
        category = "low"

    strong_factors = [
        name for name, value in scores.items() if value >= _HIGH_SCORE_THRESHOLD_FOR_NARRATIVE
    ]
    weak_factors = [
        name for name, value in scores.items() if value < _LOW_SCORE_THRESHOLD_FOR_NARRATIVE
    ]

    return ConfidenceResult(
        score=final_score,
        raw_weighted_score=clamp(weighted_score, 0.0, 1.0),
        category=category,
        factor_scores=factor_scores,
        weights=dict(weights),
        triggered_caps=triggered_caps,
        strong_factors=strong_factors,
        weak_factors=weak_factors,
    )


# Keeps an AI "agree" bonus from landing exactly ON the high threshold
# (which would count as "high" — see the >= comparison below).
_AI_SAME_TIER_SAFETY_MARGIN = 0.001


def apply_ai_agreement_adjustment(
    confidence_result: ConfidenceResult,
    *,
    agreement_status: str,
    agree_bonus: float,
    disagree_penalty: float,
    high_threshold: float,
    medium_threshold: float,
) -> ConfidenceResult:
    """Conservative, capped adjustment layered on top of an already-computed
    FAO-only ConfidenceResult (see compute_confidence above) — a Phase 2
    additive evidence layer, never a redesign of confidence itself. Only
    score/category change; factor_scores, weights, triggered_caps, and
    strong/weak_factors are carried over unchanged because they describe
    the FAO-only evidence, not this AI evidence layer.

    Bonuses/penalties come from backend/config/ai_evidence.yaml
    confidence_adjustment and apply only for "agree"/"disagree"
    (app/domain/ai_agreement.py AgreementStatus) — "partial" and
    "unavailable" leave the result untouched.

    Safety rule (CLAUDE.md / PHASE 2 section 6): an "agree" bonus alone can
    never promote a non-high category all the way to "high" — the generic
    public-data AI model must never turn low/medium confidence into falsely
    high confidence by itself. A "disagree" penalty has no such floor: it
    is always allowed to lower the score/category further, since a
    corroborating AI signal is inherently weaker evidence than a
    contradicting one is a warning sign.

    This function is never used as an input to app/domain/recommendation.py
    — the recommendation range is always computed from the pre-adjustment
    ConfidenceResult, so AI evidence can never indirectly widen/narrow
    recommended_min_mm/max_mm through the confidence-driven uncertainty
    padding. See app/services/analysis.py for the call ordering that
    enforces this.
    """
    if agreement_status == "agree":
        delta = agree_bonus
    elif agreement_status == "disagree":
        delta = -disagree_penalty
    else:  # "partial" or "unavailable": no adjustment
        return confidence_result

    adjusted_score = clamp(confidence_result.score + delta, 0.0, 1.0)

    if delta > 0 and confidence_result.category != "high" and adjusted_score >= high_threshold:
        adjusted_score = high_threshold - _AI_SAME_TIER_SAFETY_MARGIN

    if adjusted_score >= high_threshold:
        category = "high"
    elif adjusted_score >= medium_threshold:
        category = "medium"
    else:
        category = "low"

    return replace(confidence_result, score=adjusted_score, category=category)
