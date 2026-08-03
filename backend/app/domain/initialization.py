"""Explicit water-balance initialization strategy.

Never starts the daily water balance from an unexplained arbitrary
depletion value. Tries, in order (see docs/methodology.md):

  1. RECENT_IRRIGATION_KNOWN_AMOUNT — a quantitative IrrigationEvent
     (amount_mm or total_volume_m3+area) within max_anchor_age_days: assume
     the field was at full allowable depletion (TAW) immediately before that
     irrigation, apply the known effective amount, roll forward from there.
  2. RECENT_IRRIGATION_DURATION_FLOW — same as (1) but the depth is derived
     from duration_minutes + flow_rate_m3_hour (lower confidence, same math).
  3. PLANTING_DATE_ASSUMPTION — planting_date is within max_anchor_age_days:
     assume near-field-capacity (zero depletion) at planting.
  4. CONSERVATIVE_DEFAULT — initialize at conservative_default_fraction_of_raw
     of RAW, anchored at the earliest date covered by available weather
     history, so there is at least some real data to roll forward through.
  5. INSUFFICIENT_DATA — none of the above apply; the caller must not guess
     further and should surface this as the overall analysis status.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from app.domain.irrigation_normalization import IrrigationDepthSource, normalize_irrigation_event
from app.domain.water_balance import clamp, compute_effective_irrigation


class InitializationMethod(StrEnum):
    RECENT_IRRIGATION_KNOWN_AMOUNT = "recent_irrigation_known_amount"
    RECENT_IRRIGATION_DURATION_FLOW = "recent_irrigation_duration_flow"
    PLANTING_DATE_ASSUMPTION = "planting_date_assumption"
    CONSERVATIVE_DEFAULT = "conservative_default"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class IrrigationEventInput:
    occurred_at: date
    amount_mm: float | None = None
    total_volume_m3: float | None = None
    duration_minutes: float | None = None
    flow_rate_m3_hour: float | None = None
    qualitative_amount: str | None = None


@dataclass(frozen=True)
class InitializationResult:
    method: InitializationMethod
    start_date: date | None
    starting_depletion_mm: float | None
    # 0.0 = well-grounded, 1.0 = maximally uncertain — same scale as the
    # crop/soil uncertainty_factor config values.
    uncertainty: float
    warnings: list[str] = field(default_factory=list)


_QUANTITATIVE_KNOWN_AMOUNT_SOURCES = (
    IrrigationDepthSource.DIRECT_AMOUNT_MM,
    IrrigationDepthSource.VOLUME_AND_AREA,
)


def determine_initialization(
    *,
    planting_date: date,
    analysis_date: date,
    irrigation_events: Iterable[IrrigationEventInput],
    field_area_hectares: float,
    qualitative_irrigation_mm: dict[str, float],
    irrigation_efficiency: float,
    max_anchor_age_days: int,
    conservative_default_fraction_of_raw: float,
    weather_available_dates: Iterable[date],
    taw_at: Callable[[date], float],
    raw_at: Callable[[date], float],
) -> InitializationResult:
    candidates = sorted(
        (
            event
            for event in irrigation_events
            if event.occurred_at <= analysis_date
            and (analysis_date - event.occurred_at).days <= max_anchor_age_days
        ),
        key=lambda event: event.occurred_at,
        reverse=True,
    )

    for event in candidates:
        normalized = normalize_irrigation_event(
            amount_mm=event.amount_mm,
            total_volume_m3=event.total_volume_m3,
            duration_minutes=event.duration_minutes,
            flow_rate_m3_hour=event.flow_rate_m3_hour,
            qualitative_amount=None,  # qualitative-only events are not a reliable anchor
            field_area_hectares=field_area_hectares,
            qualitative_irrigation_mm=qualitative_irrigation_mm,
        )
        if normalized.depth_mm is None or not normalized.is_quantitative:
            continue

        anchor_date = event.occurred_at
        taw_at_anchor = taw_at(anchor_date)
        effective_irrigation_mm = compute_effective_irrigation(
            normalized.depth_mm, irrigation_efficiency
        )
        starting_depletion_mm = clamp(taw_at_anchor - effective_irrigation_mm, 0.0, taw_at_anchor)

        is_direct = normalized.source in _QUANTITATIVE_KNOWN_AMOUNT_SOURCES
        method = (
            InitializationMethod.RECENT_IRRIGATION_KNOWN_AMOUNT
            if is_direct
            else InitializationMethod.RECENT_IRRIGATION_DURATION_FLOW
        )
        warnings = [
            *normalized.warnings,
            f"Initialized from a known irrigation event on {anchor_date.isoformat()}: assumed "
            "the field was at full allowable depletion immediately before that irrigation, "
            "then applied the known effective amount.",
        ]
        return InitializationResult(
            method=method,
            start_date=anchor_date,
            starting_depletion_mm=starting_depletion_mm,
            uncertainty=0.2 if is_direct else 0.35,
            warnings=warnings,
        )

    days_since_planting = (analysis_date - planting_date).days
    if 0 <= days_since_planting <= max_anchor_age_days:
        return InitializationResult(
            method=InitializationMethod.PLANTING_DATE_ASSUMPTION,
            start_date=planting_date,
            starting_depletion_mm=0.0,
            uncertainty=0.5,
            warnings=[
                "No usable recent irrigation record; assuming the field was near field "
                f"capacity at planting_date ({planting_date.isoformat()}) and rolling "
                "forward from there."
            ],
        )

    available_dates = sorted(weather_available_dates)
    if available_dates and available_dates[0] <= analysis_date:
        earliest = available_dates[0]
        starting_depletion_mm = conservative_default_fraction_of_raw * raw_at(earliest)
        return InitializationResult(
            method=InitializationMethod.CONSERVATIVE_DEFAULT,
            start_date=earliest,
            starting_depletion_mm=starting_depletion_mm,
            uncertainty=0.75,
            warnings=[
                "No recent irrigation record and no in-window planting date; initializing at "
                f"{conservative_default_fraction_of_raw * 100:.0f}% of RAW on "
                f"{earliest.isoformat()} (earliest available weather data) as a conservative "
                "default. Confidence is reduced."
            ],
        )

    return InitializationResult(
        method=InitializationMethod.INSUFFICIENT_DATA,
        start_date=None,
        starting_depletion_mm=None,
        uncertainty=1.0,
        warnings=[
            "Insufficient data to initialize the water balance: no recent irrigation record, "
            "no in-window planting date, and no usable weather history."
        ],
    )
