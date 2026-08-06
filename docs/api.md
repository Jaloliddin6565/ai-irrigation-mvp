# API reference

Status: Phase 5 — farmer/field/irrigation CRUD, the full analysis
pipeline, live Open-Meteo/CDSE Sentinel Hub providers behind
`DATA_MODE=live`, and a complete frontend against this contract (no
authentication — see `docs/security.md`). Interactive docs are always
available at `/docs` (Swagger UI) and `/redoc` when the backend is
running.

## CDSE endpoint verification

CDSE (Copernicus Data Space Ecosystem) Sentinel Hub endpoint paths were
verified against official Copernicus documentation on **2026-08-04**:

- OAuth token: `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`
- Sentinel Hub base: `https://sh.dataspace.copernicus.eu`
- Catalog API: `https://sh.dataspace.copernicus.eu/catalog/v1/search`
- Statistical API: `https://sh.dataspace.copernicus.eu/statistics/v1`
- Process API: `https://sh.dataspace.copernicus.eu/process/v1`

Copernicus announced a path-format migration effective 2026-03-17: both the
legacy format (`/api/v1/<service>`) and the new format (`/<service>/v1`,
used above) work with no breaking change during the rollout. Every one of
these URLs is a `Settings` field (`CDSE_TOKEN_URL`, `CDSE_CATALOG_URL`,
`CDSE_STATISTICS_URL`, `CDSE_PROCESS_URL`) — a future path change is a
config edit, not a code change. This list was re-verified live once during
the Phase 4.5 connectivity check (`backend/scripts/live_smoke_test.py` and
direct provider calls) — see `docs/security.md` "Live-credential handling
status" for what that check covered.

Open-Meteo requires no API key for non-commercial use;
`OPEN_METEO_ARCHIVE_URL`/`OPEN_METEO_FORECAST_URL` are likewise
`Settings` fields, verified against https://open-meteo.com/en/docs the same
date.

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

```
GET /api/farmers?phone=
```
Look up a farmer by their exact, already-validated phone number. `200` +
farmer, or `404 farmer_not_found` if no farmer has that phone number;
`422` if `phone` doesn't match the same pattern `POST /api/farmers`
validates. Added in Phase 5 so the frontend's trusted-MVP "select an
existing farmer" flow (`docs/architecture.md` "Frontend") has a lookup
mechanism — there is still no farmer *list* endpoint, and no update/delete
endpoint, both out of the approved MVP scope.

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
`analysis_date`. Provider selection is `DATA_MODE`-driven
(`app/providers/factory.py`): `fixture` uses the deterministic demo
providers described throughout this doc; `live` calls real Open-Meteo/CDSE
Sentinel Hub — see "Structured provider errors" below for how a live-mode
failure is reported. Live mode is never used in CI and has not yet been
exercised against real credentials (see `docs/data_modes.md`).

Response shape:

```json
{
  "id": 1, "field_id": 1, "requested_at": "...", "analysis_date": "2026-06-01",
  "data_mode": "fixture", "methodology_version": "0.3.0",
  "field_summary": { "...": "crop/soil/method/area snapshot at analysis time" },
  "crop_stage": { "days_after_planting": 61, "stage": "development", "kc": 0.75, "root_depth_m": 0.75, "depletion_fraction": 0.55, "stage_overridden": false, "assumptions": [], "warnings": [] },
  "weather_summary": { "data_mode": "fixture", "start_date": "...", "end_date": "...", "days_covered": 62, "days_missing": 0, "total_et0_mm": 232.1, "total_precipitation_mm": 14.0, "forecast_precipitation_mm": 0.0, "forecast_window_hours": 60, "provider": "fixture", "source": "DEMO / FIXTURE DATA", "retrieved_at": null, "cache_hit": false, "missing_dates": [], "coverage_ratio": 1.0, "completeness_status": "complete" },
  "satellite_summary": { "data_mode": "fixture", "observations_considered": 13, "valid_observations_used": 3, "latest_observation_date": "...", "latest_observation_age_days": 6, "latest_valid_pixel_ratio": 0.93, "data_quality": "ok", "adjustment_applied": true, "adjustment_mm": 4.2, "reasons": ["..."], "provider": "fixture", "source": "DEMO / FIXTURE DATA", "retrieved_at": null, "cache_hit": false, "rejected_acquisitions_count": 0 },
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
Direct provider access (the same `DATA_MODE`-selected provider the analyze
pipeline uses — see `app/providers/factory.py`), independent of any
persisted `Analysis` — useful for charting history without running a full
analysis. Both default their date range to the configured satellite
lookback window (+ the forecast window, for weather) ending today. The
satellite endpoint always queries the field's actual stored polygon (never
a centroid). Response fields `provider`/`source`/`retrieved_at`/
`cache_hit` identify where the data came from (`"fixture"`/
`"DEMO / FIXTURE DATA"` in fixture mode; `"open-meteo"`/`"cdse-sentinel-hub"`
and a real timestamp in live mode); `satellite-timeseries` also returns
`rejected_acquisitions` (date + reason, live mode only) and `weather`
returns `coverage` (requested/received range, missing dates, completeness
status). `404 field_not_found` if the field doesn't exist.

## Structured provider errors (live mode)

Every external-provider failure (`app/core/provider_errors.py`) is an
`AppError` subclass, so it returns the same `{code, message_uz, message_en,
details}` shape as any other domain error, with `details.provider` and
`details.retryable` — never a token, client secret, or raw upstream
response body:

| `code` | status | meaning |
|---|---|---|
| `provider_configuration_error` | 503 | `DATA_MODE=live` without `CDSE_CLIENT_ID`/`CDSE_CLIENT_SECRET` configured |
| `provider_authentication_error` | 502 | CDSE rejected the OAuth client credentials |
| `provider_rate_limited` | 503 | upstream returned 429 after retries exhausted |
| `provider_timeout` | 504 | upstream request timed out after retries |
| `provider_network_error` | 502 | connection-level failure after retries |
| `provider_server_error` | 502 | upstream 5xx after retries exhausted |
| `provider_malformed_response` | 502 | response failed structural/type validation |
| `unsupported_geometry` | 422 | polygon isn't a valid GeoJSON `Polygon` |
| `invalid_date_range` | 422 | `end_date` before `start_date` |

Outbound HTTP (`app/core/http_client.py`) retries only 429/500/502/503/504
and connection timeouts, with bounded exponential backoff — never other
4xx, and never unboundedly.

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
