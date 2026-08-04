"""CdseSentinelHubProvider — the SatelliteProvider implementation used when
DATA_MODE=live.

Composes CdseCatalogClient (acquisition discovery over the real field
polygon), CdseStatisticsClient (full-polygon parcel statistics), and
per-observation quality classification (quality.py) behind the same
interface FixtureSatelliteProvider implements, so
app/services/analysis.py does not need to know which mode it is running in
— see app/providers/factory.py for the DATA_MODE-driven selection.
"""

import asyncio
import json
import logging
from datetime import UTC, date, datetime, timedelta

from app.core.cache import TTLCache
from app.providers.satellite.base import (
    IndexStatistics,
    ParcelObservation,
    RejectedAcquisition,
    SatelliteTimeseries,
)
from app.providers.satellite.catalog import CdseCatalogClient
from app.providers.satellite.quality import classify_observation
from app.providers.satellite.statistics import INDEX_NAMES, CdseStatisticsClient

logger = logging.getLogger("app.providers.satellite.cdse")

PROVIDER_NAME = "cdse-sentinel-hub"


def _polygon_cache_key(polygon: dict) -> str:
    return json.dumps(polygon, sort_keys=True)


class CdseSentinelHubProvider:
    def __init__(
        self,
        *,
        catalog_client: CdseCatalogClient,
        statistics_client: CdseStatisticsClient,
        max_cloud_cover_pct: float,
        min_valid_pixel_ratio: float,
        max_observation_age_days: int | None,
        cache: TTLCache | None = None,
        cache_ttl_seconds: float = 0,
    ) -> None:
        self._catalog_client = catalog_client
        self._statistics_client = statistics_client
        self._max_cloud_cover_pct = max_cloud_cover_pct
        self._min_valid_pixel_ratio = min_valid_pixel_ratio
        self._max_observation_age_days = max_observation_age_days
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    def get_index_timeseries(
        self, polygon: dict, start_date: date, end_date: date
    ) -> SatelliteTimeseries:
        return self.get_index_timeseries_for_range(polygon, start_date, end_date)

    def get_latest_observation(self, polygon: dict, as_of: date) -> ParcelObservation | None:
        lookback_start = as_of - timedelta(days=90)
        series = self.get_index_timeseries_for_range(polygon, lookback_start, as_of)
        usable = [o for o in series.observations if o.quality_status == "usable"]
        if not usable:
            return None
        return max(usable, key=lambda o: o.acquisition_date)

    def get_index_timeseries_for_range(
        self, polygon: dict, start_date: date, end_date: date
    ) -> SatelliteTimeseries:
        return asyncio.run(self._get_async(polygon, start_date, end_date))

    async def _get_async(
        self, polygon: dict, start_date: date, end_date: date
    ) -> SatelliteTimeseries:
        cache_key = ("satellite", _polygon_cache_key(polygon), start_date, end_date)
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached.model_copy(update={"cache_hit": True})

        catalog_result = await self._catalog_client.search(
            polygon,
            start_date=start_date,
            end_date=end_date,
            max_cloud_cover_pct=self._max_cloud_cover_pct,
        )
        rejected = [
            RejectedAcquisition(acquisition_date=r.acquisition_date, reason=r.reason)
            for r in catalog_result.rejected
        ]

        if not catalog_result.accepted:
            series = SatelliteTimeseries(
                observations=[],
                provider=PROVIDER_NAME,
                source="CDSE Sentinel Hub (live)",
                retrieved_at=datetime.now(UTC),
                requested_start_date=start_date,
                requested_end_date=end_date,
                rejected_acquisitions=rejected,
            )
            self._maybe_cache(cache_key, series)
            return series

        interval_stats = await self._statistics_client.get_parcel_statistics(
            polygon, start_date=start_date, end_date=end_date
        )
        stats_by_date = {s.interval_start: s for s in interval_stats}

        observations: list[ParcelObservation] = []
        for acquisition in catalog_result.accepted:
            stats = stats_by_date.get(acquisition.acquisition_date)
            if stats is None:
                rejected.append(
                    RejectedAcquisition(
                        acquisition_date=acquisition.acquisition_date,
                        reason="no usable Statistical API pixels for this acquisition date",
                    )
                )
                continue

            total_pixels = stats.valid_pixel_count + stats.invalid_pixel_count
            valid_ratio = stats.valid_pixel_count / total_pixels if total_pixels > 0 else 0.0
            invalid_pct = 100.0 * (1.0 - valid_ratio)

            all_values = [v for idx in INDEX_NAMES for v in stats.index_stats[idx].values()]
            assessment = classify_observation(
                valid_pixel_ratio=valid_ratio,
                invalid_pixel_percentage=invalid_pct,
                acquisition_date=acquisition.acquisition_date,
                as_of=end_date,
                index_values=all_values,
                min_valid_pixel_ratio=self._min_valid_pixel_ratio,
                max_observation_age_days=self._max_observation_age_days,
            )

            observations.append(
                ParcelObservation(
                    acquisition_date=acquisition.acquisition_date,
                    valid_pixel_count=stats.valid_pixel_count,
                    invalid_pixel_count=stats.invalid_pixel_count,
                    valid_pixel_ratio=valid_ratio,
                    cloud_or_invalid_percentage=invalid_pct,
                    ndvi=IndexStatistics(**stats.index_stats["ndvi"]),
                    ndmi=IndexStatistics(**stats.index_stats["ndmi"]),
                    ndre=IndexStatistics(**stats.index_stats["ndre"]),
                    msi=IndexStatistics(**stats.index_stats["msi"]),
                    ndwi=IndexStatistics(**stats.index_stats["ndwi"]),
                    nbr2=IndexStatistics(**stats.index_stats["nbr2"]),
                    scene_id=acquisition.scene_id,
                    quality_status=assessment.status.value,
                    quality_warnings=assessment.warnings,
                )
            )

        observations.sort(key=lambda o: o.acquisition_date)
        series = SatelliteTimeseries(
            observations=observations,
            provider=PROVIDER_NAME,
            source="CDSE Sentinel Hub (live)",
            retrieved_at=datetime.now(UTC),
            requested_start_date=start_date,
            requested_end_date=end_date,
            rejected_acquisitions=rejected,
        )
        self._maybe_cache(cache_key, series)
        return series

    def _maybe_cache(self, key: tuple, series: SatelliteTimeseries) -> None:
        if self._cache is not None and self._cache_ttl_seconds > 0:
            self._cache.set(key, series, self._cache_ttl_seconds)
