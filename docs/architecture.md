# Architecture

Status: Phase 1 foundation. Domain models, the water-balance engine, and
live provider integrations land in later phases (see the repository's
implementation plan) — this document describes the shape already in place
and the shape being built toward.

## Monorepo layout

```
backend/    FastAPI app, domain logic, providers, YAML config, tests
frontend/   React + TypeScript + Vite SPA
docs/       This directory
```

## Backend layering

```
api/        Thin FastAPI routers: validate input, call domain/providers, shape output.
domain/     Pure business logic. No I/O, no framework imports, no randomness.
providers/  The only place external I/O happens (CDSE, Open-Meteo), behind
            SatelliteProvider / WeatherProvider interfaces with fixture and
            live implementations selected by DATA_MODE.
db/         SQLAlchemy 2.0 declarative models + session management.
config/     Agronomic YAML (crop Kc curves, soil parameters, irrigation
            efficiencies, confidence weights) — never hardcoded in Python.
```

This separation exists so the scientifically-sensitive calculation code
(`domain/`) can be unit-tested in complete isolation from HTTP, databases,
and external APIs, and so a live-vs-fixture switch never leaks into
business logic — only the composition root (`app/settings.py` +
`api/deps.py`) knows about `DATA_MODE`.

## Provider abstraction

```
SatelliteProvider (Protocol)         WeatherProvider (Protocol)
  ├── FixtureSatelliteProvider         ├── FixtureWeatherProvider
  └── CdseSentinelHubProvider (Phase4) └── OpenMeteoProvider (Phase 4)
```

Fixture implementations read static JSON under `backend/fixtures/` and are
used for all local development, CI, and demos. Live implementations call
real external services and are added in Phase 4 — see `docs/data_modes.md`.

## Determinism guarantee

Nothing under `app/domain/` or a `*fixture*` provider may depend on
`random`, `numpy.random`, non-fixed UUIDs, or wall-clock time as a
calculation input. Enforced by code review, a CI grep check
(`.github/workflows/backend-ci.yml`), and regression tests.

## Authentication seam (not implemented in this MVP)

This MVP intentionally ships with no authentication — see
`docs/security.md`. The backend still separates:

- **Identity** — the `Farmer` model (Phase 2).
- **Ownership** — `farmer_id` foreign keys on `Field`/`IrrigationEvent`.
- **Authorization** — `app/api/deps.py::get_current_farmer_id`, currently a
  no-op that trusts a client-supplied `farmer_id`.

so a real auth layer can be substituted into the one seam later without
restructuring the rest of the API.

## Database

SQLite for local development and CI; SQLAlchemy models are written to be
dialect-agnostic so the same models work unmodified against PostgreSQL.
Field geometry is stored as validated GeoJSON with area/centroid computed
in Python (geodesic, via `pyproj`) rather than relying on database-side
geometry functions — see `docs/postgis_migration.md` for the documented
future move to PostGIS.

## Frontend

React + TypeScript + Vite SPA. `react-i18next` with Uzbek as the only
complete locale; `ru`/`en` resource files exist with a handful of keys and
fall back to Uzbek for anything not yet translated (see
`frontend/src/i18n/`). TanStack Query is the server-state layer once pages
start calling the API (Phase 5). A `DataModeBadge` component makes the
active `DATA_MODE` visible on every screen so fixture/demo output is never
mistaken for a live result.
