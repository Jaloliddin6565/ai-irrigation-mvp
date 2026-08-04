# Architecture

Status: Phase 4 complete. Farmer/Field/IrrigationEvent CRUD, GeoJSON polygon
validation, the full deterministic analysis pipeline (crop stage → water
balance → initialization → satellite qualification → recommendation →
confidence → persistence), and live Open-Meteo/CDSE Sentinel Hub providers
behind the same provider interfaces are implemented and tested — see
docs/methodology.md for the calculations and docs/api.md for the endpoint
contract. Real live connectivity has **not** been exercised yet (that is a
separately-approved smoke test, see `backend/scripts/live_smoke_test.py`);
everything here is verified against respx-mocked HTTP.

## Monorepo layout

```
backend/    FastAPI app, domain logic, providers, YAML config, tests
frontend/   React + TypeScript + Vite SPA
docs/       This directory
```

## Backend layering

```
api/          Thin FastAPI routers: parse/validate request, call a service, shape response.
services/     Business rules and orchestration: ownership checks (farmer/field
              existence), calls into domain/ for geometry validation, commits/
              rollbacks. Raises AppError for every domain-level failure.
repositories/ Plain CRUD against SQLAlchemy models. No validation, no business
              rules — just get/create/list/delete.
domain/       Pure business logic. No I/O, no framework imports, no randomness.
              geo.py validates/normalizes GeoJSON, computes area/centroid.
              crop_stage.py, water_balance.py, initialization.py,
              irrigation_normalization.py, satellite_adjustment.py,
              recommendation.py, confidence.py — the Phase 3 analysis
              engine, each independently unit-tested with no DB/HTTP
              dependency.
providers/    The only place external I/O happens (CDSE, Open-Meteo), behind
              SatelliteProvider / WeatherProvider interfaces with fixture and
              live implementations. factory.py is the single DATA_MODE-driven
              selection point application code must go through.
core/         http_client.py (bounded-retry async httpx wrapper),
              provider_errors.py (typed AppError subtypes for every external-
              provider failure mode), cache.py (in-memory TTL cache), plus
              the pre-existing errors.py/logging.py.
db/           SQLAlchemy 2.0 declarative models (models/farmer.py, field.py,
              irrigation_event.py, analysis.py) + session management.
schemas/      Pydantic v2 request/response DTOs — separate from the ORM models
              so the API contract and the storage schema can evolve independently.
config/       Agronomic YAML (crop Kc curves, soil parameters, irrigation
              efficiencies, confidence weights) — never hardcoded in Python.
```

This separation exists so the scientifically-sensitive calculation code
(`domain/`) can be unit-tested in complete isolation from HTTP, databases,
and external APIs, and so a live-vs-fixture switch never leaks into
business logic — only the composition root (`app/settings.py` +
`api/deps.py`) knows about `DATA_MODE`. The api → services → repositories
split keeps the same discipline for CRUD: routers never touch SQLAlchemy
directly, and validation (geometry, ownership, cross-field date/override
checks) always happens before any row is written, so a rejected request
never leaves partial state in the database.

## Provider abstraction

```
SatelliteProvider (Protocol)         WeatherProvider (Protocol)
  ├── FixtureSatelliteProvider         ├── FixtureWeatherProvider
  └── CdseSentinelHubProvider          └── OpenMeteoProvider
```

`app/providers/factory.py::get_weather_provider()`/`get_satellite_provider()`
are the **only** place `DATA_MODE` is read to pick a concrete provider class
— `app/services/analysis.py` and the `/satellite-timeseries`/`/weather`
endpoints call the factory, never a concrete provider class, so live mode
can never end up silently using fixture data by one call site forgetting to
check the mode.

