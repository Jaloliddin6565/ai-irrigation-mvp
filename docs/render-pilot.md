# Render controlled-pilot deployment

This repository includes a root-level `render.yaml` Blueprint that creates:

- one Docker web service that serves both the React SPA and the FastAPI API;
- one Render Postgres database;
- live Open-Meteo and CDSE provider configuration;
- a shared HTTP Basic access gate for the controlled pilot.

The shared pilot gate is intentionally **not** farmer-level authentication.
It prevents casual public access to the pilot URL while the full identity,
ownership and authorization layer remains deferred. Do not remove it for a
public deployment.

## Deploy

1. In Render, create a new Blueprint and select this private GitHub repository.
2. Render reads `render.yaml` from `main` after the deployment pull request is
   merged.
3. Provide these four values when Render prompts for `sync: false` variables:
   - `PILOT_USERNAME` — a non-obvious shared pilot username;
   - `PILOT_PASSWORD` — a strong unique password;
   - `CDSE_CLIENT_ID` — the Copernicus OAuth client ID;
   - `CDSE_CLIENT_SECRET` — the Copernicus OAuth client secret.
4. Deploy the Blueprint.
5. Open the generated `onrender.com` URL. The browser should display an HTTP
   Basic login prompt before serving the application.

Never place any of those values in GitHub, `render.yaml`, screenshots, issue
comments, or frontend environment variables.

## Architecture

The production Docker image is multi-stage:

1. Node builds the Vite frontend with an empty `VITE_API_BASE_URL`, which makes
   browser API requests same-origin.
2. Python installs the FastAPI backend and PostgreSQL driver.
3. The frontend build is copied into the backend image.
4. FastAPI serves `/assets/*`, the SPA fallback, and the API from one origin.
5. Alembic migrations run before Uvicorn starts.

Render supplies the database URL through `fromDatabase`. The application
normalizes Render's `postgresql://` connection string to SQLAlchemy's
`postgresql+psycopg://` dialect.

## First validation

After deployment, verify:

1. `/health` returns HTTP 200 without credentials (Render health check).
2. Every other page requires the pilot username and password.
3. The UI shows `JONLI MA’LUMOT`.
4. Farmer, field, polygon and irrigation-event records persist after a service
   restart.
5. A minimal analysis returns real Open-Meteo data and an actual Sentinel-2
   acquisition date.
6. Browser developer tools show no CDSE credential or bearer token.
7. The service logs contain no secret values.

## Limitations

- The free Render web service may sleep when inactive and the first request can
  be slow.
- Free Postgres availability and retention are controlled by Render's current
  plan terms; upgrade before relying on the pilot for long-term records.
- The shared access gate is not per-farmer authentication. All trusted pilot
  users share the same gate and the application's existing trusted-MVP farmer
  selection remains unchanged.
- Do not advertise this as a production or public service until real
  authentication, authorization, rate limiting and operational monitoring are
  implemented.
