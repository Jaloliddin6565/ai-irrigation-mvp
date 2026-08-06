import pytest

from app.domain.irrigation_normalization import (
    IrrigationDepthSource,
    duration_and_flow_rate_to_mm,
    normalize_irrigation_event,
    volume_and_area_to_mm,
)

QMAP = {"little": 8.0, "moderate": 18.0, "a_lot": 35.0}


def test_volume_and_area_to_mm_matches_10_m3_per_ha_rule() -> None:
    # 1 mm over 1 hectare = 10 m3
    assert volume_and_area_to_mm(10.0, 1.0) == 1.0
    assert volume_and_area_to_mm(100.0, 2.0) == 5.0


def test_volume_and_area_rejects_non_positive_area() -> None:
    with pytest.raises(ValueError, match="field_area_hectares"):
        volume_and_area_to_mm(10.0, 0.0)


def test_duration_and_flow_rate_to_mm() -> None:
    # 60 minutes at 10 m3/hour = 10 m3 -> over 1 ha = 1mm
    assert duration_and_flow_rate_to_mm(60, 10.0, 1.0) == 1.0
    # 30 minutes at 20 m3/hour = 10 m3 -> over 1 ha = 1mm
    assert duration_and_flow_rate_to_mm(30, 20.0, 1.0) == pytest.approx(1.0)


def test_direct_amount_mm_is_preferred_and_quantitative() -> None:
    result = normalize_irrigation_event(
        amount_mm=20.0,
        total_volume_m3=None,
        duration_minutes=None,
        flow_rate_m3_hour=None,
        qualitative_amount=None,
        field_area_hectares=1.0,
        qualitative_irrigation_mm=QMAP,
    )
    assert result.depth_mm == 20.0
    assert result.source == IrrigationDepthSource.DIRECT_AMOUNT_MM
    assert result.is_quantitative is True


def test_volume_and_area_used_when_no_direct_amount() -> None:
    result = normalize_irrigation_event(
        amount_mm=None,
        total_volume_m3=15.0,
        duration_minutes=None,
        flow_rate_m3_hour=None,
        qualitative_amount=None,
        field_area_hectares=1.5,
        qualitative_irrigation_mm=QMAP,
    )
    assert result.source == IrrigationDepthSource.VOLUME_AND_AREA
    assert result.depth_mm == pytest.approx(1.0)


def test_duration_and_flow_used_as_last_quantitative_resort() -> None:
    result = normalize_irrigation_event(
        amount_mm=None,
        total_volume_m3=None,
        duration_minutes=60,
        flow_rate_m3_hour=5.0,
        qualitative_amount=None,
        field_area_hectares=1.0,
        qualitative_irrigation_mm=QMAP,
    )
    assert result.source == IrrigationDepthSource.DURATION_AND_FLOW_RATE
    assert result.is_quantitative is True


def test_qualitative_only_is_conservative_estimate_and_not_quantitative() -> None:
    result = normalize_irrigation_event(
        amount_mm=None,
        total_volume_m3=None,
        duration_minutes=None,
        flow_rate_m3_hour=None,
        qualitative_amount="moderate",
        field_area_hectares=1.0,
        qualitative_irrigation_mm=QMAP,
    )
    assert result.depth_mm == 18.0
    assert result.source == IrrigationDepthSource.QUALITATIVE_ESTIMATE
    assert result.is_quantitative is False
    assert result.warnings


def test_no_data_at_all_returns_unknown() -> None:
    result = normalize_irrigation_event(
        amount_mm=None,
        total_volume_m3=None,
        duration_minutes=None,
        flow_rate_m3_hour=None,
        qualitative_amount=None,
        field_area_hectares=1.0,
        qualitative_irrigation_mm=QMAP,
    )
    assert result.depth_mm is None
    assert result.source == IrrigationDepthSource.UNKNOWN
    assert result.warnings


def test_inconsistent_quantitative_inputs_warn_but_prefer_direct_amount() -> None:
    result = normalize_irrigation_event(
        amount_mm=20.0,
        total_volume_m3=10.0,  # -> 1mm over 1ha, wildly different from 20mm
        duration_minutes=None,
        flow_rate_m3_hour=None,
        qualitative_amount=None,
        field_area_hectares=1.0,
        qualitative_irrigation_mm=QMAP,
    )
    assert result.depth_mm == 20.0
    assert result.warnings
    assert "inconsistent" in result.warnings[0].lower()


def test_consistent_quantitative_inputs_do_not_warn() -> None:
    result = normalize_irrigation_event(
        amount_mm=10.0,
        total_volume_m3=1000.0,  # -> 10mm over 10ha (1000 / 10 / 10)
        duration_minutes=None,
        flow_rate_m3_hour=None,
        qualitative_amount=None,
        field_area_hectares=10.0,
        qualitative_irrigation_mm=QMAP,
    )
    assert result.depth_mm == 10.0
    assert result.warnings == []
