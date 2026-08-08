# Award demo recipe

Three representative demo fields, verified end-to-end locally (fixture-mode
backend) before this document was written — each produces a successful
analysis with a primary FAO-56 recommendation and an available AI Soil
Wetness Index summary, no 500/502s. Coordinates are real Uzbekistan
agricultural locations; no fabricated sensor/soil-moisture data is used
anywhere — soil texture is farmer-selected, exactly as the running system
requires.

These are **not** pre-loaded into the production database. Demo/pilot
records should be created live during the demo (or ahead of time by the
presenter) through the running app, not committed as fixtures — see
`docs/render-pilot.md` for why persistent pilot records are otherwise
unmanaged. This file is the reproducible recipe for creating them.

## Field 1 — Cotton (Tashkent region, Chinoz)

| Field | Value |
|---|---|
| Name | Chinoz paxta dalasi |
| Crop | `cotton` |
| Planting date | 2026-04-05 |
| Irrigation method | `drip` |
| Soil texture | `loam` |
| Centroid | 40.900 N, 69.200 E |
| Polygon | small square around the centroid, ~3.7 ha (see below) |

```json
{
  "type": "Polygon",
  "coordinates": [[[69.199, 40.899], [69.201, 40.899], [69.201, 40.901], [69.199, 40.901], [69.199, 40.899]]]
}
```

Verified: analysis on `2026-08-08` → `recommendation.status = irrigate_now`,
`ai_summary.status = available`.

## Field 2 — Wheat (Samarkand region, Kattaqo'rg'on)

| Field | Value |
|---|---|
| Name | Kattaqo'rg'on bug'doy dalasi |
| Crop | `wheat` |
| Planting date | 2025-10-15 (realistic autumn-sown winter wheat) |
| Irrigation method | `furrow` |
| Soil texture | `clay_loam` |
| Centroid | 39.900 N, 66.250 E |

```json
{
  "type": "Polygon",
  "coordinates": [[[66.249, 39.899], [66.251, 39.899], [66.251, 39.901], [66.249, 39.901], [66.249, 39.899]]]
}
```

Verified: analysis on `2026-04-01` → `recommendation.status = irrigate_now`,
`ai_summary.status = available`.

## Field 3 — Vegetables (Fergana Valley)

| Field | Value |
|---|---|
| Name | Farg'ona sabzavot dalasi |
| Crop | `vegetables` |
| Planting date | 2026-06-01 |
| Irrigation method | `sprinkler` |
| Soil texture | `sandy_loam` |
| Centroid | 40.380 N, 71.780 E |

```json
{
  "type": "Polygon",
  "coordinates": [[[71.779, 40.379], [71.781, 40.379], [71.781, 40.381], [71.779, 40.381], [71.779, 40.379]]]
}
```

Verified: analysis on `2026-08-08` → `recommendation.status = irrigate_now`,
`ai_summary.status = available`.

## How to create these live during a demo

1. Register (or select) a demo farmer via the UI (`Fermer sifatida ro'yxatdan
   o'tish`) — any name/phone, e.g. `+998911112222`.
2. For each field above: **Yangi dala qo'shish**, draw the ~3.7 ha square
   polygon around the given centroid (or paste the GeoJSON via the API
   directly — see below), fill in crop/planting date/irrigation/soil exactly
   as listed.
3. Record an irrigation event if you want a higher-confidence
   `recent_irrigation_known_amount` initialization (optional — all three
   fields above were verified without one, using the conservative-default
   initialization path).
4. Run **Tahlil qilish** for the analysis date noted above (or "today").

To create a field directly via the API instead of the map UI (useful for a
fast, reliable pre-demo setup), `POST /api/fields` with the JSON above plus
`farmer_id`/`irrigation_method`/`soil_texture`/`planting_date`, then
`POST /api/fields/{id}/analyze`.

## What to point out live

- The primary recommendation card (status, mm/m³ range, window) — unchanged,
  deterministic FAO-56 output.
- The **AI tahlili** card — wetness index, category, FAO/AI agreement badge,
  confidence, and the "AI modeli haqida" section with the honest R²/RMSE/MAE
  weak-label metrics.
- **Nega?** — the short plain-language synthesis.
- **Foydalanilgan ma'lumot manbalari** — Sentinel-2, Open-Meteo, FAO-56,
  XGBoost, farmer-provided field/soil data, all named explicitly.
- If running in `DATA_MODE=live` (the deployed pilot), the data-mode badge
  reads `JONLI MA'LUMOT` and satellite/weather provenance shows real
  Sentinel-2 acquisition dates and Open-Meteo retrieval times.
