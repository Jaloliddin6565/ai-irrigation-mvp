# Validation rules

Status: Phase 1 foundation document. The `Field`/`IrrigationEvent` models
and their API-boundary validation land in Phase 2; this records the rules
they must implement so the contract is decided ahead of the code.

## Configuration validation (implemented, Phase 1)

`backend/app/domain/config_loader.py` loads every file in `backend/config/`
into typed, frozen Pydantic v2 models at startup (`get_agronomic_config()`,
process-lifetime cached). A malformed or missing config file raises
immediately — the application fails to start rather than serving requests
against partially-loaded or guessed agronomic values. Covered by
`backend/tests/unit/test_config_loader.py`.

## Field polygon validation (planned, Phase 2)

Before persistence or use in any calculation, a submitted GeoJSON `Polygon`
must:

- Be well-formed GeoJSON (correct type, closed linear ring(s)).
- Pass a geometric validity check (no self-intersection) via Shapely
  `is_valid`.
- Stay within a configured maximum vertex count.
- Stay within a configured maximum area — rejecting implausibly large
  polygons rather than silently accepting them.
- Use WGS84 coordinates (EPSG:4326), consistent with GeoJSON's default CRS.

Area and centroid are computed server-side from the validated polygon using
`pyproj`'s geodesic calculation (`Geod.geometry_area_perimeter`) — never
trusted from the client, and correct independent of the SQLite/PostgreSQL
storage backend (see `docs/postgis_migration.md`).

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
