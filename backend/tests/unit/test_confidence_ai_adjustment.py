import pytest

from app.domain.confidence import (
    ConfidenceFactorScores,
    ConfidenceResult,
    apply_ai_agreement_adjustment,
)

HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.40
AGREE_BONUS = 0.05
DISAGREE_PENALTY = 0.08

_FACTOR_SCORES = ConfidenceFactorScores(
    field_data_completeness=0.5,
    crop_profile_quality=0.5,
    soil_profile_quality=0.5,
    planting_date_availability=0.5,
    last_irrigation_availability=0.5,
    irrigation_amount_quality=0.5,
    initialization_certainty=0.5,
    weather_data_availability=0.5,
    satellite_freshness=0.5,
    valid_pixel_ratio=0.5,
    observation_count=0.5,
)


def _confidence_result(score: float, category: str) -> ConfidenceResult:
    return ConfidenceResult(
        score=score,
        raw_weighted_score=score,
        category=category,
        factor_scores=_FACTOR_SCORES,
        weights={"field_data_completeness": 1.0},
        triggered_caps=["some_cap"],
        strong_factors=["field_data_completeness"],
        weak_factors=[],
    )


def _adjust(base: ConfidenceResult, agreement_status: str) -> ConfidenceResult:
    return apply_ai_agreement_adjustment(
        base,
        agreement_status=agreement_status,
        agree_bonus=AGREE_BONUS,
        disagree_penalty=DISAGREE_PENALTY,
        high_threshold=HIGH_THRESHOLD,
        medium_threshold=MEDIUM_THRESHOLD,
    )


def test_agree_gives_small_capped_bonus() -> None:
    base = _confidence_result(0.50, "medium")
    adjusted = _adjust(base, "agree")
    assert adjusted.score == pytest.approx(0.55)
    assert adjusted.category == "medium"


def test_agree_bonus_cannot_promote_a_non_high_category_to_high() -> None:
    base = _confidence_result(0.68, "medium")
    adjusted = _adjust(base, "agree")
    assert adjusted.score < HIGH_THRESHOLD
    assert adjusted.category == "medium"


def test_agree_bonus_at_already_high_stays_high_and_clamps_at_one() -> None:
    base = _confidence_result(0.98, "high")
    adjusted = _adjust(base, "agree")
    assert adjusted.score == pytest.approx(1.0)
    assert adjusted.category == "high"


def test_disagree_penalty_can_cross_a_category_boundary_downward() -> None:
    base = _confidence_result(0.45, "medium")
    adjusted = _adjust(base, "disagree")
    assert adjusted.score == pytest.approx(0.37)
    assert adjusted.category == "low"


def test_disagree_penalty_clamps_at_zero() -> None:
    base = _confidence_result(0.02, "low")
    adjusted = _adjust(base, "disagree")
    assert adjusted.score == 0.0
    assert adjusted.category == "low"


@pytest.mark.parametrize("agreement_status", ["partial", "unavailable"])
def test_partial_and_unavailable_apply_no_adjustment(agreement_status: str) -> None:
    base = _confidence_result(0.50, "medium")
    adjusted = _adjust(base, agreement_status)
    assert adjusted is base


def test_adjustment_preserves_factor_scores_weights_and_caps() -> None:
    base = _confidence_result(0.50, "medium")
    adjusted = _adjust(base, "agree")
    assert adjusted.factor_scores == base.factor_scores
    assert adjusted.weights == base.weights
    assert adjusted.triggered_caps == base.triggered_caps
    assert adjusted.strong_factors == base.strong_factors
    assert adjusted.weak_factors == base.weak_factors


def test_adjusted_score_always_stays_in_zero_one_range() -> None:
    for score, category, status in [
        (0.99, "high", "agree"),
        (0.01, "low", "disagree"),
        (0.5, "medium", "agree"),
        (0.5, "medium", "disagree"),
    ]:
        adjusted = _adjust(_confidence_result(score, category), status)
        assert 0.0 <= adjusted.score <= 1.0
