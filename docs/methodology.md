# Methodology

`methodology_version: 0.1.0`

Status: Phase 1 foundation document, written ahead of the engine
implementation (Phase 3) so the configuration values already in
`backend/config/*.yaml` have documented meaning. Every equation below is
implemented as a pure function in `backend/app/domain/` once Phase 3 lands.

## What this system estimates — and does not measure

This is a **decision-support estimate** built from remote/indirect data. It
does not directly measure root-zone soil moisture, soil pH, electrical
conductivity, organic matter, crop disease, or crop yield, and it never
reports a guaranteed water saving, yield increase, or an invented accuracy
percentage. Recommended irrigation amounts are always ranges (e.g. 20–26 mm),
never single point values, and every result carries its confidence category,
data provenance, and known limitations alongside it.

## Daily crop water balance (FAO-56 style)

**Crop evapotranspiration:**

```
ETc = Kc(day_after_planting, crop_profile) × ET0
```

`Kc` is linearly interpolated between the crop's stage breakpoints
(initial → development → mid → late) defined per crop in
`backend/config/crops.yaml`. `ET0` (reference evapotranspiration) comes
from the weather provider (FAO-56 Penman-Monteith, as supplied by
Open-Meteo in live mode).

**Effective precipitation and irrigation:**

```
effective_precipitation = precipitation × effective_precipitation_factor
effective_irrigation     = irrigation_amount × irrigation_efficiency
```

`effective_precipitation_factor` is a single configurable value in
`backend/config/water_balance_defaults.yaml`. `irrigation_efficiency` is
keyed by irrigation method (drip/sprinkler/furrow/basin/unknown) in
`backend/config/irrigation_methods.yaml`.

**Total and readily available water:**

```
TAW = 1000 × (field_capacity − wilting_point) × root_depth_m
RAW = depletion_fraction × TAW
```

`field_capacity`, `wilting_point`, and `depletion_fraction` come from the
soil-texture profile (`backend/config/soils.yaml`); `root_depth_m` comes
from the crop profile and may vary by growth stage.

**Daily depletion update:**

```
depletion_today = clamp(
    depletion_previous + ETc − effective_precipitation − effective_irrigation,
    0,
    TAW,
)
```

### Initializing the water balance

The engine never starts from an unexplained arbitrary depletion value. In
order of preference (see `initial_depletion` in
`water_balance_defaults.yaml`):

1. A recent known `IrrigationEvent` within
   `recent_irrigation_lookback_days` of the analysis start — assume
   near-field-capacity (near-zero depletion) at that event's date.
2. If `planting_date` falls within the lookback window, assume
   near-field-capacity at planting.
3. Otherwise, initialize at `conservative_default_fraction_of_raw` of RAW —
   a deliberate middle-ground assumption.
4. If none of the above apply and weather/satellite history also can't
   bridge the gap, the engine returns `insufficient_data` rather than
   guessing further.

Whichever branch fires is recorded in the analysis result so "how reliable
is this" is answerable from the output itself.

### Satellite trend adjustment (qualifies, never replaces, the water balance)

Applied only when at least `min_valid_observations_for_trend` (default 2)
valid satellite observations exist. Considers the direction of NDMI, MSI,
and NDVI, the freshness of the latest observation, and its valid-pixel
ratio. The adjustment is capped at
`trend_adjustment_cap_fraction_of_raw` (default 15%) of RAW and is always
explained in the result's reasons/warnings. It nudges the water-balance
output; it never substitutes for it, and it never runs on fewer than the
configured minimum number of observations.

## Confidence

A 0–1 score from a weighted sum of independently-scored factors (farmer
input completeness, last-irrigation/amount availability, satellite
freshness and valid-pixel ratio, observation count, crop/soil profile
quality, weather data availability, water-balance initialization
certainty), mapped to `high` / `medium` / `low` via configurable
thresholds — see `backend/config/confidence_weights.yaml`. This is a
documented heuristic scoring formula, not a trained model's probability
output, and is described that way everywhere it's shown.

## A note on every value in `backend/config/*.yaml`

Kc curves, soil parameters, irrigation efficiencies, and confidence weights
are generic FAO-56-style/textbook placeholder values. They are **not**
calibrated for Uzbekistan varieties, soils, or practice, and must be
validated against local field trials before being relied on for real
irrigation decisions. This is stated in the YAML files themselves and
repeated here deliberately.
