# Methodology

Engine code version (`ANALYSIS_METHODOLOGY_VERSION`, `app/services/analysis.py`): `0.3.0`
Agronomic config version (`backend/config/*.yaml`): `0.2.0`

Status: Phase 4 complete. Every equation below is implemented as a pure,
deterministic function in `backend/app/domain/` and covered by unit tests
in `backend/tests/unit/`; nothing in this section changed in Phase 4. Live
Open-Meteo/CDSE Sentinel Hub providers now feed the same equations under
`DATA_MODE=live` — see "Weather gap handling" and "Satellite qualification"
below for what's different about live-sourced data, and `docs/api.md`/
`docs/architecture.md` for the provider implementation itself. Real live
connectivity has not been exercised yet (only respx-mocked HTTP).

These are two independent version numbers on purpose: the engine version
tracks the *calculation code*, the config version tracks the *agronomic
values* it's fed. Changing a Kc curve bumps the config version; changing
how depletion is clamped bumps the engine version.

## What this system estimates — and does not measure

This is a **decision-support estimate** built from remote/indirect data,
computed by a deterministic FAO-56-style calculation — **not a trained AI
model**. It does not directly measure root-zone soil moisture, soil pH,
electrical conductivity, organic matter, crop disease, or crop yield, and it
never reports a guaranteed water saving, yield increase, or an invented
accuracy percentage. Recommended irrigation amounts are always ranges (e.g.
20–26 mm), never single point values, and every result carries its
confidence category, data provenance, and known limitations alongside it.

## Units

| Quantity | Unit |
|---|---|
| Water depth (ETc, precipitation, irrigation, depletion, TAW, RAW) | millimetres (mm) |
| Root depth | metres (m) |
| field_capacity / wilting_point | volumetric fraction (m³/m³) |
| Area | hectares (ha) |
| Volume | cubic metres (m³) |
| Conversion | 1 mm over 1 ha = 10 m³ |

Internal calculations use plain IEEE double floats end to end, not
`Decimal`. Over a realistic ~90-day daily loop, accumulated floating-point
error is many orders of magnitude smaller than the agronomic uncertainty
already present in the inputs (Kc curves, soil parameters, etc. are
uncalibrated placeholders — see below), so `Decimal` would add complexity
without a real precision benefit. Rounding happens only at the API/response
boundary; the daily loop itself carries full precision.

## Crop-stage determination (`app/domain/crop_stage.py`)

Given `planting_date`, `analysis_date`, a crop profile, and an optional
`crop_stage_override`:

```
days_after_planting = analysis_date − planting_date
```

