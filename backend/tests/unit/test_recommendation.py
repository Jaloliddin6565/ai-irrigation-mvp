from datetime import date

import pytest

from app.domain.recommendation import RecommendationStatus, determine_recommendation

COMMON = dict(
    analysis_date=date(2026, 6, 1),
    taw_mm=100.0,
    raw_mm=50.0,
    irrigation_efficiency=0.9,
    practical_min_mm=15.0,
    practical_max_mm=90.0,
    field_area_hectares=2.0,
    forecast_precipitation_mm=0.0,
    forecast_window_hours=60,
    confidence_category="high",
    monitor_depletion_raw_ratio=0.5,
    irrigate_soon_depletion_raw_ratio=0.8,
    irrigate_now_depletion_raw_ratio=1.0,
    forecast_rain_delay_threshold_mm=10.0,
    min_replacement_fraction=0.8,
    max_replacement_fraction=1.15,
    uncertainty_range_padding_fraction=0.15,
)


@pytest.mark.parametrize(
    "depletion_mm,expected_status",
    [
        (10.0, RecommendationStatus.NO_IRRIGATION_NEEDED),
        (24.9, RecommendationStatus.NO_IRRIGATION_NEEDED),
        (25.0, RecommendationStatus.MONITOR),
        (39.9, RecommendationStatus.MONITOR),
        (40.0, RecommendationStatus.IRRIGATE_SOON),
        (49.9, RecommendationStatus.IRRIGATE_SOON),
        (50.0, RecommendationStatus.IRRIGATE_NOW),
        (70.0, RecommendationStatus.IRRIGATE_NOW),
    ],
)
def test_status_thresholds(depletion_mm: float, expected_status: RecommendationStatus) -> None:
    result = determine_recommendation(depletion_mm=depletion_mm, **COMMON)
    assert result.status == expected_status


def test_no_irrigation_needed_has_zero_range_and_no_window() -> None:
    result = determine_recommendation(depletion_mm=10.0, **COMMON)
    assert result.recommended_min_mm == 0.0
    assert result.recommended_max_mm == 0.0
    assert result.window is None


def test_irrigate_now_has_a_positive_range_and_immediate_window() -> None:
    result = determine_recommendation(depletion_mm=55.0, **COMMON)
    assert result.recommended_min_mm > 0
    assert result.recommended_max_mm > result.recommended_min_mm
    assert result.window is not None
    assert result.window.start_date == COMMON["analysis_date"]


def test_forecast_rain_delays_an_otherwise_irrigate_now_result() -> None:
    result = determine_recommendation(
        depletion_mm=55.0, **{**COMMON, "forecast_precipitation_mm": 15.0}
    )
    assert result.status == RecommendationStatus.DELAY_DUE_TO_FORECAST_RAIN


def test_forecast_rain_below_threshold_does_not_delay() -> None:
    result = determine_recommendation(
        depletion_mm=55.0, **{**COMMON, "forecast_precipitation_mm": 5.0}
    )
    assert result.status == RecommendationStatus.IRRIGATE_NOW


def test_forecast_rain_does_not_delay_no_irrigation_needed() -> None:
    result = determine_recommendation(
        depletion_mm=10.0, **{**COMMON, "forecast_precipitation_mm": 50.0}
    )
    assert result.status == RecommendationStatus.NO_IRRIGATION_NEEDED


def test_insufficient_data_when_depletion_is_none() -> None:
    result = determine_recommendation(depletion_mm=None, **COMMON)
    assert result.status == RecommendationStatus.INSUFFICIENT_DATA
    assert result.recommended_min_mm == 0.0
    assert result.window is None


def test_m3_per_ha_and_total_volume_conversion() -> None:
    result = determine_recommendation(depletion_mm=55.0, **COMMON)
    assert result.recommended_min_m3_per_ha == pytest.approx(result.recommended_min_mm * 10)
    assert result.recommended_max_m3_per_ha == pytest.approx(result.recommended_max_mm * 10)
    assert result.total_min_volume_m3 == pytest.approx(
        result.recommended_min_m3_per_ha * COMMON["field_area_hectares"]
    )
    assert result.total_max_volume_m3 == pytest.approx(
        result.recommended_max_m3_per_ha * COMMON["field_area_hectares"]
    )


def test_range_clamped_to_practical_application_limits() -> None:
    result = determine_recommendation(depletion_mm=45.0, **{**COMMON, "practical_min_mm": 50.0})
    assert result.recommended_min_mm >= 50.0
    assert result.warnings


def test_low_confidence_widens_the_range_versus_high_confidence() -> None:
    high = determine_recommendation(depletion_mm=55.0, **COMMON)
    low = determine_recommendation(depletion_mm=55.0, **{**COMMON, "confidence_category": "low"})
    assert (low.recommended_max_mm - low.recommended_min_mm) >= (
        high.recommended_max_mm - high.recommended_min_mm
    )


def test_recommended_range_is_never_a_single_point_value() -> None:
    result = determine_recommendation(depletion_mm=55.0, **COMMON)
    assert result.recommended_max_mm > result.recommended_min_mm


def test_non_positive_taw_or_raw_raises() -> None:
    with pytest.raises(ValueError):
        determine_recommendation(depletion_mm=10.0, **{**COMMON, "taw_mm": 0.0})
    with pytest.raises(ValueError):
        determine_recommendation(depletion_mm=10.0, **{**COMMON, "raw_mm": 0.0})


def test_deterministic_repeated_calls() -> None:
    first = determine_recommendation(depletion_mm=55.0, **COMMON)
    second = determine_recommendation(depletion_mm=55.0, **COMMON)
    assert first == second
