# President Tech Award MVP — hybrid physics-guided AI irrigation decision support

This is a hybrid physics-guided AI decision-support MVP. It never claims to
measure soil moisture directly, and never claims guaranteed water savings or
yield increases (see `docs/security.md`, `docs/methodology.md`, and
`CLAUDE.md` for the hard constraints this whole codebase is built around).

## 1. Problem

Uzbekistan's irrigated agriculture is water-intensive and largely
sensor-free at the farm level. Farmers decide when and how much to irrigate
from experience and visual inspection, without systematic access to
satellite, weather, or modelled soil-water information. Deploying in-situ
soil-moisture sensors at scale is expensive and slow to roll out. A
decision-support tool that works today, without waiting for sensor
infrastructure, can still meaningfully improve irrigation timing.

## 2. MVP solution

A field-level irrigation decision-support system that combines:

- a deterministic FAO-56-style daily water-balance model (satellite- and
  weather-informed), which remains the sole authority over the recommended
  irrigation amount and timing; and
- an XGBoost **AI Soil Wetness Index** — a public-data pre-calibrated
  machine-learning signal that corroborates or flags disagreement with the
  water-balance estimate, explains itself in farmer-readable Uzbek, and
  never controls the recommended amount.

Both signals, their agreement, and full provenance are shown to the farmer
— never a single falsely-precise number, never an unexplained black box.

## 3. Architecture

```
Weather (Open-Meteo) + Satellite (Sentinel-2, CDSE) + Farmer/field data
                |                                  |
                v                                  v
      FAO-56 water balance                AI Soil Wetness Index
      (deterministic, authoritative)      (XGBoost, pre-calibrated)
                |                                  |
                +----------------+-----------------+
                                 |
                       AI-FAO agreement engine
                       (deterministic, read-only)
                                 |
                                 v
              Recommendation (FAO-56 only) + Confidence
              (small, capped AI-agreement adjustment)
                                 |
                                 v
                    Farmer-facing Uzbek result page
```

Backend: FastAPI + SQLAlchemy + Alembic, deployed as a single Docker image
that also serves the built React/TypeScript frontend (same-origin, no
separate frontend host). See `docs/architecture.md` for the full layering
and `docs/render-pilot.md` for the deployment shape.

## 4. Data sources

- **Satellite**: Copernicus Sentinel-2 (via CDSE Sentinel Hub) — NDVI,
  NDMI, NDRE, MSI, NDWI, NBR2, used only to adjust the water-balance trend,
  never converted into an absolute soil-moisture percentage.
- **Weather**: Open-Meteo (historical + forecast: ET0, precipitation,
  temperature, humidity, wind, radiation).
- **Field/agronomic data**: farmer-entered crop, planting date, soil
  texture, irrigation method and history.
- **Soil**: farmer-selected soil texture. ISRIC SoilGrids' public REST
  point-query was evaluated for Uzbekistan and returns `null` for every
  tested coordinate in-country (a confirmed regional coverage gap on that
  endpoint) — not integrated, and the UI never claims it is.

## 5. AI model

**AI Soil Wetness Index v0.1** — XGBoost regressor. Current AI is
pre-calibrated using public model/reanalysis data: same-day and
antecedent (3/7/14/30-day) weather features from Open-Meteo's ERA5-Land
reanalysis archive, 2023–2025, across 15 representative Uzbekistan
bootstrap locations. The target is a location-relative 0–1 wetness index
(each location's own observed min/max range), not an absolute volumetric
value — an absolute-moisture formulation was tried first and rejected for
poor held-out generalization (see `backend/scripts/train_ai_soil_moisture.py`).

## 6. FAO-56 role

The deterministic water balance (crop-stage Kc curve, TAW/RAW, daily
depletion accounting, satellite trend adjustment, forecast-rain delay) is
the sole source of `recommended_min_mm`/`recommended_max_mm`, the
irrigation window, and the depletion figures. This never changes based on
the AI signal — enforced in code and covered by a dedicated test
(`backend/tests/api/test_ai_summary_api.py`) that asserts these values are
byte-identical whether or not the AI signal is available.

## 7. AI role

The AI signal is corroborating evidence only:

- classified into dry/moderate/wet and compared against the water
  balance's own depletion-based dryness signal by a small deterministic
  agreement engine (agree / partial / disagree / unavailable);
- applies a small, capped adjustment to the displayed confidence score
  (an "agree" bonus can never by itself push confidence up to "high"; a
  "disagree" penalty can lower it further, uncapped);
- explained in plain Uzbek ("Nega?") using real antecedent-weather signals,
  never invented reasons;
- always degrades safely to "AI tahlili hozir mavjud emas" (AI unavailable)
  on any failure, with the FAO-56 recommendation unaffected.

## 8. Validation metrics

Held-out-location evaluation (4 locations never seen during training or
model selection, out of 15 total):

| Metric | Value |
|---|---|
| R² | 0.365 |
| RMSE | 0.191 |
| MAE | 0.153 |

This beats a global-mean baseline (R²=-0.148), ridge regression
(R²=0.097), and random forest (R²=0.211) evaluated the same way. It is
**not** yet validated against in-situ soil-moisture sensors — the weak
label itself is a public reanalysis model output, not ground truth.

## 9. Current limitations

- Generic FAO-56 agronomic constants (Kc curves, soil parameters,
  irrigation efficiencies) are placeholder values requiring Uzbekistan
  field validation — documented in every `backend/config/*.yaml` file.
- The AI Soil Wetness Index is a location-relative proxy trained on public
  reanalysis weak labels across 15 bootstrap locations and 2023–2025 only;
  not validated across other years, crop types, or irrigation practices.
- No in-situ soil-moisture or water-flow sensor data exists yet anywhere
  in the system.
- Soil texture is farmer-selected, not a measured or public-mapped value.
- No farmer-level authentication yet (by design — see `CLAUDE.md` rule 6).

## 10. Future sensor calibration

Hozirgi AI modeli ochiq ma'lumotlar asosida dastlabki kalibrlangan.
Keyingi pilot bosqichida tanlangan dalalarga tuproq namligi va suv sarfi
sensorlari o'rnatilib, model mahalliy real ma'lumotlar bilan qayta
o'qitiladi.

In English: future pilot will add soil-moisture sensors and water-flow
meters for Uzbekistan-specific recalibration — turning the current
public-data pre-calibration into a locally-validated model, and enabling
real accuracy claims that do not exist yet.

## 11. Commercial roadmap

1. **Sensor pilot**: install soil-moisture and water-flow sensors on a
   small number of partner fields across crop types/regions; collect
   in-situ ground truth.
2. **Local recalibration**: retrain the AI Soil Wetness Index (and
   evaluate reintroducing an absolute-moisture target) against real
   sensor data; publish real accuracy numbers, replacing the current
   weak-label metrics.
3. **Public soil integration**: revisit SoilGrids (or an alternative
   public soil source) once a working access method for Uzbekistan
   coverage is identified.
4. **Farmer authentication and multi-user accounts**: replace the
   trusted-MVP active-farmer selection with real identity/authorization.
5. **Scale-out**: broaden crop/region coverage, add satellite-derived
   crop-health signals beyond the current six indices, and evaluate
   controlled automation only after sensor-validated confidence is
   established — never before.