Stages, in order: `pre_planting` (analysis_date before planting) →
`initial` → `development` → `mid_season` → `late_season` → `post_season`
(beyond the crop's documented cycle length). Stage boundaries come from
`stage_lengths_days` (initial/development/mid/late, in days) in
`backend/config/crops.yaml`.

- **`pre_planting`**: Kc = 0 (no crop water use modelled pre-planting — a
  documented simplification; bare-soil evaporation isn't modelled), root
  depth = the crop's initial root depth. A warning is attached.
- **`initial`**: Kc = `kc.initial` (FAO-56 `Kc_ini`), constant. Root depth =
  `root_depth_initial_m`, constant.
- **`development`**: Kc interpolates linearly from `kc.initial` to
  `kc.mid`; root depth interpolates linearly from `root_depth_initial_m` to
  `root_depth_max_m` — both using the same day-within-stage fraction.
- **`mid_season`**: Kc = `kc.mid` (FAO-56 `Kc_mid`), constant. Root depth =
  `root_depth_max_m`.
- **`late_season`**: Kc interpolates linearly from `kc.mid` to `kc.end`
  (FAO-56 `Kc_end`). Root depth stays at `root_depth_max_m`.
- **`post_season`**: Kc holds at `kc.end`, root depth holds at
  `root_depth_max_m`. A warning is attached (the crop is past its
  documented cycle — this may mean the planting_date is stale, the crop
  was harvested, or the crop profile's stage lengths don't match reality).

`depletion_fraction` (FAO-56 "p") is a single crop-level constant from
`crops.yaml` — FAO-56 allows an ETc-rate adjustment to p which this MVP
does not implement (documented simplification).

**Stage override**: when `Field.crop_stage_override` is set, the
calendar-derived stage is replaced entirely by the override, and Kc/root
depth are computed at that stage's **midpoint** (fraction = 0.5 for
`development`/`late_season`) rather than from `days_after_planting` — the
day-level position within an overridden stage isn't knowable, so the
midpoint is a documented, defensible approximation.

## Daily root-zone water balance (`app/domain/water_balance.py`)

```
ETc                     = Kc × ET0
effective_precipitation = precipitation × effective_precipitation_factor
effective_irrigation    = irrigation_mm × irrigation_efficiency
TAW                     = 1000 × (field_capacity − wilting_point) × root_depth_m
RAW                     = depletion_fraction × TAW
depletion_today = clamp(
    depletion_previous + ETc − effective_precipitation − effective_irrigation,
    0, TAW,
)
```

Kc and root depth (and therefore TAW/RAW) are recomputed **per day** from
the crop-stage engine, unless `Field.root_depth_override` is set, in which
case root depth is held fixed at that value for every day regardless of
stage. When TAW grows because root depth grows, the newly available
root-zone layer is assumed to enter **at field capacity** — it does not
retroactively inflate yesterday's depletion. This is a documented,
conservative simplification.

`ET0`/`precipitation`/`irrigation_mm` are validated non-negative;
`field_capacity` must exceed `wilting_point`; `root_depth_m` must be
positive — violations raise immediately rather than producing a
nonsensical result.

**Missing weather days** are handled explicitly, not silently: a day with
no weather record is treated as zero ETc/zero effective precipitation (a
no-op for that day) and a warning is attached. This is conservative in the
sense of never fabricating a plausible-looking ET0/precipitation value, but
it can understate depletion if real ET0 that day was non-zero — this
trade-off is documented, not hidden.

### Weather gap handling in live mode (`OpenMeteoProvider`)

Fixture mode never has gaps (the cycling demo dataset always covers any
requested window). In live mode, `OpenMeteoProvider` can genuinely fail to
return a day — e.g. archive reanalysis for very recent dates isn't
processed yet, or Open-Meteo itself returns `null` for one variable on one
day. That day is simply **absent** from the series (never zero-filled) and
reported in `WeatherSeries.coverage.missing_dates` / `coverage_ratio` /
`completeness_status` (`complete`/`partial`/`insufficient`). The existing
water-balance no-op-day handling above applies unchanged; Phase 4 only adds
a warning surfaced on the `Analysis` record so a missing day is visible in
the API response, not just implicit in a lower `days_covered` count. A
*malformed* response (mismatched array lengths, missing `daily` block,
negative ET0/precipitation, unparseable dates) is a hard failure
(`provider_malformed_response`), not treated as a per-day gap — see
`docs/api.md`.

### Initialization (`app/domain/initialization.py`)

The water balance never starts from an unexplained arbitrary depletion. In
order of preference (config: `water_balance_defaults.yaml:initialization`):

1. **`recent_irrigation_known_amount`** — the most recent `IrrigationEvent`
   with a directly-stated `amount_mm` or `total_volume_m3` within
   `max_anchor_age_days` of `analysis_date`. Assumes the field was at
   **full allowable depletion (TAW)** — i.e. the worst case — immediately
   before that irrigation, applies the known effective amount, then rolls
   the daily water balance forward from that date through real weather (and
   any further recorded irrigation) to `analysis_date`. Assuming worst-case
   dryness before the one known data point is deliberately conservative and
   avoids inventing an unknowable prior depletion state.
2. **`recent_irrigation_duration_flow`** — same math as (1), but the depth
   is derived from `duration_minutes` × `flow_rate_m3_hour` rather than a
   directly stated amount (lower confidence — an assumed constant flow
   rate is a rougher estimate).
3. **`planting_date_assumption`** — if no usable recent irrigation exists
   but `planting_date` is within `max_anchor_age_days`, assume
   near-field-capacity (zero depletion) at planting (soil is typically
   prepared/irrigated before planting) and roll forward from there.
4. **`conservative_default`** — otherwise, initialize at
   `conservative_default_fraction_of_raw` of RAW, anchored at the
   *earliest date covered by the available weather history* (so there is
   at least some real data to roll forward through), with reduced
   confidence.
5. **`insufficient_data`** — none of the above apply (no irrigation record,
   no in-window planting date, no usable weather history at all). The
   engine returns this rather than guessing, and the overall recommendation
   status becomes `insufficient_data` too.

Every branch records its method, anchor date, starting depletion, an
uncertainty value (0.0 = well-grounded, 1.0 = maximally uncertain), and a
human-readable explanation — all surfaced in the API response's
`water_balance_summary.initialization`.

### Irrigation-event normalization (`app/domain/irrigation_normalization.py`)

Farmer-recorded irrigation is converted to an effective depth in mm, in
preference order (most to least directly measured):

```
1. amount_mm (stated directly)
2. total_volume_m3 / field_area_hectares / 10   (1 mm over 1 ha = 10 m3)
3. (flow_rate_m3_hour × duration_minutes/60) / field_area_hectares / 10
4. a configurable, conservative qualitative_amount estimate (mm) —
   'little'/'moderate'/'a_lot' — only when nothing quantitative exists
```

If more than one quantitative value is present and they disagree by more
than 25% (relative), a warning is attached and the most directly measured
value is used. A qualitative-only estimate is always flagged as a farmer
estimate (not a measurement) and pulls confidence down accordingly.

## Satellite qualification (`app/domain/satellite_adjustment.py`)

Satellite data **qualifies, never replaces**, the water balance, and never
converts a spectral index into an exact soil-moisture value. It requires
**at least 2** valid observations (fresh: within
`max_observation_age_days_for_trend`; high-quality: valid-pixel ratio ≥
`low_valid_pixel_ratio_threshold`) to do anything at all — a single
observation, however extreme, produces no adjustment.

Given two usable observations, the delta (latest − earliest) of NDMI, MSI,
and NDVI each "vote" drier/wetter/inconclusive (a delta below a small noise
floor doesn't count). An adjustment is only applied when **at least 2 of
the 3 indices agree** on a direction. Its magnitude scales with agreement
strength (2-of-3 vs 3-of-3) and is capped at
`trend_adjustment_cap_fraction_of_raw` (default 15%) of RAW. The signed
adjustment is added to (drier) or subtracted from (wetter) the
water-balance-computed depletion before the recommendation engine sees it,
and is always reported alongside its reasoning. Stale, low-quality, or
absent satellite data doesn't block the recommendation — it just lowers
confidence and is flagged (`data_quality`: `ok` / `stale` / `low_quality` /
`insufficient`).

### Live-mode satellite quality gate (`app/providers/satellite/quality.py`)

In live mode, an extra classification runs **before** the trend logic
above ever sees an observation: `usable` / `low_valid_pixel_ratio` /
`stale` / `cloud_contaminated` / `non_finite_values` /
`malformed_response` / `no_data` / `insufficient_observations`. Corrupt or
non-physical results (`non_finite_values`, `cloud_contaminated`,
`malformed_response`, `no_data`) never reach the trend logic at all — they
are provider-layer defects, not a legitimate "dry"/"wet" signal.
`stale`/`low_valid_pixel_ratio` observations **are** passed through,
because the trend logic above already has its own freshness/pixel-ratio
thresholds and is specifically designed to react to them (skip the
adjustment, lower confidence) rather than being filtered on the same two
dimensions twice with different numbers. Every acquisition the CDSE Catalog
API found but excluded (e.g. over the configured cloud-cover threshold) is
recorded with its rejection reason in `satellite_summary`/
`rejected_acquisitions`, never silently dropped. This never converts a
spectral index into an exact root-zone soil-moisture value, live or
fixture.

## Recommendation (`app/domain/recommendation.py`)

Status is driven by the (satellite-qualified) depletion as a fraction of
RAW, against configurable thresholds
(`recommendation_defaults.yaml:status_thresholds`):

```
depletion/RAW < monitor_ratio           -> no_irrigation_needed
depletion/RAW < irrigate_soon_ratio     -> monitor
depletion/RAW < irrigate_now_ratio      -> irrigate_soon
depletion/RAW >= irrigate_now_ratio     -> irrigate_now
```

If irrigation would otherwise be recommended (`irrigate_soon`/
`irrigate_now`) and forecast precipitation over the next
`forecast_rain.window_hours` meets `forecast_rain.delay_threshold_mm`, the
status becomes `delay_due_to_forecast_rain` instead — rain never delays a
result that wasn't going to recommend irrigation anyway.

The recommended **range** (never a single value) brackets the gross
application needed to replace the depletion, accounting for irrigation
efficiency (`depletion / efficiency` = gross mm to apply), scaled by
`recommended_range.min_replacement_fraction`/`max_replacement_fraction`,
widened further when confidence isn't `high`
(`uncertainty_range_padding_fraction`), then clamped to the crop's
practical application limits (`crops.yaml:practical_application_mm`) so the
system never recommends an agronomically silly depth. `1mm × 1ha = 10m³`
converts the mm range to m³/ha and total field volume
(`Field.area_hectares × m³/ha`).

## Confidence (`app/domain/confidence.py`)

A 0–1 score from a weighted sum of 11 independently-scored 0–1 factors
(`confidence_weights.yaml:weights`): field-data completeness, crop/soil
profile quality (`1 − uncertainty_factor`), planting-date availability,
last-irrigation availability, irrigation-amount quality, initialization
certainty, weather-data availability, satellite freshness, valid-pixel
ratio, and observation count — mapped to `high`/`medium`/`low` via
configurable thresholds. This is a **documented heuristic scoring
formula**, never described as a trained model's probability.

After the weighted sum, five **caps** (each only ever lowers the score,
never raises it) guarantee specific weak points can't be masked by
everything else looking good:

- irrigation amount unknown (no quantitative irrigation record found)
- soil texture unknown (`requires_field_survey`)
- initialization weak (`conservative_default`/`insufficient_data`, or high
  uncertainty)
- satellite stale, low-quality, or absent
- weather data materially missing (< 90% of the water-balance window covered)

## Initializing from a single known irrigation event: a known behaviour

Because tier 1/2 initialization assumes **full depletion (TAW) immediately
before** the one known irrigation event, a field with exactly one recorded
irrigation and no other history can readily come back `irrigate_now` a few
days later — this is the deliberately conservative worst-case assumption
described above, not a bug. It will look less aggressive as more irrigation
history accumulates for a field.

## Generic agronomic defaults require Uzbekistan field validation

Every Kc curve, root-depth range, depletion fraction, soil parameter,
irrigation efficiency, and confidence weight/cap in `backend/config/*.yaml`
is a generic FAO-56-style/textbook placeholder. None are calibrated for
Uzbekistan varieties, soils, climate, or on-farm practice. They must be
validated against local field trials before being relied on for real
irrigation decisions — this is stated in the YAML files themselves and
repeated here deliberately.

## Known limitations

- Live Sentinel-2/Open-Meteo connectivity has been verified against the
  real APIs (Phase 4.5, `backend/scripts/live_smoke_test.py`, small
  Uzbekistan test polygon): Open-Meteo forecast + archive, CDSE OAuth +
  token caching, Catalog acquisition search (real dates, real pagination
  cursor), and Statistical API parcel statistics (all six indices,
  physically plausible values) all confirmed working end to end. This was
  a single connectivity check against one small test field, not a
  systematic validation across varied geometries, cloud conditions, or
  seasons.
- The Statistical API evalscript required two corrections discovered only
  by testing live (see `app/providers/satellite/statistics.py` docstring):
  bands must be requested as plain DN (digital number) names, not
  per-band `{name, units}` objects, with reflectance computed in-script by
  dividing by the standard 10000 DN scale factor; the response *parsing*
  shape (`interval.from/to`, `outputs.<index>.bands.B0.stats.{...,
  percentiles}`) needed no correction — it matched what was already
  implemented.
- Bare-soil evaporation pre-planting isn't modelled (Kc = 0).
- A missing weather day is treated as a ETc/precipitation no-op, which can
  understate depletion across data gaps.
- `depletion_fraction` (p) doesn't vary with ETc rate as full FAO-56 allows.
- The satellite adjustment is a simple multi-index voting heuristic, not a
  calibrated moisture model — indices are never converted into an exact
  soil-moisture percentage.
- Confidence and recommendation thresholds are configured defaults, not
  derived from validated Uzbekistan outcome data.
