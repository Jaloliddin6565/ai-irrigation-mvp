# Validation rules

Status: Phase 2 complete. The `Farmer`/`Field`/`IrrigationEvent` models and
their API-boundary validation are implemented and tested; see `docs/api.md`
for the endpoint-level contract.

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

## Determinism as a validation concern

Fixture-mode provider responses are validated the same way live responses
will be (same Pydantic models in `app/providers/*/base.py`), so a fixture
payload that wouldn't pass real validation is caught immediately rather
than only surfacing once live mode is wired up in Phase 4.
