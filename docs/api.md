# API reference

Status: Phase 2 — farmer/field/irrigation CRUD. No `/analyze` endpoint yet
(Phase 3) and no authentication (see `docs/security.md`). Interactive docs
are always available at `/docs` (Swagger UI) and `/redoc` when the backend
is running.

Every error response uses the same structured shape:

```json
{
  "code": "field_not_found",
  "message_uz": "...",
  "message_en": "...",
  "details": null
}
```

`code` is a stable machine-readable identifier the frontend can switch on;
`message_uz` is always present, `message_en` may be null, `details` carries
extra structured context (e.g. Pydantic validation errors) when relevant.

## Health & config

```
GET /health
```
`{"status": "ok", "data_mode": "fixture"}` — always DB-free.

```
GET /api/config/options
```
Crop/soil/irrigation-method enums with Uzbek labels, read from
`backend/config/*.yaml`, plus `methodology_version`.

## Farmers

```
POST /api/farmers
```
Body: `full_name`, `phone` (E.164-ish, validated), `email?`, `region`,
`district`, `preferred_language?` (default `uz`). Returns `201` + the
created farmer. `409 farmer_phone_conflict` if the phone is already
registered.

```
GET /api/farmers/{farmer_id}
```
`200` + farmer, or `404 farmer_not_found`.

*(No farmer list/update/delete endpoint in this MVP — out of the approved
Phase 2 scope.)*

## Fields

```
POST /api/fields
```
Body: `farmer_id`, `name`, `geojson_polygon` (raw GeoJSON `Polygon`,
validated server-side — see below), `crop_type`, `crop_variety?`,
`planting_date`, `expected_harvest_date?`, `crop_stage_override?`,
`irrigation_method`, `soil_texture`, `root_depth_override?` (metres, 0–5),
`field_capacity_override?`/`wilting_point_override?` (volumetric fraction,
0–1, capacity must exceed wilting point if both given), `notes?`.

`area_hectares`, `centroid_latitude`, `centroid_longitude` are **always
server-computed** from the polygon — any client-supplied value for these is
ignored/absent from the request schema entirely. `404 farmer_not_found` if
`farmer_id` doesn't exist; `422 invalid_geometry` / `422 invalid_dates` /
`422 invalid_override_values` for the respective validation failures.

```
GET /api/fields?farmer_id=&limit=&offset=
```
`farmer_id` optional (omit for all fields); `limit` defaults to
`DEFAULT_LIST_LIMIT` (50), capped at `MAX_LIST_LIMIT` (200). Response:
`{"items": [...], "total": N, "limit": L, "offset": O}`.

```
GET /api/fields/{field_id}
PATCH /api/fields/{field_id}
DELETE /api/fields/{field_id}
```
`PATCH` accepts any subset of the `POST` fields (partial update); a new
`geojson_polygon` is re-validated and area/centroid recomputed. Cross-field
checks (harvest-after-planting, field-capacity-vs-wilting-point) are
re-evaluated against the **merged** state (existing + incoming), so a
one-field update can't silently create an inconsistent record. `DELETE`
returns `204` and cascades to the field's irrigation events and analyses.
All three return `404 field_not_found` if the id doesn't exist.

## Irrigation events

```
POST /api/fields/{field_id}/irrigations
```
Body: `occurred_at`, plus at least one of `duration_minutes`, `amount_mm`,
`total_volume_m3`, `flow_rate_m3_hour`, `qualitative_amount` — an event with
none of these is rejected as carrying no information. `value_source` is
required (`measured` or `farmer_estimate`). `occurred_at` may not be more
than a day in the future. `404 field_not_found` if the field doesn't exist.

```
GET /api/fields/{field_id}/irrigations?limit=&offset=
```
Same pagination shape as field listing; ordered by `occurred_at` descending.

## Geometry validation rules (`POST`/`PATCH` field polygon)

1. Must be a GeoJSON object with `"type": "Polygon"` — `Point`,
   `LineString`, `MultiPolygon`, etc. are rejected.
2. Every ring (exterior + any holes) must have at least 4 positions and be
   closed (first position equals last).
3. Every coordinate must be `[longitude, latitude]` with longitude in
   `[-180, 180]` and latitude in `[-90, 90]`.
4. Total vertex count is capped (`MAX_POLYGON_VERTICES`, default 1000).
5. The geometry must be valid per Shapely (`is_valid`) — this rejects
   self-intersecting (bowtie) polygons — and non-empty.
6. Area (via a WGS84 geodesic calculation, not planar) must be `> 0` and
   `<= MAX_FIELD_AREA_HECTARES` (default 500 ha).
7. Area and centroid are recomputed from the validated geometry — never
   trusted from the request. The stored `geojson_polygon` is the
   normalized version (coordinates rounded to 7 decimal places).

Any violation returns `422` with `code: "invalid_geometry"` and a
human-readable `message_en`/`message_uz` explaining which rule failed.
