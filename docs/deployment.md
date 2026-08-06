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

## Frontend quality checks

```bash
cd frontend
npm run lint       # ESLint
npm run test       # Vitest — mocked backend only, never a real network call
npm run build       # tsc --noEmit, then the production Vite build
```

`VITE_API_BASE_URL` is the only frontend variable that matters for local
dev (defaults to `http://localhost:8000` if unset); `VITE_MAP_TILE_URL`/
`VITE_MAP_TILE_ATTRIBUTION` only change the Leaflet basemap. None of the
three are secrets, and no `VITE_`-prefixed CDSE/credential variable exists
or should ever be added — see `docs/security.md`.

## Docker

`docker-compose.yml` and per-service `Dockerfile`s exist (backend +
frontend) but have never been build-verified end-to-end (no local Docker
available in this environment, either during initial scaffolding or the
Phase 6 audit — see `docs/validation-plan.md`). A Phase 6 static review
(read the Dockerfiles/compose file carefully; nothing was actually built or
run) found and fixed three real, confirmable-by-inspection defects the next
person to actually run `docker compose up` would otherwise have hit
immediately:

- The backend image never ran `alembic upgrade head` — a fresh container
  would boot against an empty SQLite file and every request would fail
  with `no such table: farmers` (the exact bug independently hit while
  starting a local dev server for this same audit). The image's `CMD` now
  runs the migration before starting uvicorn.
- The frontend's nginx stage shipped no `nginx.conf` at all, so nginx's
  default config has no SPA fallback — since the app uses React Router's
  `BrowserRouter`, any direct load or refresh on a route other than `/`
  (e.g. `/fields/1/analysis`) would 404. Added `frontend/nginx.conf` with
  `try_files $uri $uri/ /index.html;`.
- `docker-compose.yml` and `frontend/Dockerfile` still passed a
  `VITE_DATA_MODE` build arg — a leftover from before the frontend was
  built; nothing has read that variable since `DataModeBadge` was changed
  to always source its mode from the backend's own `/health` response (see
  `docs/architecture.md` "Frontend"). Removed.

None of this has been confirmed against a real `docker compose up` — treat
it as a corrected starting point, not confirmed-working, until someone with
Docker actually runs it.

## What this document does not cover

Production/public deployment topology, secrets management beyond a local
`.env`, horizontal scaling, and the Redis (or similar) swap for
`app/core/cache.py`'s in-memory cache are all out of scope until a real
authentication layer exists — see `docs/security.md`.
