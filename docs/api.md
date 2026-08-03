# API reference

Status: Phase 3 — farmer/field/irrigation CRUD plus the full analysis
pipeline (fixture data only; no authentication — see `docs/security.md`).
Interactive docs are always available at `/docs` (Swagger UI) and `/redoc`
when the backend is running.

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

## Analysis

```
POST /api/fields/{field_id}/analyze
```
Body: `analysis_date?` (defaults to today, Asia/Tashkent, if omitted).
Runs the full deterministic pipeline (crop stage → water balance →
initialization → satellite qualification → recommendation → confidence),
persists a new `Analysis` row (**never overwrites a previous one**), and
returns `201` with the full response (see below). `404 field_not_found` if
the field doesn't exist; `422 validation_error` for a malformed
`analysis_date`. `DATA_MODE=live` isn't wired up yet (Phase 4) — this
endpoint only ever uses fixture data in this MVP.

Response shape:

```json
{
  "id": 1, "field_id": 1, "requested_at": "...", "analysis_date": "2026-06-01",
  "data_mode": "fixture", "methodology_version": "0.3.0",
  "field_summary": { "...": "crop/soil/method/area snapshot at analysis time" },
  "crop_stage": { "days_after_planting": 61, "stage": "development", "kc": 0.75, "root_depth_m": 0.75, "depletion_fraction": 0.55, "stage_overridden": false, "assumptions": [], "warnings": [] },
  "weather_summary": { "data_mode": "fixture", "start_date": "...", "end_date": "...", "days_covered": 62, "days_missing": 0, "total_et0_mm": 232.1, "total_precipitation_mm": 14.0, "forecast_precipitation_mm": 0.0, "forecast_window_hours": 60 },
  "satellite_summary": { "data_mode": "fixture", "observations_considered": 13, "valid_observations_used": 3, "latest_observation_date": "...", "latest_observation_age_days": 6, "latest_valid_pixel_ratio": 0.93, "data_quality": "ok", "adjustment_applied": true, "adjustment_mm": 4.2, "reasons": ["..."] },
  "water_balance_summary": { "initialization": {"method": "recent_irrigation_known_amount", "start_date": "...", "starting_depletion_mm": 82.0, "uncertainty": 0.2, "warnings": []}, "taw_mm": 150.0, "raw_mm": 82.5, "depletion_before_satellite_adjustment_mm": 76.2, "satellite_adjustment_mm": 4.2, "depletion_mm": 80.4, "start_date": "...", "end_date": "2026-06-01", "daily_rows": [ "...one row per day, see docs/methodology.md" ] },
  "recommendation": { "status": "irrigate_now", "recommended_min_mm": 71.4, "recommended_max_mm": 90.0, "recommended_min_m3_per_ha": 714.0, "recommended_max_m3_per_ha": 900.0, "total_min_volume_m3": 664.0, "total_max_volume_m3": 837.1, "window_start_date": "2026-06-01", "window_end_date": "2026-06-02", "reasons": ["..."], "warnings": ["..."] },
  "confidence": { "score": 0.75, "category": "high", "factor_scores": {"...": "..."}, "weights": {"...": "..."}, "triggered_caps": [], "positive_factors": ["..."], "negative_factors": ["..."] },
  "warnings": ["...deduplicated, aggregated from every stage..."],
  "disclaimer_uz": "Ushbu tavsiya masofaviy ma'lumotlar..."
}
```

`recommendation.status` is one of `no_irrigation_needed`, `monitor`,
`irrigate_soon`, `irrigate_now`, `delay_due_to_forecast_rain`,
`insufficient_data`. When `insufficient_data`, the recommended range is
`0`/`0` and `water_balance_summary.depletion_mm` is `null` — this is a
legitimate, expected outcome (see docs/methodology.md), not an error.

```
GET /api/fields/{field_id}/analyses?limit=&offset=
```
Paginated history, newest first: `{"items": [{id, requested_at,
analysis_date, data_mode, status, confidence_category}], total, limit,
offset}`.

```
GET /api/fields/{field_id}/analyses/{analysis_id}
```
The full response shape above, reconstructed from the persisted record.
`404 analysis_not_found` if the id doesn't exist for that field.

```
GET /api/fields/{field_id}/satellite-timeseries?start_date=&end_date=
GET /api/fields/{field_id}/weather?start_date=&end_date=
```
Direct fixture-provider access (same data the analyze pipeline uses),
independent of any persisted `Analysis` — useful for charting history
without running a full analysis. Both default their date range to the
configured satellite lookback window (+ the forecast window, for weather)
ending today, and both are explicitly `"data_mode": "fixture"` in the
response. `404 field_not_found` if the field doesn't exist.

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
