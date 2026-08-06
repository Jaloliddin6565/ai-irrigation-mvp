# Future PostgreSQL / PostGIS migration

Not needed for the MVP; documented now so the current SQLite-era decisions
don't quietly become a migration blocker later.

## Current state (SQLite, MVP)

- `Field.geojson_polygon` is stored as validated `Text`/`JSON`, WGS84
  coordinates, checked by application-level Shapely validation before
  write (see `docs/validation.md`).
- Area and centroid are computed in Python via `pyproj`'s geodesic
  calculation (`Geod.geometry_area_perimeter`), not by a database function —
  this makes the result correct and identical regardless of which database
  is behind `DATABASE_URL`.
- SQLAlchemy models avoid SQLite-only column types so the same model
  definitions apply unchanged against PostgreSQL.

## Planned future state (PostgreSQL + PostGIS)

- Swap the polygon column to `Geography(Polygon, 4326)` (via GeoAlchemy2 or
  equivalent), letting PostGIS store and index real geometry instead of
  JSON text.
- Server-side geometry queries (e.g. "fields within region X",
  `ST_Intersects`) become possible without loading/parsing GeoJSON in
  Python.
- `ST_Area(geography)` could replace the Python geodesic calculation for
  area — expected to agree closely with the `pyproj` result since both use
  a geodesic/ellipsoidal area calculation; a migration should include a
  reconciliation check comparing old Python-computed areas against
  `ST_Area` for existing rows before cutting over.
- Alembic migration: add the PostGIS extension, add the new geography
  column, backfill from the existing JSON column, validate agreement, then
  drop the JSON column (or keep both during a transition window).

## Why not now

PostGIS is not required for the MVP's functional or performance needs, and
skipping it avoids a heavier local dev/Docker setup. Keeping the area/geo
math in Python (rather than relying on SQLite spatial extensions, which are
inconsistent across platforms) is what makes this migration additive later
rather than a rewrite.
