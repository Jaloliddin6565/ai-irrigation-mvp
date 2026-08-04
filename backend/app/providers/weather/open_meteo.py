"""Live weather provider backed by Open-Meteo (https://open-meteo.com).

No API key required for non-commercial use. Historical dates are served by
the archive API (ERA5 reanalysis-derived, `OPEN_METEO_ARCHIVE_URL`); "today"
onward is served by the forecast API (`OPEN_METEO_FORECAST_URL`) — see
docs/api.md for the endpoint verification date. This provider never
fabricates a missing day: any date Open-Meteo did not return (or returned as
null) is simply absent from `WeatherSeries.days` and reported in
`WeatherSeries.coverage.missing_dates` — see CLAUDE.md rule 5 and
docs/methodology.md "Weather gap handling".

Open-Meteo's `precipitation_probability_max` is a forecast-only concept; for
already-observed (archive) days this provider records
`precipitation_probability_pct=100.0` (precipitation that already occurred
is certain, not a forecast probability) — a documented convention, not
fabricated data.
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

import httpx

from app.core.cache import TTLCache
from app.core.http_client import RetryingHttpClient
from app.core.provider_errors import InvalidDateRangeError, ProviderMalformedResponseError
from app.providers.weather.base import DailyWeather, WeatherCoverage, WeatherSeries

logger = logging.getLogger("app.providers.weather.open_meteo")

PROVIDER_NAME = "open-meteo"

# Variables requested from Open-Meteo's `daily=` parameter, mapped to our
# normalized DailyWeather field names. Archive (historical) and forecast
# calls request the same set except precipitation_probability_max, which
# only exists on the forecast endpoint.
_VAR_MAP = {
    "et0_fao_evapotranspiration": "et0_mm",
    "precipitation_sum": "precipitation_mm",
    "temperature_2m_max": "temperature_max_c",
    "temperature_2m_min": "temperature_min_c",
    "wind_speed_10m_max": "wind_speed_ms",
    "shortwave_radiation_sum": "shortwave_radiation_mj_m2",
}
_DAILY_VARS_ARCHIVE = list(_VAR_MAP)
_DAILY_VARS_FORECAST = [*_DAILY_VARS_ARCHIVE, "precipitation_probability_max"]


class OpenMeteoProvider:
    """WeatherProvider implementation for DATA_MODE=live."""

    def __init__(
        self,
        *,
        forecast_url: str,
        archive_url: str,
        timezone: str,
        timeout_seconds: float,
        max_retries: int,
        retry_base_delay_seconds: float,
        retry_max_delay_seconds: float,
        cache: TTLCache | None = None,
        cache_ttl_seconds: float = 0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._forecast_url = forecast_url
        self._archive_url = archive_url
        self._timezone = timezone
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds
        self._transport = transport

    def get_daily_series(
        self, lat: float, lon: float, start_date: date, end_date: date
    ) -> WeatherSeries:
        return self.get_daily_series_for_range(lat, lon, start_date, end_date, as_of=date.today())

    def get_daily_series_for_range(
        self, lat: float, lon: float, start_date: date, end_date: date, as_of: date
    ) -> WeatherSeries:
        if end_date < start_date:
            raise InvalidDateRangeError(
                provider=PROVIDER_NAME,
                message_en=f"end_date {end_date} is before start_date {start_date}.",
                message_uz="Boshlanish sanasi tugash sanasidan keyin bo'la olmaydi.",
            )
        return asyncio.run(self._get_async(lat, lon, start_date, end_date, as_of))

    async def _get_async(
        self, lat: float, lon: float, start_date: date, end_date: date, as_of: date
    ) -> WeatherSeries:
        cache_key = (
            "weather",
            round(lat, 5),
            round(lon, 5),
            start_date,
            end_date,
            as_of,
            self._timezone,
        )
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached.model_copy(update={"cache_hit": True})

        days_by_date: dict[date, DailyWeather] = {}
        archive_end = min(end_date, as_of)
        forecast_start = max(start_date, as_of + timedelta(days=1))

        async with RetryingHttpClient(
            provider=PROVIDER_NAME,
            timeout_seconds=self._timeout_seconds,
            max_retries=self._max_retries,
            retry_base_delay_seconds=self._retry_base_delay_seconds,
            retry_max_delay_seconds=self._retry_max_delay_seconds,
            transport=self._transport,
        ) as client:
            if start_date <= archive_end:
                archive_days = await self._fetch(
                    client,
                    self._archive_url,
                    lat,
                    lon,
                    start_date,
                    archive_end,
                    _DAILY_VARS_ARCHIVE,
                    as_of=as_of,
                    is_archive=True,
                )
                days_by_date.update({d.date: d for d in archive_days})

            if forecast_start <= end_date:
                forecast_days = await self._fetch(
                    client,
                    self._forecast_url,
                    lat,
                    lon,
                    forecast_start,
                    end_date,
                    _DAILY_VARS_FORECAST,
                    as_of=as_of,
                    is_archive=False,
                )
                days_by_date.update({d.date: d for d in forecast_days})

        sorted_days = [days_by_date[d] for d in sorted(days_by_date)]

        requested_total = (end_date - start_date).days + 1
        expected_dates = {start_date + timedelta(days=i) for i in range(requested_total)}
        missing = sorted(expected_dates - set(days_by_date))
        coverage_ratio = (
            (requested_total - len(missing)) / requested_total if requested_total else 0.0
        )
        completeness_status = (
            "complete" if not missing else "partial" if coverage_ratio >= 0.5 else "insufficient"
        )

        series = WeatherSeries(
            timezone=self._timezone,
            days=sorted_days,
            provider=PROVIDER_NAME,
            source="Open-Meteo (live)",
            retrieved_at=datetime.now(UTC),
            coverage=WeatherCoverage(
                requested_start_date=start_date,
                requested_end_date=end_date,
                received_start_date=sorted_days[0].date if sorted_days else None,
                received_end_date=sorted_days[-1].date if sorted_days else None,
                missing_dates=missing,
                coverage_ratio=coverage_ratio,
                completeness_status=completeness_status,
            ),
            cache_hit=False,
        )
        if self._cache is not None and self._cache_ttl_seconds > 0:
            self._cache.set(cache_key, series, self._cache_ttl_seconds)
        return series

    async def _fetch(
        self,
        client: RetryingHttpClient,
        base_url: str,
        lat: float,
        lon: float,
        start: date,
        end: date,
        daily_vars: list[str],
        *,
        as_of: date,
        is_archive: bool,
    ) -> list[DailyWeather]:
        response = await client.request(
            "GET",
            base_url,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": ",".join(daily_vars),
                "timezone": self._timezone,
            },
        )
        if response.status_code != 200:
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en=f"Open-Meteo returned HTTP {response.status_code}.",
                message_uz="Open-Meteo dan kutilmagan javob keldi.",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en="Open-Meteo response was not valid JSON.",
                message_uz="Open-Meteo javobi noto'g'ri formatda.",
            ) from exc

        return self._parse_daily(payload, as_of=as_of, is_archive=is_archive)

    def _parse_daily(self, payload: dict, *, as_of: date, is_archive: bool) -> list[DailyWeather]:
        daily = payload.get("daily") if isinstance(payload, dict) else None
        if not isinstance(daily, dict) or "time" not in daily:
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en="Open-Meteo response is missing the 'daily' block.",
                message_uz="Open-Meteo javobida 'daily' ma'lumotlari yo'q.",
            )

        dates_raw = daily.get("time") or []
        for key in _VAR_MAP:
            series = daily.get(key)
            if not isinstance(series, list) or len(series) != len(dates_raw):
                raise ProviderMalformedResponseError(
                    provider=PROVIDER_NAME,
                    message_en=f"Open-Meteo '{key}' array length does not match 'time'.",
                    message_uz="Open-Meteo javobidagi massivlar uzunligi mos kelmadi.",
                )
        probability_series = daily.get("precipitation_probability_max")

        seen: set[date] = set()
        result: list[DailyWeather] = []
        for i, raw_date in enumerate(dates_raw):
            try:
                d = date.fromisoformat(raw_date)
            except (TypeError, ValueError) as exc:
                raise ProviderMalformedResponseError(
                    provider=PROVIDER_NAME,
                    message_en=f"Open-Meteo returned an unparseable date: {raw_date!r}.",
                    message_uz="Open-Meteo noto'g'ri sana qaytardi.",
                ) from exc
            if d in seen:
                logger.warning(
                    "Open-Meteo returned a duplicate date %s; keeping the first occurrence", d
                )
                continue
            seen.add(d)

            values: dict[str, float] = {}
            row_incomplete = False
            for src_key, dst_key in _VAR_MAP.items():
                raw_value = daily[src_key][i]
                if raw_value is None:
                    row_incomplete = True
                    break
                values[dst_key] = float(raw_value)
            if row_incomplete:
                # A day Open-Meteo itself reports as null (its own gap, e.g.
                # not-yet-processed reanalysis) — dropped, not zero-filled.
                continue
            if values["et0_mm"] < 0 or values["precipitation_mm"] < 0:
                raise ProviderMalformedResponseError(
                    provider=PROVIDER_NAME,
                    message_en=f"Open-Meteo returned a negative ET0/precipitation value for {d}.",
                    message_uz="Open-Meteo manfiy qiymat qaytardi.",
                )

            if (
                probability_series is not None
                and i < len(probability_series)
                and probability_series[i] is not None
            ):
                probability_pct = float(probability_series[i])
            else:
                probability_pct = 100.0 if is_archive else 0.0

            result.append(
                DailyWeather(
                    date=d,
                    is_forecast=d > as_of,
                    et0_mm=values["et0_mm"],
                    precipitation_mm=values["precipitation_mm"],
                    precipitation_probability_pct=probability_pct,
                    temperature_max_c=values["temperature_max_c"],
                    temperature_min_c=values["temperature_min_c"],
                    wind_speed_ms=values["wind_speed_ms"],
                    shortwave_radiation_mj_m2=values["shortwave_radiation_mj_m2"],
                )
            )
        result.sort(key=lambda dw: dw.date)
        return result
