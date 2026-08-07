"""Deterministic irrigation recommendation.

Turns the (satellite-qualified) estimated root-zone depletion into a
primary status and a recommended application RANGE — never a single
falsely-precise value. See docs/methodology.md. This is a deterministic
calculation, not a trained AI model, and never claims a guaranteed outcome.

Unit conversion: 1 mm of water depth over 1 hectare = 10 m3.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

from app.domain.messages import Message
from app.domain.water_balance import clamp

MM_PER_HA_TO_M3 = 10.0


class RecommendationStatus(StrEnum):
    NO_IRRIGATION_NEEDED = "no_irrigation_needed"
    MONITOR = "monitor"
    IRRIGATE_SOON = "irrigate_soon"
    IRRIGATE_NOW = "irrigate_now"
    DELAY_DUE_TO_FORECAST_RAIN = "delay_due_to_forecast_rain"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class RecommendationWindow:
    start_date: date
    end_date: date


@dataclass(frozen=True)
class RecommendationResult:
    status: RecommendationStatus
    recommended_min_mm: float
    recommended_max_mm: float
    recommended_min_m3_per_ha: float
    recommended_max_m3_per_ha: float
    total_min_volume_m3: float
    total_max_volume_m3: float
    window: RecommendationWindow | None
    # Point-estimate intermediates behind the range, exposed so the UI can
    # lead with a single headline number and present min/max as an
    # explained band around it, rather than only the range (see
    # docs/methodology.md and CLAUDE.md rule 3 — still never presented as a
    # single precise value on its own, always alongside the range).
    depletion_mm: float | None = None
    base_gross_mm: float | None = None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Structured counterparts to reasons/warnings above, covering only this
    # function's own internally-generated messages (not extra_reasons/
    # extra_warnings passed in from satellite/crop-stage, which stay
    # English-only for now — see docs/methodology.md). Additive: reasons/
    # warnings above are unchanged and keep carrying every message.
    reason_codes: list[Message] = field(default_factory=list)
    warning_codes: list[Message] = field(default_factory=list)


def _insufficient_data_result(warnings: list[str]) -> RecommendationResult:
    return RecommendationResult(
        status=RecommendationStatus.INSUFFICIENT_DATA,
        recommended_min_mm=0.0,
        recommended_max_mm=0.0,
        recommended_min_m3_per_ha=0.0,
        recommended_max_m3_per_ha=0.0,
        total_min_volume_m3=0.0,
        total_max_volume_m3=0.0,
        window=None,
        reasons=["Insufficient data to produce a water-balance-based recommendation."],
        warnings=warnings,
        reason_codes=[
            Message(
                code="insufficient_data_recommendation",
                text_en="Insufficient data to produce a water-balance-based recommendation.",
            )
        ],
    )


def determine_recommendation(
    *,
    analysis_date: date,
    depletion_mm: float | None,
    taw_mm: float,
    raw_mm: float,
    irrigation_efficiency: float,
    practical_min_mm: float,
    practical_max_mm: float,
    field_area_hectares: float,
    forecast_precipitation_mm: float,
    forecast_window_hours: int,
    confidence_category: str,
    monitor_depletion_raw_ratio: float,
    irrigate_soon_depletion_raw_ratio: float,
    irrigate_now_depletion_raw_ratio: float,
    forecast_rain_delay_threshold_mm: float,
    min_replacement_fraction: float,
    max_replacement_fraction: float,
    uncertainty_range_padding_fraction_medium: float,
    uncertainty_range_padding_fraction_low: float,
    extra_reasons: list[str] | None = None,
    extra_warnings: list[str] | None = None,
) -> RecommendationResult:
    warnings = list(extra_warnings or [])
    reasons = list(extra_reasons or [])
    reason_codes: list[Message] = []
    warning_codes: list[Message] = []

    if depletion_mm is None:
        return _insufficient_data_result(warnings)
    if taw_mm <= 0 or raw_mm <= 0:
        raise ValueError("taw_mm and raw_mm must be positive")

    ratio_raw = depletion_mm / raw_mm
    ratio_taw = depletion_mm / taw_mm
    reasons.append(
        f"Estimated depletion is {depletion_mm:.1f}mm, which is {ratio_raw * 100:.0f}% of RAW "
        f"({raw_mm:.1f}mm) and {ratio_taw * 100:.0f}% of TAW ({taw_mm:.1f}mm)."
    )
    reason_codes.append(
        Message(
            code="depletion_summary",
            text_en=reasons[-1],
            params={
                "depletion_mm": round(depletion_mm, 1),
                "raw_mm": round(raw_mm, 1),
                "taw_mm": round(taw_mm, 1),
                "raw_percent": round(ratio_raw * 100),
                "taw_percent": round(ratio_taw * 100),
            },
        )
    )

    if ratio_raw < monitor_depletion_raw_ratio:
        status = RecommendationStatus.NO_IRRIGATION_NEEDED
    elif ratio_raw < irrigate_soon_depletion_raw_ratio:
        status = RecommendationStatus.MONITOR
    elif ratio_raw < irrigate_now_depletion_raw_ratio:
        status = RecommendationStatus.IRRIGATE_SOON
    else:
        status = RecommendationStatus.IRRIGATE_NOW

    needs_irrigation = status in (
        RecommendationStatus.IRRIGATE_SOON,
        RecommendationStatus.IRRIGATE_NOW,
    )

    min_mm = max_mm = 0.0
    base_gross_mm: float | None = None
    if needs_irrigation:
        base_gross_mm = depletion_mm / irrigation_efficiency
        min_mm = base_gross_mm * min_replacement_fraction
        max_mm = base_gross_mm * max_replacement_fraction

        if confidence_category != "high":
            # Two separate constants (medium narrower than low) rather than
            # one shared value — see recommendation_defaults.yaml. High
            # confidence gets no padding at all (this branch never runs).
            padding_fraction = (
                uncertainty_range_padding_fraction_medium
                if confidence_category == "medium"
                else uncertainty_range_padding_fraction_low
            )
            padding = padding_fraction * base_gross_mm
            min_mm = max(0.0, min_mm - padding)
            max_mm = max_mm + padding
            reasons.append(
                f"Confidence is '{confidence_category}', not 'high', so the range is widened by "
                f"{padding_fraction * 100:.0f}% to avoid appearing more precise "
                "than the underlying data supports."
            )
            reason_codes.append(
                Message(
                    code="confidence_range_widened",
                    text_en=reasons[-1],
                    params={
                        "confidence_category": confidence_category,
                        "padding_percent": round(padding_fraction * 100),
                    },
                )
            )

        pre_clamp_min, pre_clamp_max = min_mm, max_mm
        min_mm = clamp(min_mm, practical_min_mm, practical_max_mm)
        max_mm = clamp(max_mm, practical_min_mm, practical_max_mm)
        max_mm = max(max_mm, min_mm)
        if (pre_clamp_min, pre_clamp_max) != (min_mm, max_mm):
            warnings.append(
                f"Computed range ({pre_clamp_min:.1f}-{pre_clamp_max:.1f}mm) was clamped to this "
                f"crop's practical application limits ({practical_min_mm:.1f}-"
                f"{practical_max_mm:.1f}mm)."
            )
            warning_codes.append(
                Message(
                    code="recommendation_clamped_to_practical_limits",
                    text_en=warnings[-1],
                    params={
                        "pre_clamp_min_mm": round(pre_clamp_min, 1),
                        "pre_clamp_max_mm": round(pre_clamp_max, 1),
                        "practical_min_mm": round(practical_min_mm, 1),
                        "practical_max_mm": round(practical_max_mm, 1),
                    },
                )
            )

    forecast_window_days = max(1, -(-forecast_window_hours // 24))  # ceiling division
    if needs_irrigation and forecast_precipitation_mm >= forecast_rain_delay_threshold_mm:
        status = RecommendationStatus.DELAY_DUE_TO_FORECAST_RAIN
        reasons.append(
            f"Forecast precipitation over the next {forecast_window_hours}h is "
            f"{forecast_precipitation_mm:.1f}mm, at/above the "
            f"{forecast_rain_delay_threshold_mm:.1f}mm threshold — delaying the irrigation "
            "recommendation rather than applying water shortly before rain."
        )
        reason_codes.append(
            Message(
                code="forecast_rain_delay",
                text_en=reasons[-1],
                params={
                    "forecast_window_hours": forecast_window_hours,
                    "forecast_precipitation_mm": round(forecast_precipitation_mm, 1),
                    "threshold_mm": round(forecast_rain_delay_threshold_mm, 1),
                },
            )
        )

    window: RecommendationWindow | None
    if status == RecommendationStatus.IRRIGATE_NOW:
        window = RecommendationWindow(analysis_date, analysis_date + timedelta(days=1))
    elif status == RecommendationStatus.IRRIGATE_SOON:
        window = RecommendationWindow(
            analysis_date + timedelta(days=1), analysis_date + timedelta(days=4)
        )
    elif status == RecommendationStatus.DELAY_DUE_TO_FORECAST_RAIN:
        window = RecommendationWindow(
            analysis_date + timedelta(days=forecast_window_days),
            analysis_date + timedelta(days=forecast_window_days + 3),
        )
    elif status == RecommendationStatus.MONITOR:
        window = RecommendationWindow(
            analysis_date + timedelta(days=3), analysis_date + timedelta(days=7)
        )
    else:
        window = None

    return RecommendationResult(
        status=status,
        recommended_min_mm=min_mm,
        recommended_max_mm=max_mm,
        recommended_min_m3_per_ha=min_mm * MM_PER_HA_TO_M3,
        recommended_max_m3_per_ha=max_mm * MM_PER_HA_TO_M3,
        total_min_volume_m3=min_mm * MM_PER_HA_TO_M3 * field_area_hectares,
        total_max_volume_m3=max_mm * MM_PER_HA_TO_M3 * field_area_hectares,
        window=window,
        depletion_mm=depletion_mm,
        base_gross_mm=base_gross_mm,
        reasons=reasons,
        warnings=warnings,
        reason_codes=reason_codes,
        warning_codes=warning_codes,
    )
