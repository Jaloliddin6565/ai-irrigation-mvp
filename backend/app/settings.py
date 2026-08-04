"""Application configuration.

All values are read from the environment (and a local .env file in
development). This module is the only place that reads DATA_MODE and
provider credentials directly — everything else receives already-resolved
settings via dependency injection.

Never log a Settings instance directly (str(settings) would include
cdse_client_secret) — read individual non-secret fields instead.
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = BACKEND_ROOT / "config"
FIXTURES_DIR = BACKEND_ROOT / "fixtures"


class DataMode(StrEnum):
    FIXTURE = "fixture"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    data_mode: DataMode = Field(default=DataMode.FIXTURE, alias="DATA_MODE")
    timezone: str = Field(default="Asia/Tashkent", alias="TIMEZONE")

    database_url: str = Field(
        default=f"sqlite:///{BACKEND_ROOT / 'ai_irrigation.db'}",
        alias="DATABASE_URL",
    )

    cors_allowed_origins: str = Field(default="http://localhost:5173", alias="CORS_ALLOWED_ORIGINS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Field polygon validation limits — deliberately conservative defaults;
    # see docs/validation.md.
    max_field_area_hectares: float = Field(default=500.0, alias="MAX_FIELD_AREA_HECTARES")
    max_polygon_vertices: int = Field(default=1000, alias="MAX_POLYGON_VERTICES")

    # List-endpoint pagination limits.
    default_list_limit: int = Field(default=50, alias="DEFAULT_LIST_LIMIT")
    max_list_limit: int = Field(default=200, alias="MAX_LIST_LIMIT")

    # --- Weather provider (Open-Meteo) — live mode only, no API key required
    # for non-commercial use. Two base URLs because Open-Meteo splits
    # historical ("archive") and forecast data across separate hosts. See
    # docs/api.md for verification date. ---
    open_meteo_forecast_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        alias="OPEN_METEO_FORECAST_URL",
    )
    open_meteo_archive_url: str = Field(
        default="https://archive-api.open-meteo.com/v1/archive",
        alias="OPEN_METEO_ARCHIVE_URL",
    )

    # --- Satellite provider (Copernicus Data Space Ecosystem / Sentinel Hub)
    # — live mode only. Endpoints verified against official Copernicus
    # documentation; see docs/api.md for the verification date. All are
    # configurable because CDSE announced (2026-03-09) a path-format
    # migration — see docs/api.md "CDSE endpoint verification". ---
    cdse_client_id: str | None = Field(default=None, alias="CDSE_CLIENT_ID")
    cdse_client_secret: str | None = Field(default=None, alias="CDSE_CLIENT_SECRET")
    cdse_token_url: str = Field(
        default="https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        alias="CDSE_TOKEN_URL",
    )
    cdse_sh_base_url: str = Field(
        default="https://sh.dataspace.copernicus.eu",
        alias="CDSE_SH_BASE_URL",
    )
    cdse_catalog_url: str = Field(
        default="https://sh.dataspace.copernicus.eu/catalog/v1/search",
        alias="CDSE_CATALOG_URL",
    )
    cdse_statistics_url: str = Field(
        default="https://sh.dataspace.copernicus.eu/statistics/v1",
        alias="CDSE_STATISTICS_URL",
    )
    cdse_process_url: str = Field(
        default="https://sh.dataspace.copernicus.eu/process/v1",
        alias="CDSE_PROCESS_URL",
    )

    # --- Satellite data-quality thresholds (live mode). ---
    satellite_lookback_days: int = Field(default=90, alias="SATELLITE_LOOKBACK_DAYS")
    min_valid_pixel_ratio: float = Field(default=0.60, alias="MIN_VALID_PIXEL_RATIO")
    max_scene_cloud_cover: float = Field(default=80.0, alias="MAX_SCENE_CLOUD_COVER")
    max_satellite_observation_age_days: int | None = Field(
        default=None, alias="MAX_SATELLITE_OBSERVATION_AGE_DAYS"
    )
    token_expiry_margin_seconds: int = Field(default=120, alias="TOKEN_EXPIRY_MARGIN_SECONDS")

    # --- Outbound HTTP client (both live providers). ---
    http_timeout_seconds: float = Field(default=30.0, alias="HTTP_TIMEOUT_SECONDS")
    http_max_retries: int = Field(default=3, alias="HTTP_MAX_RETRIES")
    http_retry_base_delay_seconds: float = Field(default=0.5, alias="HTTP_RETRY_BASE_DELAY_SECONDS")
    http_retry_max_delay_seconds: float = Field(default=8.0, alias="HTTP_RETRY_MAX_DELAY_SECONDS")

    # --- Provider response caching (live mode). An in-memory MVP cache; see
    # app/core/cache.py and docs/architecture.md for the Redis-swap design. ---
    weather_cache_ttl_seconds: int = Field(default=3600, alias="WEATHER_CACHE_TTL_SECONDS")
    satellite_cache_ttl_seconds: int = Field(default=3600, alias="SATELLITE_CACHE_TTL_SECONDS")

    # --- Frontend map tiles (read by the frontend build, not the backend;
    # kept here too so one .env documents the full variable set). ---
    map_tile_url: str = Field(
        default="https://tile.openstreetmap.org/{z}/{x}/{y}.png", alias="MAP_TILE_URL"
    )
    map_tile_attribution: str = Field(
        default="© OpenStreetMap contributors", alias="MAP_TILE_ATTRIBUTION"
    )

    @field_validator("max_satellite_observation_age_days", mode="before")
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        # .env.example documents this as an optional, commonly-blank field
        # (no freshness cap by default) — an empty string from a real .env
        # must resolve to "unset", not a parse error.
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    def require_live_satellite_credentials(self) -> tuple[str, str]:
        """Raise clearly if live mode is selected without CDSE credentials.

        Never falls back to fixture data — the caller must surface this as a
        configuration error to the client.
        """
        if not self.cdse_client_id or not self.cdse_client_secret:
            raise RuntimeError(
                "DATA_MODE=live requires CDSE_CLIENT_ID and CDSE_CLIENT_SECRET to be set. "
                "Refusing to silently fall back to fixture data."
            )
        return self.cdse_client_id, self.cdse_client_secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
