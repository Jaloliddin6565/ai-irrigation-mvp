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
## Phase 6 (final audit)

- **Live-mode frontend walkthrough**: performed for the first time —
  backend switched to `DATA_MODE=live` against real CDSE/Open-Meteo
  credentials, driven from an actual Chrome browser (not just curl/pytest).
  Confirmed: the frontend detects live mode from the backend and shows
  "JONLI MA'LUMOT"; farmer/field creation and irrigation logging are
  unaffected by `DATA_MODE`; a real live analysis attempt surfaced two
  genuine backend bugs (both described below and in
  `docs/methodology.md` "Known limitations"), which were then either fixed
  and regression-tested, or documented as a scoped follow-up — this was
  the actual point of running the check live rather than only against
  mocks. Kept deliberately minimal (a handful of requests total, backend
  switched back to fixture mode immediately after) per the standing
  live-credential security rules — not a systematic live QA pass.
- **Confirmed and fixed, backend**: (1) CORS headers were missing on any
  truly unexpected (non-`AppError`) 500 response, because Starlette
  promotes an `@app.exception_handler(Exception)` registration to a
  middleware layer outside `CORSMiddleware` — the browser saw an opaque
  network failure instead of the real error. (2) `CdseTokenClient`'s
  `asyncio.Lock`, created once for a process-lifetime singleton client but
  awaited across many separate `asyncio.run()` calls (one per provider
  call), raised `RuntimeError: ... is bound to a different event loop` on
  the second live analysis in a running process — this is why a live
  analysis failed outright before the fix. Both are regression-tested
  (`backend/tests/api/test_error_handling.py`,
  `backend/tests/integration/test_cdse_auth.py`). See
  `docs/architecture.md` for the full explanation of each.
- **Confirmed and fixed, frontend**: `ApiErrorPanel` was discarding the
  backend's own specific, already-Uzbek `message_uz` (e.g. exactly which
  area limit a polygon exceeded) in favor of a generic static translation
  keyed only on the error code — found by deliberately drawing an
  oversized field polygon in the browser and reading the resulting error
  text. Fixed to always show the backend's message directly.
- **Confirmed, not fixed (documented as known limitations)**: the
  `reasons`/`warnings` text generated by several `app/domain/` modules is
  English (and partly raw internal factor names), inconsistent with every
  other Uzbek-localized label on the same screen; a real ~281 ha field with
  a ~90-day daily-aggregation lookback window hit a genuine CDSE
  Statistical API 400 that the Phase 4.5 small-polygon check never
  triggered (likely a request-complexity/processing-unit limit); the
  satellite-timeseries/weather chart endpoints reflect the *current* server
  `DATA_MODE`, not the specific analysis being viewed, which only surfaces
  when `DATA_MODE` changes on an already-running process (not normal
  operation). See `docs/methodology.md` "Known limitations" for detail on
  all three — none were fixed live, to keep external requests minimal.
- **Static Docker review** (Docker not installed in this environment,
  before or during this project): found and fixed three real defects
  purely by reading the Dockerfiles/compose file — the backend image never
  ran migrations, the frontend's nginx stage had no SPA fallback, and both
  still referenced a `VITE_DATA_MODE` build arg nothing has read since
  Phase 5. See `docs/deployment.md` "Docker". Still never build-verified
  end to end.
- **Accessibility**: chart components (satellite/weather/water-balance)
  gained an `aria-label` summary plus a same-page, non-hidden `<details>`
  data table as a real alternative to the visual SVG chart, not just a
  screen-reader-only echo. Form-field errors on the farmer registration
  page gained `aria-invalid`/`aria-describedby` wiring; the same pattern is
  not yet applied to the field, irrigation, or farmer-lookup forms — a
  scoped, mechanical follow-up. The polygon editor's Leaflet-driven, not
  fully keyboard-operable, drawing UI remains a known, documented library
  limitation (`docs/architecture.md`). No screen-reader pass or WCAG
  contrast audit has been performed.
- **Responsive/cross-browser**: the browser-automation tool's window-resize
  control did not actually change this session's viewport (confirmed via
  `window.innerWidth` before/after), so mobile/tablet breakpoints were
  verified by CSS code review only (existing `640px` breakpoint, `minmax()`
  grids, `.table-scroll`/`.chart-wrap` overflow containers), not by an
  actual narrow-viewport screenshot. Cross-browser (Firefox/Edge) was not
  verified — only Chromium, via the one available browser-automation tool.
- **Database**: Alembic upgrade *and* downgrade both verified clean on a
  fresh SQLite file (not just upgrade, as in earlier phases). Deleting a
  field with an attached irrigation event and analysis now has a dedicated
  regression test confirming both cascade-delete with no orphaned rows
  (`backend/tests/api/test_fields_api.py::test_delete_field_cascades_to_irrigation_events_and_analyses`).
- **Not yet done**: cross-browser (Firefox/Edge) and real mobile-device
  manual testing; a screen-reader pass; a WCAG contrast audit; root-causing
  the large-polygon Statistical API 400; localizing domain-layer
  `reasons`/`warnings` text; a real `docker compose up`.

## What "validated" does not mean here

None of the above validates the underlying agronomic model against real
Uzbekistan field outcomes — see `docs/methodology.md` "Generic agronomic
defaults require Uzbekistan field validation". This document only tracks
software correctness (does the code do what it claims, deterministically,
safely) and connectivity, not agronomic accuracy.