Fixture implementations read static JSON under `backend/fixtures/` and are
used for all local development, CI, and demos. Each fixture provider has two
access patterns: the original Phase 1 `get_daily_series`/
`get_index_timeseries` (filters the static file by absolute calendar date —
only returns data if the request overlaps the file's own fixed 2024 demo
window) and a Phase 3 addition, `get_daily_series_for_range`/
`get_index_timeseries_for_range`, which *cycles* the same fixed, non-random
values to cover **any** requested date range. The analysis service uses the
latter exclusively. Still fully deterministic and still labelled
`DEMO / FIXTURE DATA`; only the calendar alignment is remapped. Live
providers implement the same two method names with real logic — no cycling,
no fabricated dates.

### Live weather — `OpenMeteoProvider` (`app/providers/weather/open_meteo.py`)

Splits a requested range at `as_of`: dates `<= as_of` come from the archive
API (`OPEN_METEO_ARCHIVE_URL`), dates `> as_of` from the forecast API
(`OPEN_METEO_FORECAST_URL`). A date Open-Meteo doesn't return (or returns as
`null`) is simply absent from `WeatherSeries.days` and reported in
`WeatherSeries.coverage` (`requested_start/end_date`, `received_start/
end_date`, `missing_dates`, `coverage_ratio`, `completeness_status`) — never
zero-filled. `precipitation_probability_pct` is `100.0` for archive
(already-observed) days, since forecast probability doesn't apply to the
past — a documented convention, not fabricated data.

### Live satellite — `CdseSentinelHubProvider` (`app/providers/satellite/cdse.py`)

Composes three pieces, each independently testable:

- **`cdse_auth.CdseTokenClient`** — OAuth client-credentials flow, in-memory
  token cache with an expiry margin, one automatic 401-triggered refresh+
  retry (never a loop). A single process-lifetime instance is shared across
  requests (`factory._cdse_token_client()`, `@lru_cache`) so tokens are
  genuinely reused, not re-fetched per analysis.
- **`catalog.CdseCatalogClient`** — Sentinel-2 L2A acquisition search (STAC
  Catalog API) against the field's **actual stored polygon** (never a
  centroid or bounding box), filtering by `MAX_SCENE_CLOUD_COVER` and
  recording *why* an acquisition was rejected rather than dropping it
  silently (`RejectedAcquisition`).
- **`statistics.CdseStatisticsClient`** — full-polygon Statistical API call
  computing NDVI/NDMI/NDRE/MSI/NDWI/NBR2 via a documented evalscript
  (`build_evalscript()`), masked by `dataMask` and the SCL exclusion list in
  `scl.py`. An interval with non-finite values, a zero sample count, or a
  malformed shape is dropped, never reported with an invented number.

`providers/satellite/quality.py` then classifies each parsed observation
(`usable`/`low_valid_pixel_ratio`/`stale`/`cloud_contaminated`/
`non_finite_values`/`malformed_response`/...) **before** it ever reaches
`app/domain/satellite_adjustment.py`. This is a provider-layer gate distinct
from — and upstream of — the existing Phase 3 domain-layer trend logic:
quality.py rejects corrupt/non-physical data outright; the domain layer's
own freshness/pixel-ratio thresholds still apply to what's left (an
observation tagged `stale`/`low_valid_pixel_ratio` is passed through to
`app/services/analysis.py`'s `sat_observation_inputs`, since the domain
layer already reacts to those two dimensions itself — see
docs/methodology.md).

### Shared HTTP/error/cache infrastructure

