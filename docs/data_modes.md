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
- `Settings.require_live_satellite_credentials()` (wrapped by
  `providers/factory.py` into a structured `provider_configuration_error`,
  HTTP 503) raises immediately if live mode is selected without CDSE
  credentials configured — this is a hard, clearly-reported failure, not a
  fallback trigger.
- **Never silently falls back to fixture mode.** `app/providers/factory.py`
  is the only place `DATA_MODE` selects a concrete provider class; a failed
  or absent live provider surfaces as an explicit, typed error (see
  `docs/api.md` "Structured provider errors") — never fixture data
  presented as if it were live.
- **Never fabricates replacement data.** If the CDSE Catalog API has no
  usable acquisition for the lookback window, `CdseSentinelHubProvider`
  returns an empty observation list (never a synthesized one). If
  Open-Meteo can't return a day, that day is absent from `WeatherSeries`
  and reported in `coverage.missing_dates`, never zero-filled.
- Implemented and covered by respx-mocked tests
  (`backend/tests/integration/test_live_mode_analysis.py` and the
  provider-level test files alongside it). Real live connectivity has not
  been exercised — see `backend/scripts/live_smoke_test.py`, which requires
  a separate, explicit, manually-run approval step. Never exercised in CI
  under any circumstance.
- Provider responses are cached in-memory (`WEATHER_CACHE_TTL_SECONDS`/
  `SATELLITE_CACHE_TTL_SECONDS`) and outbound HTTP uses bounded
  exponential-backoff retries only on transient failures (429/5xx/timeout/
  network) — see `docs/architecture.md` "Shared HTTP/error/cache
  infrastructure".

## Why this split exists

The MVP's scientific credibility depends on never blurring "this is a
believable demo" with "this is what the satellite/weather actually said
about your field." Keeping the switch at the provider-selection layer,
with both fixture and live implementations validated against the same
Pydantic schemas (`app/providers/*/base.py`), makes that boundary
mechanical rather than a matter of remembering to check a flag everywhere.
