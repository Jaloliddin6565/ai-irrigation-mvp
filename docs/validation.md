# Validation rules

Status: Phase 4 complete. `Farmer`/`Field`/`IrrigationEvent` CRUD validation
(Phase 2), the analysis engine's input/calculation validation (Phase 3),
and live-provider response validation (Phase 4) are implemented and
tested; see `docs/api.md` for the endpoint-level contract and
`docs/methodology.md` for the calculations these rules feed.

(This file covers the same ground the plan referred to as
"docs/validation-plan.md" — kept as `docs/validation.md`, the file that
already existed, rather than creating a second, overlapping document.)

## Configuration validation (implemented, Phase 1)

`backend/app/domain/config_loader.py` loads every file in `backend/config/`
into typed, frozen Pydantic v2 models at startup (`get_agronomic_config()`,
process-lifetime cached). A malformed or missing config file raises
immediately — the application fails to start rather than serving requests
against partially-loaded or guessed agronomic values. Covered by
`backend/tests/unit/test_config_loader.py`.

## Field polygon validation (implemented — `app/domain/geo.py`)

Before persistence or use in any calculation, a submitted GeoJSON geometry
must (see `docs/api.md` for the full rule list and status codes):

- Be `"type": "Polygon"` — not `Point`, `LineString`, `MultiPolygon`, etc.
- Have every ring (exterior + holes) well-formed: at least 4 positions,
  closed (first == last position), each position a numeric
  `[longitude, latitude]` pair within range.
- Pass a geometric validity check (no self-intersection) via Shapely
  `is_valid`, and be non-empty.
- Stay within a configured maximum vertex count (`MAX_POLYGON_VERTICES`).
- Stay within a configured maximum area (`MAX_FIELD_AREA_HECTARES`) —
  rejecting implausibly large polygons rather than silently accepting them.
- Use WGS84 coordinates (EPSG:4326), consistent with GeoJSON's default CRS.

Area and centroid are computed server-side from the validated polygon using
`pyproj`'s geodesic calculation (`Geod.geometry_area_perimeter`) — never
trusted from the client, and correct independent of the SQLite/PostgreSQL
storage backend (see `docs/postgis_migration.md`). The stored geometry is
normalized (coordinates rounded to 7 decimal places) rather than the raw
client payload. Covered by `backend/tests/unit/test_geo_validation.py` and
the field-creation/-update tests in `backend/tests/api/`.

## Model-level validation (implemented — `app/db/models/`)

CHECK constraints enforce the same invariants at the database layer as a
defense-in-depth measure, independent of the application code above:
`area_hectares > 0`, centroid within valid lat/lon ranges,
`expected_harvest_date > planting_date`, override values within their
documented ranges (root depth, field capacity, wilting point), and
non-negative irrigation amounts/rates. `Farmer.phone` is unique. Covered by
`backend/tests/unit/test_models.py`.

## API-boundary validation (ongoing)

- Every request/response body is a Pydantic v2 schema; FastAPI rejects
  malformed input with a 422 before it reaches application code.
- Domain-level "can't proceed without fabricating data" outcomes
  (`insufficient_satellite_data`, `insufficient_data`) are distinct,
  documented response states — not exceptions disguised as validation
  errors, and not silently defaulted around.
- Structured error responses (`app/core/errors.py::ErrorResponse`) carry a
  stable `code`, an Uzbek message, an optional English message, and
  optional structured `details` — never a raw stack trace.

## Analysis engine validation (implemented — `app/domain/`)

- `compute_etc`/`compute_effective_precipitation`/`compute_effective_irrigation`
  reject negative ET0/precipitation/irrigation inputs immediately
  (`ValueError`) rather than silently clamping or ignoring them.
- `compute_taw` requires `field_capacity > wilting_point` and
  `root_depth_m > 0`; `compute_raw` requires `depletion_fraction` in
  `(0, 1]`. Malformed config or a bad override would fail loudly here
  rather than producing a nonsensical TAW/RAW.
- The satellite adjustment requires **at least 2** valid (fresh,
  high-quality) observations before doing anything; one observation,
  however extreme, never moves the estimate (`test_satellite_adjustment.py`).
- The recommendation engine requires `taw_mm > 0` and `raw_mm > 0` whenever
  a depletion value is present, and always returns a range
  (`recommended_max_mm > recommended_min_mm`) rather than a single value
  when irrigation is recommended.
- `determine_initialization` never fabricates a starting depletion: it
  either grounds it in a real anchor (irrigation event or planting date,
  rolled forward through real weather) or returns `insufficient_data`
  explicitly (`test_initialization.py`).
- A malformed `analysis_date` in `POST /analyze` (e.g. not a valid ISO
  date) is rejected with `422 validation_error` by the Pydantic request
  schema before any engine code runs.

## Live-provider response validation (implemented — `app/providers/weather/open_meteo.py`, `app/providers/satellite/{catalog,statistics}.py`)

- Open-Meteo: structural checks (a `daily` block exists, every requested
  variable's array length matches `time`), non-negative ET0/precipitation,
  parseable dates, duplicate-date detection (first occurrence kept, a
  warning logged), sorted output. Any structural failure raises
  `provider_malformed_response` rather than passing through partial data.
- CDSE Catalog: geometry validated (must be a well-formed `Polygon`) before
  submission; response must have a `features` array; malformed feature
  entries are skipped, not fatal; cloud-cover filtering records a reason
  per rejected acquisition rather than silently dropping it; pagination is
  bounded (`MAX_PAGES = 5`) so a misbehaving `next` link can't loop forever.
- CDSE Statistical API: per-interval, per-index — `sampleCount`/
  `noDataCount` must be non-negative integers with `sampleCount > 0`;
  percentile/mean/std values must be finite (`math.isnan`/`math.isinf`
  checked) or the whole interval is dropped, never partially reported.
- All three raise typed `app/core/provider_errors.py` exceptions (mapped to
  502/503/504/422 — see `docs/api.md` "Structured provider errors"), never
  a raw stack trace or a silently-degraded result.

## Determinism as a validation concern

Fixture-mode provider responses are validated the same way live responses
are (same Pydantic models in `app/providers/*/base.py`), so a fixture
payload that wouldn't pass real validation would be caught immediately.
Live-provider code paths are exercised only via respx-mocked HTTP
(`backend/tests/integration/`) — no test in this repository ever makes a
real external request; see `docs/security.md` "Live-credential handling
status" for what remains unverified until a separately-approved smoke test.
