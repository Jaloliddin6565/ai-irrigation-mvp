from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import analyses, config_options, farmers, fields, health, irrigations
from app.core.errors import (
    AppError,
    UnhandledExceptionMiddleware,
    app_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging
from app.core.pilot_auth import PilotBasicAuthMiddleware
from app.settings import FRONTEND_DIST_DIR, get_settings

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="AI Irrigation MVP API",
    version="0.1.0",
    description=(
        "Sensor-free irrigation decision-support API. Estimates only — this "
        "system does not directly measure soil moisture. Farmer-level "
        "authentication is not implemented in this MVP; public deployment is "
        "allowed only behind the controlled pilot access gate."
    ),
)

# Order matters: UnhandledExceptionMiddleware must be added BEFORE
# CORSMiddleware so that CORSMiddleware ends up outermost and still applies
# its headers to the 500 responses this middleware builds.
app.add_middleware(UnhandledExceptionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A shared HTTP Basic gate protects the whole pilot deployment while the
# farmer-level authentication/authorization layer remains intentionally
# deferred. /health stays public for Render health checks.
if settings.app_env == "pilot":
    pilot_username, pilot_password = settings.require_pilot_credentials()
    app.add_middleware(
        PilotBasicAuthMiddleware,
        username=pilot_username,
        password=pilot_password,
    )

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]

app.include_router(health.router)
app.include_router(config_options.router)
app.include_router(farmers.router)
app.include_router(fields.router)
app.include_router(irrigations.router)
app.include_router(analyses.router)

# The Render pilot image bundles the Vite build into the backend image. Local
# development still uses the separate Vite dev server because this directory
# is absent outside the production Docker build.
_assets_dir = FRONTEND_DIST_DIR / "assets"
if _assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="frontend-assets")


if FRONTEND_DIST_DIR.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str) -> FileResponse:
        candidate = (FRONTEND_DIST_DIR / full_path).resolve()
        frontend_root = FRONTEND_DIST_DIR.resolve()
        if candidate.is_file() and frontend_root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(Path(frontend_root) / "index.html")
