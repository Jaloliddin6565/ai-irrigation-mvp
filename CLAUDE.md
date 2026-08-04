# CLAUDE.md

Conventions and hard constraints for anyone (human or AI) working in this
repository. See the repository's implementation plan for full architecture
and phased roadmap context.

## Non-negotiable rules

1. **No random values in production analysis code.** Nothing under
   `backend/app/domain/` or a `*fixture*` provider may use `random`,
   `numpy.random`, non-deterministic UUIDs, or wall-clock time as an input to
   a calculation. Fixture mode must produce byte-identical output for
   identical input, every time.
2. **Agronomic constants live in YAML** (`backend/config/*.yaml`), never
   hardcoded in Python. Every value in those files is a generic FAO-56-style
   placeholder that explicitly requires local Uzbekistan field validation —
   say so in comments, don't present them as calibrated.
3. **Never claim direct measurement or guarantees.** No feature may claim to
   directly determine exact soil moisture, soil pH, EC, organic matter, crop
   disease, or crop yield; no feature may claim guaranteed water savings or
   yield increases; no invented accuracy statistics (e.g. "92% AI accuracy").
   The water-balance calculation is a deterministic model, never described as
   a "trained AI model." All irrigation amounts are ranges, not point values.
4. **Every `Analysis` result carries its provenance and limitations**:
   analysis date, latest usable satellite acquisition date and its age,
   valid-pixel ratio / cloud percentage, weather summary, farmer-input
   summary, calculation explanation, confidence category + breakdown,
   warnings, limitations, and `methodology_version`.
5. **Live mode never silently falls back to fixture mode**, and never
   fabricates replacement data when a provider has nothing usable. Missing
   satellite data returns `insufficient_satellite_data`; missing water-balance
   inputs return `insufficient_data`. These are real, expected outcomes, not
   bugs to be papered over.
6. **No authentication in this MVP — by design, not by oversight.** There is
   no password/JWT/SMS/PIN layer. Identity (`Farmer`), ownership (`farmer_id`
   foreign keys), and authorization (the `api/deps.py` seam) are kept
   architecturally separate so a real auth layer can be added later without
   restructuring. Do not casually bolt on partial auth (e.g. a password field
   with no login flow) — either implement the full layer in a dedicated phase
   or leave the seam as a clean no-op.
7. **Secrets never enter the frontend or logs.** CDSE bearer tokens and
   client secrets are server-side only. Logging middleware must redact
   `Authorization` headers. Real credentials only ever live in a local
   untracked `.env` — `.env.example` holds names only.

## Git workflow

- `main` carries only the secure foundation commit(s) approved by the human
  operator. All application work happens on feature branches.
- Small, meaningful commits. No `--no-verify`, no `--no-gpg-sign`, no force
  push, ever, unless explicitly instructed in the moment.
- Do not push directly to `main` after the initial foundation commit — open a
  pull request and wait for human review/merge.

## Data modes

- `DATA_MODE=fixture`: default for all local development and CI. Reads static
  fixtures under `backend/fixtures/`. UI must visibly label results as
  demo/fixture data.
- `DATA_MODE=live`: real Sentinel Hub (CDSE) + Open-Meteo calls. Requires real
  credentials via `.env`; fails with a clear configuration error if absent.
  Never used in CI.

## Where things go

- `backend/app/domain/` — pure business logic (crop_stage, water_balance,
  initialization, irrigation_normalization, satellite_adjustment,
  recommendation, confidence, geo/polygon math). No I/O, no framework
  imports, fully unit-testable, no randomness. Two independent version
  numbers exist on purpose: `ANALYSIS_METHODOLOGY_VERSION`
  (`app/services/analysis.py`) versions this *calculation code*; each YAML
  file's own `methodology_version` versions the *agronomic values* fed
  into it. Don't conflate them when bumping one or the other.
- `backend/app/providers/` — the only place external I/O (CDSE, Open-Meteo)
  happens, behind `SatelliteProvider`/`WeatherProvider` interfaces with
  fixture (`*/fixture.py`) and live (`weather/open_meteo.py`,
  `satellite/{cdse.py,cdse_auth.py,catalog.py,statistics.py,quality.py,
  scl.py}`) implementations. `providers/factory.py` is the **only** place
  `DATA_MODE` selects a concrete provider class — application code (incl.
  `app/services/analysis.py`) calls the factory, never a concrete provider
  class directly.
- `backend/app/core/` — cross-cutting infrastructure with no business logic:
  `http_client.py` (bounded-retry async HTTP client shared by live
  providers), `provider_errors.py` (typed `AppError` subclasses for every
  external-provider failure mode), `cache.py` (in-memory TTL cache for
  normalized provider responses), plus `errors.py`/`logging.py`.
- `backend/app/api/` — thin FastAPI routers: validate input, call domain/
  providers, shape output. No business logic here.
- `backend/config/*.yaml` — all agronomic configuration (crop Kc curves, soil
  parameters, irrigation efficiencies, confidence weights).
- `backend/scripts/live_smoke_test.py` — the **only** sanctioned way to make
  a real live-credential request. Never invoked automatically by anything
  (not CI, not application code) — see rule 7 and `docs/deployment.md`.

## Persistent in-app disclaimer

Every analysis-facing screen must display (Uzbek, MVP default):

> "Ushbu tavsiya masofaviy ma'lumotlar, ob-havo modeli va fermer kiritgan
> ma'lumotlar asosidagi taxminiy qaror ko'magidir. Tizim tuproq namligini
> bevosita o'lchamaydi va agronom yoki suv xo'jaligi mutaxassisi xulosasini
> to'liq almashtirmaydi."
