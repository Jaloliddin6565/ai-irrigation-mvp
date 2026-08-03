"""SatelliteProvider interface.

Implementations must never fabricate an acquisition date or index value. If
no usable observation exists for the requested window, return an empty
observation list rather than inventing one — callers treat that as
insufficient_satellite_data.
"""

from datetime import date
from typing import Protocol

from pydantic import BaseModel


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


class SatelliteTimeseries(BaseModel):
    observations: list[ParcelObservation]


class SatelliteProvider(Protocol):
    def get_index_timeseries(
        self, polygon: dict, start_date: date, end_date: date
    ) -> SatelliteTimeseries:
        """Return all usable parcel-level observations in [start_date, end_date]."""
        ...

    def get_latest_observation(self, polygon: dict, as_of: date) -> ParcelObservation | None:
        """Return the most recent usable observation at or before as_of, if any."""
        ...
