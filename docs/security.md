# Security

## No authentication in this MVP — read this first

This MVP has **no password, JWT, SMS OTP, PIN, or email verification**.
Registering a farmer creates a database record; the frontend selects and
remembers an active farmer ID client-side. API endpoints check that a
referenced `farmer_id`/`field_id` **exists** (404 if not) — they do not
check that the caller is entitled to act on it. `GET /api/fields?farmer_id=`
filters by farmer, but `GET`/`PATCH`/`DELETE /api/fields/{field_id}` operate
on any field id with no ownership check at all. `POST /api/fields/{field_id}/analyze`
and its `GET` counterparts follow the same pattern (existence-checked, not
ownership-checked). There is no credential check proving the caller
actually is that farmer.

This is a deliberate scope decision for local development and controlled
pilots. **It must not be exposed as a public-internet-facing service.** The
backend keeps identity (`Farmer`), ownership (`farmer_id` foreign keys),
and authorization (`app/api/deps.py::get_current_farmer_id`) architecturally
separate specifically so a real auth layer can be added later without a
rewrite — but that layer does not exist yet, and nothing in this MVP should
be read as a security control against an untrusted caller.

## Secrets

- Real credentials live only in a local, untracked `.env` file.
  `.env.example` lists variable names with no values.
- `.gitignore` excludes `.env`, `.venv/`, `node_modules/`, `*.db`, and
  other local/build artifacts.
- CDSE OAuth client credentials and bearer tokens are handled server-side
  only (Phase 4) — never returned in an API response, never sent to the
  frontend.
- Logging must redact `Authorization`/cookie headers
  (`app/core/logging.py::redact_headers`) before anything is ever logged.
- CI never references real provider credentials; it only runs
  `DATA_MODE=fixture` and mocked-provider tests.
- Secret scanning (`gitleaks`) runs on every push/PR via
  `.github/workflows/secret-scan.yml`.

## Network-facing defaults

- CORS allow-list is read from `CORS_ALLOWED_ORIGINS` (comma-separated),
  not `*`, and defaults to the local dev frontend origin only.
- All outbound HTTP calls to external providers (Phase 4) use explicit
  timeouts and a small bounded number of retries on transient failures
  only (timeouts, 429, 5xx) — never retried into different behavior, and
  never silently substituting fixture data for a failed live call.

## Input validation (see also `docs/validation.md` and `docs/api.md`)

- All request/response bodies are Pydantic v2 schemas.
- Field polygons are validated server-side (`app/domain/geo.py`):
  well-formed GeoJSON `Polygon` only, closed rings, coordinate range checks,
  no self-intersection (Shapely `is_valid`), vertex-count and area caps
  (`MAX_POLYGON_VERTICES`/`MAX_FIELD_AREA_HECTARES`) — before persistence or
  use in any calculation. Area/centroid are always server-recomputed, never
  accepted from the client.
- Structured error responses (`app/core/errors.py`) cover three cases
  uniformly: domain errors (`AppError` → its own status code, e.g. 404/409/
  422), request schema validation (`RequestValidationError` → 422), and any
  other unhandled exception (→ 500, logged server-side, no stack trace or
  internal detail in the response body).
- A unique-constraint violation (e.g. duplicate farmer phone) is caught at
  the service layer, the transaction is rolled back, and a `409` with a
  clear `code` is returned — the database session stays usable for
  subsequent requests rather than being left in a broken state.

## What's intentionally deferred

- Authentication/authorization beyond the no-op seam described above.
- Rate limiting / abuse protection on public endpoints.
- Any live-credential handling — not implemented until Phase 4, and never
  exercised in CI.
