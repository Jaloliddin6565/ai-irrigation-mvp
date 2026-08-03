# AI Irrigation MVP

A sensor-free irrigation decision-support system for farmers in Uzbekistan.

The system combines Sentinel-2 satellite observations, historical/forecast
weather data, and farmer-provided field/crop/irrigation information through a
transparent, deterministic FAO-style daily water-balance model to produce
**explainable, range-based irrigation recommendations**.

## What this system is — and is not

This is a **decision-support estimate**, not a measurement device and not a
trained AI model.

- It does **not** directly measure root-zone soil moisture, soil pH,
  electrical conductivity, organic matter, crop disease, or crop yield.
- It does **not** guarantee water savings or yield increases.
- It does **not** report invented accuracy statistics.
- Every recommendation is a **range** (e.g. 20–26 mm / 200–260 m³/ha), labelled
  as an estimate, and comes with a confidence category, a breakdown of what
  drove that confidence, the data sources used, warnings, and known
  limitations.

> **Disclaimer (shown persistently in the app):**
> "Ushbu tavsiya masofaviy ma'lumotlar, ob-havo modeli va fermer kiritgan
> ma'lumotlar asosidagi taxminiy qaror ko'magidir. Tizim tuproq namligini
> bevosita o'lchamaydi va agronom yoki suv xo'jaligi mutaxassisi xulosasini
> to'liq almashtirmaydi."

See `docs/methodology.md` (added as the water-balance engine lands) for the
full calculation methodology and its version history.

## Current status

Farmer/Field/IrrigationEvent CRUD is implemented and tested (Phase 2), with
server-side GeoJSON polygon validation and area/centroid calculation — see
`docs/api.md`. The water-balance engine, recommendation engine, confidence
calculations, and live provider integrations are not implemented yet — see
the repository's implementation plan for the phased roadmap. `main` only
carries the secure foundation; all application work happens on feature
branches and lands via pull request.

## Security posture — read before running anywhere but your own machine

**This MVP has no authentication.** Registering a farmer creates a database
record; the frontend simply selects/remembers an active farmer ID in the
browser. There is no login, no password, and no per-user access control —
API endpoints check that a referenced farmer/field *exists*, not that the
caller is entitled to act on it. See `docs/security.md` for the exact scope.

This is intentional for local development and controlled pilots, and
**unsuitable for public/production deployment** until a real authentication
and authorization layer is added. The backend keeps identity (`Farmer`),
ownership (`farmer_id` foreign keys), and authorization (a single dependency
seam) separate specifically so that layer can be added later without a
rewrite — but it does not exist yet.

## Data modes

- `DATA_MODE=fixture` — deterministic static sample data, no external
  credentials required, visibly labelled as demo/fixture data in the UI.
  Identical inputs always produce identical outputs.
- `DATA_MODE=live` — real Sentinel Hub (Copernicus Data Space Ecosystem) and
  Open-Meteo calls. Fails clearly if credentials are missing; never silently
  falls back to fixture data, and never fabricates replacement values.

## Getting started (fixture mode)

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -e ".[dev]"
copy ..\.env.example ..\.env   # then edit if needed; DATA_MODE=fixture works with no further changes
alembic upgrade head           # creates the SQLite schema (farmers/fields/irrigation_events/analyses)
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Repository layout

```
backend/    FastAPI app, domain logic, providers, config (YAML), tests
frontend/   React + TypeScript + Vite SPA
docs/       Architecture, API reference, methodology, security, validation,
            data-mode contract, future PostGIS migration notes
```

See `CLAUDE.md` for conventions this repository expects an AI coding
assistant (or any contributor) to follow.

## Uzbek

See `README_UZ.md` for the Uzbek version of this document.