Both live providers build requests through `core/http_client.py`'s
`RetryingHttpClient` — bounded exponential-backoff retries only on
429/500/502/503/504/timeout/connection-error, never on other 4xx (those are
permanent from the caller's perspective) — and raise typed
`core/provider_errors.py` exceptions (all `AppError` subclasses, so they
flow through the existing structured-error response pipeline with no new
FastAPI wiring). Normalized responses are cached in `core/cache.py`'s
`TTLCache` (in-memory, process-local, deterministic — see the module
docstring for the documented future Redis-swap path), keyed on request
parameters only (coordinates/polygon/date-range), never on credentials.

## Analysis orchestration (`app/services/analysis.py`)

`analyze_field()` runs, per request: resolve crop/soil/irrigation-method
config profiles (with per-field overrides applied) → crop stage at
`analysis_date` → get providers from `providers/factory.py` (DATA_MODE-
driven) → fetch weather + satellite over the lookback window, using the
field's real polygon for satellite → determine initialization
(§ methodology) → run the daily water balance from the initialization
anchor to `analysis_date` → determine the satellite adjustment (only on
observations that passed the provider-layer quality gate) → compute
confidence → compute the recommendation → persist an `Analysis` row →
return the full structured response. Every calculation step is a call into
a `domain/` pure function; the service's job is data plumbing (DB reads,
provider calls, assembling inputs) plus provider selection, never
calculation logic itself.

If the live weather provider reports missing dates within the
water-balance window (`WeatherSeries.coverage.missing_dates`), a
human-readable warning is added to the persisted `Analysis.warnings` — the
underlying missing days are still handled the way Phase 3 always handled
them (an explicit no-op day in `water_balance.py`, never a fabricated
zero), this just makes the gap visible in the response too.

`Analysis`'s four JSON columns (from the Phase 2 schema) carry more than
their names suggest: `water_balance_summary` nests `input_summary` (a
field-data snapshot) and `crop_stage` alongside the water-balance figures
and daily rows, since the Phase 2-approved `Analysis` table has no
dedicated columns for those — see `docs/api.md` for how the API response
still exposes them as clean, separate top-level fields.

## Determinism guarantee

Nothing under `app/domain/` or a `*fixture*` provider may depend on
`random`, `numpy.random`, non-fixed UUIDs, or wall-clock time as a
calculation input. Enforced by code review, a CI grep check
(`.github/workflows/backend-ci.yml`), and regression tests.

## Authentication seam (not implemented in this MVP)

This MVP intentionally ships with no authentication — see
`docs/security.md`. The backend still separates:

- **Identity** — the `Farmer` model.
- **Ownership** — `farmer_id` foreign keys on `Field` (and transitively on
  `IrrigationEvent`/`Analysis` via `field_id`).
- **Authorization** — `app/api/deps.py::get_current_farmer_id`, currently a
  no-op that trusts a client-supplied `farmer_id`. Not yet wired into the
  Phase 2 field/irrigation routes (there is no per-request caller identity
  to check against) — existence checks (farmer/field must exist) are
  enforced, but not "does this caller own it."

so a real auth layer can be substituted into the one seam later without
restructuring the rest of the API.

## Database

SQLite for local development and CI; SQLAlchemy models are written to be
dialect-agnostic so the same models work unmodified against PostgreSQL —
enums use `native_enum=False` (portable VARCHAR+CHECK instead of a
PostgreSQL-only native ENUM type), and CHECK constraints use SQL that both
dialects understand identically. Field geometry is stored as validated
GeoJSON with area/centroid computed in Python (geodesic, via `pyproj`,
`app/domain/geo.py`) rather than relying on database-side geometry
functions — see `docs/postgis_migration.md` for the documented future move
to PostGIS. Migrations are managed with Alembic (`backend/alembic/`); the
initial migration creates all four tables (`farmers`, `fields`,
`irrigation_events`, `analyses`) with their indexes and CHECK constraints,
and is verified to upgrade/downgrade cleanly on an empty database.

## Frontend

React + TypeScript + Vite SPA. `react-i18next` with Uzbek as the only
complete locale; `ru`/`en` resource files exist with a handful of keys and
fall back to Uzbek for anything not yet translated (see
`frontend/src/i18n/`). TanStack Query is the server-state layer once pages
start calling the API (Phase 5). A `DataModeBadge` component makes the
active `DATA_MODE` visible on every screen so fixture/demo output is never
mistaken for a live result.
