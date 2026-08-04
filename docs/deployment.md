# Deployment

Status: local development and controlled pilots only — see
`docs/security.md` "No authentication in this MVP". Nothing in this
document should be read as guidance for a public-internet-facing
deployment; that requires a real authentication/authorization layer this
MVP deliberately does not have yet.

## Environment configuration

All runtime configuration is environment variables, read once at process
start by `backend/app/settings.py` (`pydantic-settings`, `lru_cache`d — a
running process does not pick up a changed `.env` without a restart).
`.env.example` at the repo root lists every variable name; copy it to
`.env` and fill in real values locally. `.env` is git-ignored and must
never be committed — see `docs/security.md`.

| Group | Variables | Notes |
|---|---|---|
| App | `APP_ENV`, `TIMEZONE`, `DATA_MODE` | `DATA_MODE=fixture` for all local dev/CI |
| Backend | `DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `LOG_LEVEL` | SQLite path defaults to `backend/ai_irrigation.db` |
| Pagination/geometry limits | `MAX_FIELD_AREA_HECTARES`, `MAX_POLYGON_VERTICES`, `DEFAULT_LIST_LIMIT`, `MAX_LIST_LIMIT` | conservative defaults, see `docs/validation.md` |
| Open-Meteo (live only) | `OPEN_METEO_ARCHIVE_URL`, `OPEN_METEO_FORECAST_URL` | no API key required |
| CDSE (live only) | `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET`, `CDSE_TOKEN_URL`, `CDSE_SH_BASE_URL`, `CDSE_CATALOG_URL`, `CDSE_STATISTICS_URL`, `CDSE_PROCESS_URL` | see `docs/api.md` "CDSE endpoint verification" |
| Satellite quality (live only) | `SATELLITE_LOOKBACK_DAYS`, `MIN_VALID_PIXEL_RATIO`, `MAX_SCENE_CLOUD_COVER`, `MAX_SATELLITE_OBSERVATION_AGE_DAYS` | |
| HTTP client (live only) | `HTTP_TIMEOUT_SECONDS`, `HTTP_MAX_RETRIES`, `HTTP_RETRY_BASE_DELAY_SECONDS`, `HTTP_RETRY_MAX_DELAY_SECONDS`, `TOKEN_EXPIRY_MARGIN_SECONDS` | see `docs/architecture.md` "Shared HTTP/error/cache infrastructure" |
| Caching (live only) | `WEATHER_CACHE_TTL_SECONDS`, `SATELLITE_CACHE_TTL_SECONDS` | in-memory, process-local — see `app/core/cache.py` |
| Frontend | `VITE_API_BASE_URL`, `MAP_TILE_URL`/`VITE_MAP_TILE_URL`, `MAP_TILE_ATTRIBUTION`/`VITE_MAP_TILE_ATTRIBUTION` | |

## Local setup — fixture mode (default, no credentials)

See `README.md` "Getting started (fixture mode)". `DATA_MODE=fixture`
requires no external credentials at all and is what CI always runs.

## Local setup — enabling live mode

1. Obtain a CDSE Sentinel Hub OAuth client (client ID + secret) from your
   Copernicus Data Space Ecosystem account dashboard.
2. In your local, untracked `.env`: set `DATA_MODE=live`,
   `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET`. The endpoint URLs already have
   working defaults (see `docs/api.md`); override them only if Copernicus
   changes the path structure again.
3. Restart the backend process so the new `.env` is read.
4. Do **not** yet assume connectivity works — every live code path in this
   repository has only ever been exercised against mocked HTTP
   (`backend/tests/integration/`). The first real connectivity check is a
   separate, explicit, manual step:

   ```bash
   cd backend
   python scripts/live_smoke_test.py
   ```

   This script refuses to run unless `DATA_MODE=live` and both CDSE
   credentials are set, makes a small bounded number of requests (one
   OAuth token, one short Catalog search, one short Open-Meteo fetch),
   never prints a secret or token, and must be run by a human — it is
   never invoked by CI, Docker, or application code. See
   `docs/security.md` "Live-credential handling status".

## Docker

`docker-compose.yml` and per-service `Dockerfile`s exist (backend +
frontend) but have not been build-verified in this environment (no local
Docker available during initial scaffolding — see the original
implementation plan). Treat them as a starting point to validate, not as
confirmed-working, before relying on them.

## What this document does not cover

Production/public deployment topology, secrets management beyond a local
`.env`, horizontal scaling, and the Redis (or similar) swap for
`app/core/cache.py`'s in-memory cache are all out of scope until a real
authentication layer exists — see `docs/security.md`.
