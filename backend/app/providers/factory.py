"""DATA_MODE-driven provider selection.

This is the single place that decides whether fixture or live weather/
satellite providers are used. Application code (app/services/analysis.py,
app/api/analyses.py) must call these factories instead of importing a
concrete provider class directly — that is what makes "DATA_MODE=live never
silently falls back to fixture data" (CLAUDE.md rule 5) an architectural
property rather than a per-call-site discipline.

CDSE credentials are read once per process (via `get_settings()`, itself
process-cached) and the OAuth token client is a process-lifetime singleton
so tokens are genuinely cached across requests — constructing a fresh
`CdseSentinelHubProvider` per request is fine and expected; each one shares
the same underlying token client and response caches.
"""

from functools import lru_cache

from app.core.cache import TTLCache
from app.core.provider_errors import ProviderConfigurationError
from app.providers.satellite.base import SatelliteProvider
from app.providers.satellite.catalog import CdseCatalogClient
from app.providers.satellite.cdse import CdseSentinelHubProvider
from app.providers.satellite.cdse_auth import CdseTokenClient
from app.providers.satellite.fixture import FixtureSatelliteProvider
from app.providers.satellite.statistics import CdseStatisticsClient
from app.providers.weather.base import WeatherProvider
from app.providers.weather.fixture import FixtureWeatherProvider
from app.providers.weather.open_meteo import OpenMeteoProvider
from app.settings import FIXTURES_DIR, DataMode, get_settings

CDSE_PROVIDER_NAME = "cdse-sentinel-hub"


@lru_cache
def _weather_cache() -> TTLCache:
    return TTLCache()


@lru_cache
def _satellite_cache() -> TTLCache:
    return TTLCache()


def _require_live_satellite_credentials() -> tuple[str, str]:
    settings = get_settings()
    try:
        return settings.require_live_satellite_credentials()
    except RuntimeError as exc:
        raise ProviderConfigurationError(
            provider=CDSE_PROVIDER_NAME,
            message_en=str(exc),
            message_uz=(
                "DATA_MODE=live uchun CDSE_CLIENT_ID va CDSE_CLIENT_SECRET sozlanishi shart."
            ),
        ) from exc


@lru_cache
def _cdse_token_client() -> CdseTokenClient:
    settings = get_settings()
    client_id, client_secret = _require_live_satellite_credentials()
    return CdseTokenClient(
        client_id=client_id,
        client_secret=client_secret,
        token_url=settings.cdse_token_url,
        expiry_margin_seconds=settings.token_expiry_margin_seconds,
        timeout_seconds=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
        retry_base_delay_seconds=settings.http_retry_base_delay_seconds,
        retry_max_delay_seconds=settings.http_retry_max_delay_seconds,
    )


def get_weather_provider() -> WeatherProvider:
    settings = get_settings()
    if settings.data_mode == DataMode.FIXTURE:
        return FixtureWeatherProvider(FIXTURES_DIR)

    return OpenMeteoProvider(
        forecast_url=settings.open_meteo_forecast_url,
        archive_url=settings.open_meteo_archive_url,
        timezone=settings.timezone,
        timeout_seconds=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
        retry_base_delay_seconds=settings.http_retry_base_delay_seconds,
        retry_max_delay_seconds=settings.http_retry_max_delay_seconds,
        cache=_weather_cache(),
        cache_ttl_seconds=settings.weather_cache_ttl_seconds,
    )


def get_satellite_provider() -> SatelliteProvider:
    settings = get_settings()
    if settings.data_mode == DataMode.FIXTURE:
        return FixtureSatelliteProvider(FIXTURES_DIR)

    token_client = _cdse_token_client()
    catalog_client = CdseCatalogClient(
        catalog_url=settings.cdse_catalog_url,
        token_client=token_client,
        timeout_seconds=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
        retry_base_delay_seconds=settings.http_retry_base_delay_seconds,
        retry_max_delay_seconds=settings.http_retry_max_delay_seconds,
    )
    statistics_client = CdseStatisticsClient(
        statistics_url=settings.cdse_statistics_url,
        token_client=token_client,
        timeout_seconds=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
        retry_base_delay_seconds=settings.http_retry_base_delay_seconds,
        retry_max_delay_seconds=settings.http_retry_max_delay_seconds,
    )
    return CdseSentinelHubProvider(
        catalog_client=catalog_client,
        statistics_client=statistics_client,
        max_cloud_cover_pct=settings.max_scene_cloud_cover,
        min_valid_pixel_ratio=settings.min_valid_pixel_ratio,
        max_observation_age_days=settings.max_satellite_observation_age_days,
        cache=_satellite_cache(),
        cache_ttl_seconds=settings.satellite_cache_ttl_seconds,
    )
