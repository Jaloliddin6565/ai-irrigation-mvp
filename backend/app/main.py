from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import config_options, health
from app.core.errors import AppError, app_error_handler
from app.core.logging import configure_logging
from app.settings import get_settings

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="AI Irrigation MVP API",
    version="0.1.0",
    description=(
        "Sensor-free irrigation decision-support API. Estimates only — this "
        "system does not directly measure soil moisture. No authentication "
        "in this MVP; not suitable for public deployment. See CLAUDE.md."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

app.include_router(health.router)
app.include_router(config_options.router)
