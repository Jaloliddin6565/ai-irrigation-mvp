"""Public-data collection for AI Soil Moisture Proxy training.

Fetches Open-Meteo Archive API daily + hourly data per bootstrap location
(app/ai/locations.py) and parses it into a chronological, per-location list
of `RawDailyRecord`s: same-day weather plus the depth-weighted root-zone
soil-moisture weak label (see app/ai/features.py
`aggregate_root_zone_soil_moisture`).

This module makes real network calls (`fetch_location`) but caches each
location's raw JSON response to disk (`backend/.ai_dataset_cache/`, never
committed — see .gitignore) so repeated experimentation (feature
engineering, model comparison) does not repeat the same Open-Meteo request.
Delete that directory to force a refetch.

No randomness, no fabricated values: a location/day that Open-Meteo cannot
supply is simply absent from the returned series (see `_parse_daily`).
"""

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from app.ai.features import (
    RawDailyRecord,
    aggregate_hourly_to_daily,
    aggregate_root_zone_soil_moisture,
)
from app.ai.locations import BootstrapLocation
from app.core.http_client import RetryingHttpClient

PROVIDER_NAME = "open-meteo-ai-bootstrap"

_DAILY_VARS = [
    "et0_fao_evapotranspiration",
    "precipitation_sum",
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
    "shortwave_radiation_sum",
]
_HOURLY_VARS = ["soil_moisture_7_to_28cm", "soil_moisture_28_to_100cm"]


class CollectionFailure(Exception):
    def __init__(self, location_id: str, reason: str) -> None:
        self.location_id = location_id
        self.reason = reason
        super().__init__(f"Failed to collect data for location '{location_id}': {reason}")


def _cache_path(cache_dir: Path, location: BootstrapLocation, start: date, end: date) -> Path:
    key = f"{location.id}_{start.isoformat()}_{end.isoformat()}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{location.id}_{digest}.json"


async def _fetch_raw(
    client: RetryingHttpClient,
    archive_url: str,
    location: BootstrapLocation,
    start: date,
    end: date,
) -> dict:
    response = await client.request(
        "GET",
        archive_url,
        params={
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": ",".join(_DAILY_VARS),
            "hourly": ",".join(_HOURLY_VARS),
            "wind_speed_unit": "ms",
            "timezone": "Asia/Tashkent",
        },
    )
    if response.status_code != 200:
        raise CollectionFailure(location.id, f"HTTP {response.status_code}: {response.text[:500]}")
    try:
        return response.json()
    except ValueError as exc:
        raise CollectionFailure(location.id, f"non-JSON response: {exc}") from None


def _parse_daily(payload: dict, location: BootstrapLocation) -> dict[date, dict[str, float]]:
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise CollectionFailure(location.id, "response missing 'daily' block")

    dates_raw = daily.get("time") or []
    for key in _DAILY_VARS:
        series = daily.get(key)
        if not isinstance(series, list) or len(series) != len(dates_raw):
            raise CollectionFailure(location.id, f"daily['{key}'] length mismatch with 'time'")

    rows: dict[date, dict[str, float]] = {}
    for i, raw_date in enumerate(dates_raw):
        d = date.fromisoformat(raw_date)
        values: dict[str, float] = {}
        incomplete = False
        for key in _DAILY_VARS:
            raw_value = daily[key][i]
            if raw_value is None:
                incomplete = True
                break
            values[key] = float(raw_value)
        if not incomplete:
            rows[d] = values
    return rows


def _parse_hourly_layer(payload: dict, key: str, location: BootstrapLocation) -> dict[date, float]:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise CollectionFailure(location.id, "response missing 'hourly' block")
    times_raw = hourly.get("time") or []
    series = hourly.get(key)
    if not isinstance(series, list) or len(series) != len(times_raw):
        raise CollectionFailure(location.id, f"hourly['{key}'] length mismatch with 'time'")

    timestamps: list[datetime] = []
    values: list[float] = []
    for raw_time, raw_value in zip(times_raw, series, strict=True):
        if raw_value is None:
            continue
        timestamps.append(datetime.fromisoformat(raw_time))
        values.append(float(raw_value))
    return aggregate_hourly_to_daily(timestamps, values)


def _build_records(payload: dict, location: BootstrapLocation) -> list[RawDailyRecord]:
    daily_by_date = _parse_daily(payload, location)
    shallow_by_date = _parse_hourly_layer(payload, "soil_moisture_7_to_28cm", location)
    deep_by_date = _parse_hourly_layer(payload, "soil_moisture_28_to_100cm", location)

    records: list[RawDailyRecord] = []
    for d, daily_values in sorted(daily_by_date.items()):
        if d not in shallow_by_date or d not in deep_by_date:
            continue
        target = aggregate_root_zone_soil_moisture(
            soil_moisture_7_to_28cm_m3m3=shallow_by_date[d],
            soil_moisture_28_to_100cm_m3m3=deep_by_date[d],
        )
        records.append(
            RawDailyRecord(
                location_id=location.id,
                date=d,
                latitude=location.latitude,
                longitude=location.longitude,
                et0_mm=daily_values["et0_fao_evapotranspiration"],
                precipitation_mm=daily_values["precipitation_sum"],
                temperature_max_c=daily_values["temperature_2m_max"],
                temperature_min_c=daily_values["temperature_2m_min"],
                temperature_mean_c=daily_values["temperature_2m_mean"],
                relative_humidity_mean_pct=daily_values["relative_humidity_2m_mean"],
                wind_speed_ms=daily_values["wind_speed_10m_max"],
                shortwave_radiation_mj_m2=daily_values["shortwave_radiation_sum"],
                root_zone_soil_moisture_proxy_m3m3=target,
            )
        )
    return records


async def fetch_location(
    client: RetryingHttpClient,
    archive_url: str,
    location: BootstrapLocation,
    start: date,
    end: date,
    *,
    cache_dir: Path,
) -> list[RawDailyRecord]:
    """Return one location's daily records for [start, end], using a local
    JSON cache when present instead of re-fetching from Open-Meteo."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(cache_dir, location, start, end)

    if cache_file.exists():
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    else:
        payload = await _fetch_raw(client, archive_url, location, start, end)
        cache_file.write_text(json.dumps(payload), encoding="utf-8")

    return _build_records(payload, location)
