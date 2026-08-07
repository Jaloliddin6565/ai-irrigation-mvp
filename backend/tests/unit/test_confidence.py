import pytest

from app.domain.confidence import compute_confidence
from app.domain.config_loader import get_agronomic_config
from app.domain.initialization import InitializationMethod, InitializationResult
from app.domain.satellite_adjustment import SatelliteAdjustmentResult, SatelliteDataQuality

CFG = get_agronomic_config().confidence_weights
COTTON = get_agronomic_config().crops.crops["cotton"]
LOAM = get_agronomic_config().soils.soils["loam"]

GOOD_SATELLITE = SatelliteAdjustmentResult(
    applied=True,
    adjustment_mm=1.0,
    valid_observations_used=3,
    latest_observation_date=None,
    latest_observation_age_days=2,
    latest_valid_pixel_ratio=0.95,
    data_quality=SatelliteDataQuality.OK,
)
BAD_SATELLITE = SatelliteAdjustmentResult(
    applied=False,
    adjustment_mm=0.0,
    valid_observations_used=0,
    latest_observation_date=None,
    latest_observation_age_days=None,
    latest_valid_pixel_ratio=None,
    data_quality=SatelliteDataQuality.INSUFFICIENT,
)
GOOD_INIT = InitializationResult(
    method=InitializationMethod.RECENT_IRRIGATION_KNOWN_AMOUNT,
    start_date=None,
    starting_depletion_mm=10.0,
    uncertainty=0.2,
)
BAD_INIT = InitializationResult(
    method=InitializationMethod.INSUFFICIENT_DATA,
    start_date=None,
    starting_depletion_mm=None,
    uncertainty=1.0,
)


def _base_kwargs(**overrides):
    kwargs = dict(
        crop_variety_present=True,
        expected_harvest_date_present=True,
        irrigation_method_known=True,
        notes_present=True,
        crop_stage_is_edge_case=False,
        crop_profile_uncertainty_factor=COTTON.uncertainty_factor,
        soil_profile_uncertainty_factor=LOAM.uncertainty_factor,
        soil_requires_field_survey=False,
        initialization=GOOD_INIT,
        weather_available_fraction=1.0,
        satellite=GOOD_SATELLITE,
        max_observation_age_days_for_trend=20,
        min_valid_observations_for_trend=2,
        weights=CFG.weights,
        high_threshold=CFG.thresholds.high,
        medium_threshold=CFG.thresholds.medium,
        cap_irrigation_amount_unknown=CFG.caps.max_score_if_irrigation_amount_unknown,
        cap_soil_unknown=CFG.caps.max_score_if_soil_unknown,
        cap_initialization_weak=CFG.caps.max_score_if_initialization_weak,
        cap_satellite_stale_or_low_quality=CFG.caps.max_score_if_satellite_stale_or_low_quality,
        cap_weather_missing=CFG.caps.max_score_if_weather_missing,
    )
    kwargs.update(overrides)
    return kwargs


def test_score_is_bounded_between_zero_and_one() -> None:
    result = compute_confidence(**_base_kwargs())
    assert 0.0 <= result.score <= 1.0


def test_best_case_scenario_can_reach_high() -> None:
    result = compute_confidence(**_base_kwargs())
    assert result.category == "high"
    assert not result.triggered_caps


def test_worst_case_scenario_is_low_and_triggers_every_cap() -> None:
    result = compute_confidence(
        **_base_kwargs(
            crop_variety_present=False,
            expected_harvest_date_present=False,
            irrigation_method_known=False,
            notes_present=False,
            crop_stage_is_edge_case=True,
            soil_profile_uncertainty_factor=1.0,
            soil_requires_field_survey=True,
            initialization=BAD_INIT,
            weather_available_fraction=0.0,
            satellite=BAD_SATELLITE,
        )
    )
    assert result.category == "low"
    assert len(result.triggered_caps) == 5


def test_cap_prevents_high_confidence_when_irrigation_amount_unknown() -> None:
    weak_init = InitializationResult(
        method=InitializationMethod.PLANTING_DATE_ASSUMPTION,
        start_date=None,
        starting_depletion_mm=0.0,
        uncertainty=0.5,
    )
    result = compute_confidence(**_base_kwargs(initialization=weak_init))
    assert result.category != "high"
    assert "max_score_if_irrigation_amount_unknown" in result.triggered_caps


def test_cap_prevents_high_confidence_when_soil_unknown() -> None:
    result = compute_confidence(
        **_base_kwargs(soil_profile_uncertainty_factor=1.0, soil_requires_field_survey=True)
    )
    assert result.category != "high"
    assert "max_score_if_soil_unknown" in result.triggered_caps


def test_cap_prevents_high_confidence_when_initialization_weak() -> None:
    weak_init = InitializationResult(
        method=InitializationMethod.CONSERVATIVE_DEFAULT,
        start_date=None,
        starting_depletion_mm=5.0,
        uncertainty=0.75,
    )
    result = compute_confidence(**_base_kwargs(initialization=weak_init))
    assert "max_score_if_initialization_weak" in result.triggered_caps


def test_cap_prevents_high_confidence_when_satellite_stale() -> None:
    stale_satellite = SatelliteAdjustmentResult(
        applied=False,
        adjustment_mm=0.0,
        valid_observations_used=1,
        latest_observation_date=None,
        latest_observation_age_days=45,
        latest_valid_pixel_ratio=0.9,
        data_quality=SatelliteDataQuality.STALE,
    )
    result = compute_confidence(**_base_kwargs(satellite=stale_satellite))
    assert "max_score_if_satellite_stale_or_low_quality" in result.triggered_caps


def test_cap_prevents_high_confidence_when_weather_missing() -> None:
    result = compute_confidence(**_base_kwargs(weather_available_fraction=0.5))
    assert "max_score_if_weather_missing" in result.triggered_caps


def test_category_thresholds_match_config() -> None:
    result = compute_confidence(**_base_kwargs())
    if result.score >= CFG.thresholds.high:
        assert result.category == "high"
    elif result.score >= CFG.thresholds.medium:
        assert result.category == "medium"
    else:
        assert result.category == "low"


def test_deterministic_repeated_calls() -> None:
    first = compute_confidence(**_base_kwargs())
    second = compute_confidence(**_base_kwargs())
    assert first == second


@pytest.mark.parametrize("fraction", [0.0, 0.5, 1.0])
def test_weather_availability_feeds_the_factor_score_directly(fraction: float) -> None:
    result = compute_confidence(**_base_kwargs(weather_available_fraction=fraction))
    assert result.factor_scores.weather_data_availability == pytest.approx(fraction)


def test_strong_and_weak_factors_are_stable_keys_not_narrative_sentences() -> None:
    """strong_factors/weak_factors must be plain factor-name keys (same
    keys as factor_scores/triggered_caps), not English prose — the frontend
    translates by key, it does not parse sentences."""
    best = compute_confidence(**_base_kwargs())
    assert best.strong_factors
    for name in best.strong_factors:
        assert name in best.factor_scores.as_dict()
        assert " " not in name

    worst = compute_confidence(
        **_base_kwargs(
            crop_variety_present=False,
            expected_harvest_date_present=False,
            irrigation_method_known=False,
            notes_present=False,
            crop_stage_is_edge_case=True,
            soil_profile_uncertainty_factor=1.0,
            soil_requires_field_survey=True,
            initialization=BAD_INIT,
            weather_available_fraction=0.0,
            satellite=BAD_SATELLITE,
        )
    )
    assert worst.weak_factors
    for name in worst.weak_factors:
        assert name in worst.factor_scores.as_dict()
