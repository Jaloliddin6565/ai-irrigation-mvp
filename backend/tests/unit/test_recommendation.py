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
    uncertainty_range_padding_fraction_medium=0.10,
    uncertainty_range_padding_fraction_low=0.15,
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
    assert result.depletion_mm == 10.0
    assert result.base_gross_mm is None


def test_depletion_mm_and_base_gross_mm_are_exposed_for_the_point_estimate() -> None:
    result = determine_recommendation(depletion_mm=55.0, **COMMON)
    assert result.depletion_mm == 55.0
    assert result.base_gross_mm == pytest.approx(55.0 / COMMON["irrigation_efficiency"])


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
    assert any(m.code == "recommendation_clamped_to_practical_limits" for m in result.warning_codes)


def test_reason_codes_carry_the_depletion_summary_with_structured_params() -> None:
    result = determine_recommendation(depletion_mm=55.0, **COMMON)
    depletion_message = next(m for m in result.reason_codes if m.code == "depletion_summary")
    assert depletion_message.params["depletion_mm"] == pytest.approx(55.0)
    assert depletion_message.params["raw_mm"] == pytest.approx(50.0)
    assert depletion_message.params["taw_mm"] == pytest.approx(100.0)


def test_confidence_range_widened_code_only_appears_when_not_high() -> None:
    high = determine_recommendation(depletion_mm=55.0, **COMMON)
    low = determine_recommendation(depletion_mm=55.0, **{**COMMON, "confidence_category": "low"})
    assert not any(m.code == "confidence_range_widened" for m in high.reason_codes)
    widened = next(m for m in low.reason_codes if m.code == "confidence_range_widened")
    assert widened.params["confidence_category"] == "low"


def test_forecast_rain_delay_reason_code_carries_params() -> None:
    result = determine_recommendation(
        depletion_mm=55.0, **{**COMMON, "forecast_precipitation_mm": 15.0}
    )
    delay_message = next(m for m in result.reason_codes if m.code == "forecast_rain_delay")
    assert delay_message.params["forecast_precipitation_mm"] == pytest.approx(15.0)
    assert delay_message.params["threshold_mm"] == pytest.approx(10.0)


def test_insufficient_data_reason_code() -> None:
    result = determine_recommendation(depletion_mm=None, **COMMON)
    assert len(result.reason_codes) == 1
    assert result.reason_codes[0].code == "insufficient_data_recommendation"


def test_low_confidence_widens_the_range_versus_high_confidence() -> None:
    high = determine_recommendation(depletion_mm=55.0, **COMMON)
    low = determine_recommendation(depletion_mm=55.0, **{**COMMON, "confidence_category": "low"})
    assert (low.recommended_max_mm - low.recommended_min_mm) >= (
        high.recommended_max_mm - high.recommended_min_mm
    )


def test_high_medium_low_confidence_ranges_use_distinct_padding() -> None:
    """Regression for the pilot report that medium and low confidence
    produced an identical, mechanically-doubled range. High gets zero
    padding; medium and low now use two separate, distinct constants
    (medium narrower than low) instead of one shared value."""
    depletion_mm = 55.0
    base_gross_mm = depletion_mm / COMMON["irrigation_efficiency"]
    high = determine_recommendation(depletion_mm=depletion_mm, **COMMON)
    medium = determine_recommendation(
        depletion_mm=depletion_mm, **{**COMMON, "confidence_category": "medium"}
    )
    low = determine_recommendation(
        depletion_mm=depletion_mm, **{**COMMON, "confidence_category": "low"}
    )

    # High: zero padding — exactly the replacement-fraction range, no more.
    assert high.recommended_min_mm == pytest.approx(
        base_gross_mm * COMMON["min_replacement_fraction"]
    )
    assert high.recommended_max_mm == pytest.approx(
        base_gross_mm * COMMON["max_replacement_fraction"]
    )

    medium_padding = base_gross_mm * COMMON["uncertainty_range_padding_fraction_medium"]
    assert medium.recommended_min_mm == pytest.approx(
        base_gross_mm * COMMON["min_replacement_fraction"] - medium_padding
    )
    assert medium.recommended_max_mm == pytest.approx(
        base_gross_mm * COMMON["max_replacement_fraction"] + medium_padding
    )

    low_padding = base_gross_mm * COMMON["uncertainty_range_padding_fraction_low"]
    assert low.recommended_min_mm == pytest.approx(
        base_gross_mm * COMMON["min_replacement_fraction"] - low_padding
    )
    assert low.recommended_max_mm == pytest.approx(
        base_gross_mm * COMMON["max_replacement_fraction"] + low_padding
    )

    high_width = high.recommended_max_mm - high.recommended_min_mm
    medium_width = medium.recommended_max_mm - medium.recommended_min_mm
    low_width = low.recommended_max_mm - low.recommended_min_mm
    assert high_width < medium_width < low_width


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
