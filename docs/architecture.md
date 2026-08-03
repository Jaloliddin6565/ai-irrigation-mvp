# Architecture

Status: Phase 3 complete. Farmer/Field/IrrigationEvent CRUD, GeoJSON polygon
validation, and the full deterministic analysis pipeline (crop stage →
water balance → initialization → satellite qualification → recommendation
→ confidence → persistence) are implemented and tested — see
docs/methodology.md for the calculations and docs/api.md for the endpoint
contract. Live provider integrations (real Sentinel-2/Open-Meteo) are
Phase 4 — this document describes the shape already in place and the shape
being built toward.

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
              live implementations selected by DATA_MODE.
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
  └── CdseSentinelHubProvider (Phase4) └── OpenMeteoProvider (Phase 4)
```

Fixture implementations read static JSON under `backend/fixtures/` and are
used for all local development, CI, and demos. Live implementations call
real external services and are added in Phase 4 — see `docs/data_modes.md`.

Each fixture provider has two access patterns: the original Phase 1
`get_daily_series`/`get_index_timeseries` (filters the static file by
absolute calendar date — only returns data if the request overlaps the
file's own fixed 2024 demo window) and a Phase 3 addition,
`get_daily_series_for_range`/`get_index_timeseries_for_range`, which
*cycles* the same fixed, non-random values to cover **any** requested date
range. The analysis service uses the latter exclusively, since a real
`Field.planting_date`/analysis date will essentially never fall inside a
hardcoded 2024 window — this is what makes fixture mode usable for
analyses run "today" rather than only on one canned historical date.
Still fully deterministic (same request → same output) and still labelled
`DEMO / FIXTURE DATA`; only the calendar alignment is remapped.

## Analysis orchestration (`app/services/analysis.py`)

`analyze_field()` runs, per request: resolve crop/soil/irrigation-method
config profiles (with per-field overrides applied) → crop stage at
`analysis_date` → fetch fixture weather + satellite over the lookback
window → determine initialization (§ methodology) → run the daily water
balance from the initialization anchor to `analysis_date` → determine the
satellite adjustment → compute confidence → compute the recommendation →
persist an `Analysis` row → return the full structured response. Every
step is a call into a `domain/` pure function; the service's job is purely
data plumbing (DB reads, provider calls, assembling inputs), never
calculation logic itself.

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
