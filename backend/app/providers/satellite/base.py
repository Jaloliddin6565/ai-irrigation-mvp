"""SatelliteProvider interface.

Implementations must never fabricate an acquisition date or index value. If
no usable observation exists for the requested window, return an empty
observation list rather than inventing one — callers treat that as
insufficient_satellite_data.
"""

from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel, Field


class IndexStatistics(BaseModel):
    p25: float
    p50: float
    p75: float
    mean: float
    std: float
    min: float
    max: float


class ParcelObservation(BaseModel):
    acquisition_date: date
    valid_pixel_count: int
    invalid_pixel_count: int
    valid_pixel_ratio: float
    cloud_or_invalid_percentage: float
    ndvi: IndexStatistics
    ndmi: IndexStatistics
    ndre: IndexStatistics
    msi: IndexStatistics
    ndwi: IndexStatistics
    nbr2: IndexStatistics

    # Live-mode metadata. Fixture data leaves these at their defaults.
    scene_id: str | None = None
    quality_status: str = "usable"
    quality_warnings: list[str] = Field(default_factory=list)


class RejectedAcquisition(BaseModel):
    """An acquisition the Catalog API returned that was excluded before
    statistics were computed, and why — e.g. over the cloud-cover
    threshold. Never silently dropped; recorded so provenance stays honest."""

    acquisition_date: date
    reason: str


class SatelliteTimeseries(BaseModel):
    observations: list[ParcelObservation]
    provider: str = "fixture"
    source: str = "DEMO / FIXTURE DATA"
    retrieved_at: datetime | None = None
    cache_hit: bool = False
    requested_start_date: date | None = None
    requested_end_date: date | None = None
    rejected_acquisitions: list[RejectedAcquisition] = Field(default_factory=list)


class SatelliteProvider(Protocol):
    def get_index_timeseries(
        self, polygon: dict, start_date: date, end_date: date
    ) -> SatelliteTimeseries:
        """Return all usable parcel-level observations in [start_date, end_date]."""
        ...

    def get_latest_observation(self, polygon: dict, as_of: date) -> ParcelObservation | None:
        """Return the most recent usable observation at or before as_of, if any."""
        ...

    def get_index_timeseries_for_range(
        self, polygon: dict, start_date: date, end_date: date
    ) -> SatelliteTimeseries:
        """Return a parcel-level time series covering [start_date, end_date].

        Fixture implementations cycle a fixed deterministic demo dataset.
        Live implementations query the actual field polygon (never a
        centroid or an arbitrary bounding box) against the CDSE Catalog +
        Statistical APIs and return only real, dated acquisitions — an
        empty list means insufficient_satellite_data, never a fabricated
        substitute.
        """
        ...
