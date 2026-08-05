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

See `docs/methodology.md` for the full calculation methodology, units, and
version history.

## Current status

The full deterministic analysis pipeline is implemented and tested (Phase
3): crop-stage determination, daily water balance with an explicit
initialization strategy, conservative satellite qualification, and a
range-based irrigation recommendation with an explainable confidence
score — see `docs/methodology.md` and `docs/api.md`. Live Open-Meteo and
CDSE Sentinel Hub providers (Phase 4) are implemented behind the same
provider interfaces and covered by mocked tests; real connectivity was
verified once against live credentials in a single, narrowly-scoped
operator check (Phase 4.5 — see `docs/security.md` "Live-credential
handling status"), not repeated or continuous. The complete Uzbek-first
frontend workflow (Phase 5) — farmer registration/selection, field
creation with a Leaflet polygon editor, irrigation logging, analysis
launch, recommendation/confidence/data-source display, and satellite/
weather/water-balance charts — is implemented against this backend for
both `fixture` and `live` `DATA_MODE`; see "Frontend" below.
`DATA_MODE=fixture` remains the default and the only mode CI ever runs.
`main` only carries the secure foundation; all application work happens on
feature branches and lands via pull request.

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
  falls back to fixture data, and never fabricates replacement values. See
  `docs/deployment.md` for setup and `docs/data_modes.md` for the full
  contract.

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

Then open `http://localhost:5173`. With the backend running in
`DATA_MODE=fixture`, the golden path is: land on `/`, register a farmer
(`/farmers/new`) or select an existing one by phone (`/farmers/select`),
add a field with a drawn polygon (`/fields/new`), optionally log an
irrigation event, then run an analysis (`/fields/:fieldId/analysis`) to see
the recommendation, confidence, data-source panel, and charts. Every
fixture-mode screen is labelled `DEMO / NAMUNAVIY MA'LUMOT`.

## Frontend

React + TypeScript (strict) + Vite SPA, React Router, TanStack Query,
Leaflet + Leaflet-Geoman for the field polygon editor, Recharts for
satellite/weather/water-balance charts, React Hook Form + Zod for form
validation. Farmer identity in this MVP is the same trusted, no-auth model
described above: registering or looking a farmer up by phone stores their
id in `localStorage` client-side (see `frontend/src/features/farmer/`) —
this is a UX convenience, not a security boundary, and is documented as
such in `docs/security.md`. The frontend **never** calls Open-Meteo or
CDSE directly; every external-data request goes through this backend (see
`frontend/src/api/`, and the automated regression in
`frontend/src/noSecretsInFrontend.test.ts`). Frontend environment
variables (`VITE_API_BASE_URL`, `VITE_MAP_TILE_URL`,
`VITE_MAP_TILE_ATTRIBUTION`) hold no secrets — see `docs/deployment.md`.

```bash
cd frontend
npm run lint     # ESLint
npm run test      # Vitest + Testing Library, mocked backend only
npm run build     # tsc --noEmit + production build
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
