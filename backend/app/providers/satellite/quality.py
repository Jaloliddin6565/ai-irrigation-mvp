"""Per-observation satellite data-quality classification.

This is a provider-layer concern: deciding whether a single parcel
observation returned by CDSE is trustworthy enough to even become a
`ParcelObservation` the rest of the system reasons about. It is distinct
from — and composes with — `app/domain/satellite_adjustment.py`, which
decides (given a set of already-usable observations) whether there is
enough of a *trend* to adjust the water balance. Nothing here changes that
existing Phase 3 logic; it runs strictly upstream of it. See
docs/methodology.md.
"""

import math
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class SatelliteQualityStatus(StrEnum):
    USABLE = "usable"
    LOW_VALID_PIXEL_RATIO = "low_valid_pixel_ratio"
    STALE = "stale"
    CLOUD_CONTAMINATED = "cloud_contaminated"
    NO_DATA = "no_data"
    MALFORMED_RESPONSE = "malformed_response"
    NON_FINITE_VALUES = "non_finite_values"
    INSUFFICIENT_OBSERVATIONS = "insufficient_observations"


@dataclass(frozen=True)
class QualityAssessment:
    status: SatelliteQualityStatus
    warnings: list[str] = field(default_factory=list)
    rejection_reason: str | None = None

    @property
    def is_usable(self) -> bool:
        return self.status == SatelliteQualityStatus.USABLE


def _is_finite(value: float) -> bool:
    return not (math.isnan(value) or math.isinf(value))


def classify_observation(
    *,
    valid_pixel_ratio: float,
    invalid_pixel_percentage: float,
    acquisition_date: date,
    as_of: date,
    index_values: list[float],
    min_valid_pixel_ratio: float,
    max_observation_age_days: int | None,
    cloud_contamination_invalid_pct_threshold: float = 50.0,
) -> QualityAssessment:
    """Classify one already-parsed observation.

    Checked in order: non-finite values, an impossible future acquisition
    date, valid-pixel ratio, cloud/invalid contamination, then freshness.
    The first failing check wins — an observation is reported as usable
    only if it clears every one of them.
    """
    if any(not _is_finite(v) for v in index_values):
        return QualityAssessment(
            status=SatelliteQualityStatus.NON_FINITE_VALUES,
            warnings=["Observation dropped: one or more index values were not finite."],
            rejection_reason="non_finite_index_values",
        )

    if acquisition_date > as_of:
        return QualityAssessment(
            status=SatelliteQualityStatus.MALFORMED_RESPONSE,
            warnings=["Observation dropped: acquisition date is after the analysis date."],
            rejection_reason="acquisition_date_in_future",
        )

    if valid_pixel_ratio < min_valid_pixel_ratio:
        return QualityAssessment(
            status=SatelliteQualityStatus.LOW_VALID_PIXEL_RATIO,
            warnings=[
                f"Valid-pixel ratio {valid_pixel_ratio:.2f} is below the configured minimum "
                f"{min_valid_pixel_ratio:.2f}."
            ],
            rejection_reason="low_valid_pixel_ratio",
        )

    if invalid_pixel_percentage > cloud_contamination_invalid_pct_threshold:
        return QualityAssessment(
            status=SatelliteQualityStatus.CLOUD_CONTAMINATED,
            warnings=[
                f"Invalid/cloud pixel percentage {invalid_pixel_percentage:.1f}% exceeds "
                f"{cloud_contamination_invalid_pct_threshold:.1f}%."
            ],
            rejection_reason="cloud_contaminated",
        )

    if max_observation_age_days is not None:
        age_days = (as_of - acquisition_date).days
        if age_days > max_observation_age_days:
            return QualityAssessment(
                status=SatelliteQualityStatus.STALE,
                warnings=[
                    f"Observation is {age_days} days old, older than the configured "
                    f"{max_observation_age_days}-day freshness limit."
                ],
                rejection_reason="stale",
            )

    return QualityAssessment(status=SatelliteQualityStatus.USABLE, warnings=[])
