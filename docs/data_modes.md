# Data modes

`DATA_MODE` is the single switch that selects which provider
implementations the composition root wires up. Application code in
`app/domain/` and `app/api/` never branches on it directly.

## `fixture` (default)

- No external credentials required.
- `FixtureSatelliteProvider` / `FixtureWeatherProvider` read static JSON
  under `backend/fixtures/{satellite,weather}/sample_field.json` — a fixed
  historical demo season (2024-04-01 onward), not tied to the current date
  and not regenerated per request.
- Identical calls return byte-identical data, always (see
  `backend/tests/unit/test_fixture_providers.py`).
- The frontend shows a persistent `DataModeBadge` labelled
  "DEMO / NAMUNAVIY MA'LUMOT" whenever fixture data is in use — a fixture
  result must never be visually indistinguishable from a live one.
- Used for all local development and CI.

## `live`

- Requires real CDSE (`CDSE_CLIENT_ID`/`CDSE_CLIENT_SECRET`) and reaches
  Open-Meteo without a key.
- `Settings.require_live_satellite_credentials()` raises immediately if
  live mode is selected without CDSE credentials configured — this is a
  hard failure, not a fallback trigger.
- **Never silently falls back to fixture mode.** A failed or absent live
  provider surfaces as an explicit error (`insufficient_satellite_data`,
  `insufficient_data`, or a provider/config error) — never fixture data
  presented as if it were live.
- **Never fabricates replacement data.** If Sentinel-2 has no usable
  observation for the lookback window, or weather data is unavailable, the
  result says so rather than inventing a plausible-looking number.
- Not implemented yet — live providers land in Phase 4. Not exercised in
  CI under any circumstance.

## Why this split exists

The MVP's scientific credibility depends on never blurring "this is a
believable demo" with "this is what the satellite/weather actually said
about your field." Keeping the switch at the provider-selection layer,
with both fixture and live implementations validated against the same
Pydantic schemas (`app/providers/*/base.py`), makes that boundary
mechanical rather than a matter of remembering to check a flag everywhere.
