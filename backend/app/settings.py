"""Application configuration.

All values are read from the environment (and a local .env file in
development). This module is the only place that reads DATA_MODE and
provider credentials directly — everything else receives already-resolved
settings via dependency injection.
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
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

    data_mode: DataMode = Field(default=DataMode.FIXTURE, alias="DATA_MODE")

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

    # Weather provider (Open-Meteo) — live mode only.
    open_meteo_base_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        alias="OPEN_METEO_BASE_URL",
    )

    # Satellite provider (Copernicus Data Space Ecosystem / Sentinel Hub) — live mode only.
    cdse_client_id: str | None = Field(default=None, alias="CDSE_CLIENT_ID")
    cdse_client_secret: str | None = Field(default=None, alias="CDSE_CLIENT_SECRET")
    cdse_identity_token_url: str = Field(
        default="https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        alias="CDSE_IDENTITY_TOKEN_URL",
    )
    cdse_sh_base_url: str = Field(
        default="https://sh.dataspace.copernicus.eu",
        alias="CDSE_SH_BASE_URL",
    )

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
