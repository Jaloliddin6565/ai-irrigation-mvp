# Validation plan

This document tracks what has actually been verified end-to-end in this
MVP, at what level (automated vs. manual), and what remains open. It is a
running record, not a one-time sign-off — update it as later phases add
verification, rather than treating any single pass as final.

## Backend

- **Unit** (`backend/tests/unit/`): every `app/domain/` calculation
  (crop-stage, water balance, initialization, irrigation normalization,
  satellite adjustment, recommendation, confidence, geo/polygon math) —
  deterministic, no I/O, no randomness. See `docs/methodology.md`.
- **API** (`backend/tests/api/`): full CRUD + validation-error paths for
  farmers, fields, irrigation events, analyses, against a real (SQLite,
  per-test-isolated) database via `TestClient`.
- **Mocked integration** (`backend/tests/integration/`): CDSE OAuth/
  Catalog/Statistical API and Open-Meteo, entirely via `respx` — no real
  network call in CI, ever.
- **Live connectivity** (Phase 4.5): a single, narrowly-scoped, manually
  triggered operator check against real CDSE/Open-Meteo endpoints, using
  `backend/scripts/live_smoke_test.py` and a small Uzbekistan test
  polygon. Confirmed OAuth, token caching, Catalog acquisition search
  (real dates, real pagination), Statistical API parcel statistics (all
  six indices), and both Open-Meteo branches. This was **one** connectivity
  check against **one** field geometry — not systematic validation across
  varied geometries, cloud conditions, or seasons, and not a repeated or
  standing arrangement. See `docs/security.md` "Live-credential handling
  status" and `docs/methodology.md` "Known limitations".

## Frontend (Phase 5)

- **Unit/component** (`frontend/src/**/*.test.tsx`, Vitest + Testing
  Library): landing page copy and disclaimer presence, fixture/live mode
  badge rendering, farmer registration validation and duplicate-phone
  handling, farmer lookup-by-phone (found/not-found), dashboard empty
  state, field-form polygon-required validation, irrigation-form
  at-least-one-amount validation, analysis launch and its pending/disabled
  state, recommendation status + range rendering (and that
  `insufficient_data` never shows a numeric range), confidence rendering,
  warning rendering, satellite/weather/water-balance chart empty states
  and index switching, analysis history listing, and structured
  backend-error rendering (`ApiErrorPanel`). All of these run against a
  mocked `fetch` (`frontend/src/testUtils/fetchMock.ts`) — never a real
  backend or external service.
- **Security regression** (`frontend/src/noSecretsInFrontend.test.ts`):
  automated scan of every frontend source file for CDSE/Open-Meteo
  endpoints, CDSE credential env-var names, and `Authorization`-header
  literals — fails the build if any of these are ever introduced into
  frontend code, rather than relying on manual review alone.
- **Manual walkthrough** (fixture mode, this phase): register a farmer,
  add a field with a drawn polygon, log an irrigation event, run an
  analysis, and confirm the recommendation/confidence/data-source panel
  and all three chart types render with the deterministic fixture data —
  see `docs/architecture.md` "Frontend" for the page/route map. Repeated
  analysis requests against identical fixture input were confirmed to
  produce identical output (backend regression coverage), consistent with
  the fixture-mode determinism guarantee in `CLAUDE.md`.
- **Not yet done**: a live-mode frontend walkthrough against a real CDSE/
  Open-Meteo-backed backend (the backend side of that path was verified in
  Phase 4.5; the frontend has not yet been manually driven against a live
  backend); cross-browser/mobile-device manual testing; a full
  accessibility audit (automated checks and semantic-HTML/keyboard-focus
  review were done — see `docs/architecture.md`'s note on the polygon
  editor's Leaflet-driven, not fully keyboard-operable, drawing UI — but no
  screen-reader pass or WCAG contrast audit has been performed).

## What "validated" does not mean here

None of the above validates the underlying agronomic model against real
Uzbekistan field outcomes — see `docs/methodology.md` "Generic agronomic
defaults require Uzbekistan field validation". This document only tracks
software correctness (does the code do what it claims, deterministically,
safely) and connectivity, not agronomic accuracy.
