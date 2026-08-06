#!/usr/bin/env python
"""Manual, low-volume live-connectivity smoke test for the Phase 4
providers (Open-Meteo, CDSE Sentinel Hub).

NOT part of any automated pipeline. It is never imported, scheduled, or
invoked by application code, CI, or Docker — running it is an explicit,
separate, human action, and it must only be run with real credentials the
operator has explicitly approved for connectivity testing (see CLAUDE.md
"Data modes" and docs/methodology.md "Future live smoke-test procedure").

Usage (from backend/, with a real .env containing live CDSE credentials):

    python scripts/live_smoke_test.py
    python scripts/live_smoke_test.py --with-statistics   # also calls the
                                                            # heavier Statistical API

Safety rules this script follows:
- Credentials are read only from Settings (i.e. the local, untracked
  .env) — never hardcoded, never accepted as a CLI argument (which would
  risk shell-history/process-list exposure).
- No access token, client secret, or Authorization header value is ever
  printed — only high-level pass/fail status and counts.
- Requests are minimal: one OAuth token fetch, one short Catalog search
  over a small fixed test polygon, one short Open-Meteo fetch, and
  (only with --with-statistics) exactly one Statistical API call over the
  same small polygon.
- Never runs automatically; must be invoked by a human from a terminal.
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta

# A small, fixed test polygon (~0.01 ha) near Tashkent — deliberately tiny
# so a Statistical API call (if requested) stays cheap.
_TEST_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [69.2400, 41.3000],
            [69.2405, 41.3000],
            [69.2405, 41.3005],
            [69.2400, 41.3005],
            [69.2400, 41.3000],
        ]
    ],
}
_TEST_LAT = 41.3000
_TEST_LON = 69.2400


def _redact(exc: Exception) -> str:
    """A safe, single-line description of an exception — never includes
    headers, tokens, or raw provider response bodies."""
    return f"{type(exc).__name__}: {getattr(exc, 'message_en', str(exc))}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-statistics",
        action="store_true",
        help="Also call the Statistical API once (heavier than Catalog-only).",
    )
    args = parser.parse_args()

    from app.settings import DataMode, get_settings

    settings = get_settings()

    if settings.data_mode != DataMode.LIVE:
        print("SKIPPED: DATA_MODE is not 'live' in your environment. Set DATA_MODE=live in a")
        print("local .env (never committed) before running this script.")
        return 1

    if not settings.cdse_client_id or not settings.cdse_client_secret:
        print("SKIPPED: CDSE_CLIENT_ID / CDSE_CLIENT_SECRET are not set. This script never")
        print("reads credentials from anywhere but your local .env, and never prints them.")
        return 1

    print("== AI Irrigation MVP — live connectivity smoke test ==")
    print("This makes a small number of real requests to Open-Meteo and CDSE.")
    print("No secret values will be printed below.\n")

    overall_ok = True

    # --- Open-Meteo: one day of weather at a fixed test coordinate ---
    print("[1/3] Open-Meteo weather fetch ...", end=" ")
    try:
        from app.providers.weather.open_meteo import OpenMeteoProvider

        provider = OpenMeteoProvider(
            forecast_url=settings.open_meteo_forecast_url,
            archive_url=settings.open_meteo_archive_url,
            timezone=settings.timezone,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
            retry_base_delay_seconds=settings.http_retry_base_delay_seconds,
            retry_max_delay_seconds=settings.http_retry_max_delay_seconds,
        )
        yesterday = date.today() - timedelta(days=1)
        series = provider.get_daily_series_for_range(
            _TEST_LAT, _TEST_LON, yesterday, yesterday, as_of=date.today()
        )
        print(f"OK ({len(series.days)} day(s) returned, provider={series.provider})")
    except Exception as exc:  # noqa: BLE001 - top-level smoke test, report and continue
        overall_ok = False
        print(f"FAILED ({_redact(exc)})")

    # --- CDSE OAuth: obtain one token, never print it ---
    print("[2/3] CDSE OAuth token fetch ...", end=" ")
    token_client = None
    try:
        from app.providers.satellite.cdse_auth import CdseTokenClient

        token_client = CdseTokenClient(
            client_id=settings.cdse_client_id,
            client_secret=settings.cdse_client_secret,
            token_url=settings.cdse_token_url,
            expiry_margin_seconds=settings.token_expiry_margin_seconds,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
            retry_base_delay_seconds=settings.http_retry_base_delay_seconds,
            retry_max_delay_seconds=settings.http_retry_max_delay_seconds,
        )
        asyncio.run(token_client.get_token())
        print("OK (token obtained, not displayed)")
    except Exception as exc:  # noqa: BLE001
        overall_ok = False
        print(f"FAILED ({_redact(exc)})")

    # --- CDSE Catalog: a short search over the small fixed test polygon ---
    if token_client is not None:
        print("[3/3] CDSE Catalog search ...", end=" ")
        try:
            from app.providers.satellite.catalog import CdseCatalogClient

            catalog_client = CdseCatalogClient(
                catalog_url=settings.cdse_catalog_url,
                token_client=token_client,
                timeout_seconds=settings.http_timeout_seconds,
                max_retries=settings.http_max_retries,
                retry_base_delay_seconds=settings.http_retry_base_delay_seconds,
                retry_max_delay_seconds=settings.http_retry_max_delay_seconds,
            )
            result = asyncio.run(
                catalog_client.search(
                    _TEST_POLYGON,
                    start_date=date.today() - timedelta(days=14),
                    end_date=date.today(),
                    max_cloud_cover_pct=settings.max_scene_cloud_cover,
                )
            )
            print(
                f"OK ({len(result.accepted)} acquisition(s) accepted, "
                f"{len(result.rejected)} rejected)"
            )

            if args.with_statistics and result.accepted:
                print("[extra] CDSE Statistical API call ...", end=" ")
                from app.providers.satellite.statistics import CdseStatisticsClient

                statistics_client = CdseStatisticsClient(
                    statistics_url=settings.cdse_statistics_url,
                    token_client=token_client,
                    timeout_seconds=settings.http_timeout_seconds,
                    max_retries=settings.http_max_retries,
                    retry_base_delay_seconds=settings.http_retry_base_delay_seconds,
                    retry_max_delay_seconds=settings.http_retry_max_delay_seconds,
                )
                stats = asyncio.run(
                    statistics_client.get_parcel_statistics(
                        _TEST_POLYGON,
                        start_date=date.today() - timedelta(days=14),
                        end_date=date.today(),
                    )
                )
                print(f"OK ({len(stats)} interval(s) with usable statistics)")
        except Exception as exc:  # noqa: BLE001
            overall_ok = False
            print(f"FAILED ({_redact(exc)})")
    else:
        print("[3/3] CDSE Catalog search ... SKIPPED (no token)")

    print()
    print("Result:", "ALL CHECKS PASSED" if overall_ok else "ONE OR MORE CHECKS FAILED")
    print("This script never verified image generation, pixel-level correctness, or")
    print("agronomic validity of returned values — see docs/methodology.md for what")
    print("still requires field validation in Uzbekistan.")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
