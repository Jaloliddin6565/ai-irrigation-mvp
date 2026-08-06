"""Conservative satellite-based qualification of the water balance.

This NEVER replaces the water balance and NEVER converts spectral indices
into an exact root-zone soil-moisture value — it only nudges the estimated
depletion within a small, capped range when at least two fresh,
high-quality observations agree on a direction, and always says so
explicitly. See docs/methodology.md.

Signal: NDMI (near-infrared/shortwave-infrared moisture index), MSI
(moisture stress index — higher means more canopy water stress, i.e. the
opposite sense of NDMI/NDVI), and NDVI (vegetation vigor) trends between the
earliest and latest usable observation. An adjustment is only applied when
at least 2 of these 3 indices agree on direction ("drier" or "wetter") —
a single observation, or indices that disagree, produce no adjustment.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from app.domain.water_balance import clamp


class SatelliteDataQuality(StrEnum):
    OK = "ok"
    STALE = "stale"
    LOW_QUALITY = "low_quality"
    INSUFFICIENT = "insufficient"


# Below this absolute change, an index delta is treated as noise, not trend.
_INDEX_DELTA_NOISE_FLOOR = 0.02


@dataclass(frozen=True)
class SatelliteObservationInput:
    acquisition_date: date
    valid_pixel_ratio: float
    ndmi_p50: float
    msi_p50: float
    ndvi_p50: float


@dataclass(frozen=True)
class SatelliteAdjustmentResult:
    applied: bool
    adjustment_mm: float
    valid_observations_used: int
    latest_observation_date: date | None
    latest_observation_age_days: int | None
    latest_valid_pixel_ratio: float | None
    data_quality: SatelliteDataQuality
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _vote(delta: float) -> int:
    """+1 = trending drier, -1 = trending wetter, 0 = inconclusive/noise."""
    if delta > _INDEX_DELTA_NOISE_FLOOR:
        return 1
    if delta < -_INDEX_DELTA_NOISE_FLOOR:
        return -1
    return 0


def determine_satellite_adjustment(
    *,
    analysis_date: date,
    observations: list[SatelliteObservationInput],
    min_valid_observations_for_trend: int,
    max_observation_age_days_for_trend: int,
    low_valid_pixel_ratio_threshold: float,
    trend_adjustment_cap_fraction_of_raw: float,
    raw_mm: float,
) -> SatelliteAdjustmentResult:
    past_observations = sorted(
        (obs for obs in observations if obs.acquisition_date <= analysis_date),
        key=lambda obs: obs.acquisition_date,
    )

    if not past_observations:
        return SatelliteAdjustmentResult(
            applied=False,
            adjustment_mm=0.0,
            valid_observations_used=0,
            latest_observation_date=None,
            latest_observation_age_days=None,
            latest_valid_pixel_ratio=None,
            data_quality=SatelliteDataQuality.INSUFFICIENT,
            warnings=["No satellite observations available; continuing water-balance-only."],
        )

    latest = past_observations[-1]
    latest_age_days = (analysis_date - latest.acquisition_date).days

    usable = [
        obs
        for obs in past_observations
        if obs.valid_pixel_ratio >= low_valid_pixel_ratio_threshold
        and (analysis_date - obs.acquisition_date).days <= max_observation_age_days_for_trend
    ]

    if len(usable) < min_valid_observations_for_trend:
        if latest_age_days > max_observation_age_days_for_trend:
            quality = SatelliteDataQuality.STALE
        elif latest.valid_pixel_ratio < low_valid_pixel_ratio_threshold:
            quality = SatelliteDataQuality.LOW_QUALITY
        else:
            quality = SatelliteDataQuality.INSUFFICIENT
        return SatelliteAdjustmentResult(
            applied=False,
            adjustment_mm=0.0,
            valid_observations_used=len(usable),
            latest_observation_date=latest.acquisition_date,
            latest_observation_age_days=latest_age_days,
            latest_valid_pixel_ratio=latest.valid_pixel_ratio,
            data_quality=quality,
            warnings=[
                f"Fewer than {min_valid_observations_for_trend} fresh, high-quality satellite "
                "observations available; no satellite adjustment applied. Confidence is "
                "reduced accordingly."
            ],
        )

    first, last = usable[0], usable[-1]
    ndmi_delta = last.ndmi_p50 - first.ndmi_p50
    msi_delta = last.msi_p50 - first.msi_p50
    ndvi_delta = last.ndvi_p50 - first.ndvi_p50

    # Sign convention: +1 vote = "trending drier".
    votes = [_vote(-ndmi_delta), _vote(msi_delta), _vote(-ndvi_delta)]
    drier_votes = sum(1 for v in votes if v > 0)
    wetter_votes = sum(1 for v in votes if v < 0)

    reasons = [
        f"NDMI change {ndmi_delta:+.3f}, MSI change {msi_delta:+.3f}, NDVI change "
        f"{ndvi_delta:+.3f} between {first.acquisition_date.isoformat()} and "
        f"{last.acquisition_date.isoformat()} ({len(usable)} usable observations)."
    ]

    if drier_votes < 2 and wetter_votes < 2:
        reasons.append("Indices did not agree on a direction; no satellite adjustment applied.")
        return SatelliteAdjustmentResult(
            applied=False,
            adjustment_mm=0.0,
            valid_observations_used=len(usable),
            latest_observation_date=latest.acquisition_date,
            latest_observation_age_days=latest_age_days,
            latest_valid_pixel_ratio=latest.valid_pixel_ratio,
            data_quality=SatelliteDataQuality.OK,
            reasons=reasons,
        )

    agreement_strength = max(drier_votes, wetter_votes) / 3.0
    cap_mm = trend_adjustment_cap_fraction_of_raw * raw_mm
    magnitude = clamp(agreement_strength * cap_mm, 0.0, cap_mm)
    signed_adjustment = magnitude if drier_votes > wetter_votes else -magnitude

    direction = "drier" if drier_votes > wetter_votes else "wetter"
    reasons.append(
        f"{max(drier_votes, wetter_votes)}/3 indices agree the field is trending {direction}; "
        f"depletion estimate adjusted by {signed_adjustment:+.2f}mm "
        f"(capped at {cap_mm:.2f}mm = {trend_adjustment_cap_fraction_of_raw * 100:.0f}% of RAW). "
        "This qualifies, and does not replace, the water-balance estimate — spectral indices "
        "are not a direct measurement of root-zone soil moisture."
    )

    return SatelliteAdjustmentResult(
        applied=True,
        adjustment_mm=signed_adjustment,
        valid_observations_used=len(usable),
        latest_observation_date=latest.acquisition_date,
        latest_observation_age_days=latest_age_days,
        latest_valid_pixel_ratio=latest.valid_pixel_ratio,
        data_quality=SatelliteDataQuality.OK,
        reasons=reasons,
    )
