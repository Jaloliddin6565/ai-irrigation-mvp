"""CDSE Sentinel Hub Statistical API client — full-polygon Sentinel-2 L2A
parcel statistics for NDVI, NDMI, NDRE, MSI, NDWI, and NBR2.

Index formulas (safe-division: a zero/near-zero denominator yields 0, never
NaN or +/-Infinity — see `_SAFE_RATIO_JS` in the evalscript below):

    NDVI = (B08 - B04) / (B08 + B04)
    NDMI = (B08 - B11) / (B08 + B11)
    NDRE = (B08 - B05) / (B08 + B05)
    MSI  = B11 / B08
    NDWI = (B03 - B08) / (B03 + B08)
    NBR2 = (B11 - B12) / (B11 + B12)

Masking uses both the Sentinel-2 `dataMask` band and the Scene
Classification Layer (SCL) — see app/providers/satellite/scl.py for the
explicit, documented, tested exclusion class list. The evalscript template
below reads that list rather than hardcoding its own copy, so a masking
policy change happens in exactly one place.

The full field polygon (never a centroid or an arbitrary bounding box) is
sent as the aggregation geometry, so returned percentiles/mean/std describe
the whole parcel.
"""

import math
from dataclasses import dataclass
from datetime import date, datetime

from app.core.http_client import RetryingHttpClient
from app.core.provider_errors import ProviderMalformedResponseError, UnsupportedGeometryError
from app.providers.satellite.cdse_auth import CdseTokenClient
from app.providers.satellite.scl import build_scl_exclusion_js_array

PROVIDER_NAME = "cdse-statistics"
COLLECTION = "sentinel-2-l2a"

INDEX_NAMES = ("ndvi", "ndmi", "ndre", "msi", "ndwi", "nbr2")

_EVALSCRIPT_TEMPLATE = """//VERSION=3
function setup() {{
  return {{
    input: [{{
      bands: ["B03", "B04", "B05", "B08", "B11", "B12", "SCL", "dataMask"],
      units: "REFLECTANCE"
    }}],
    output: [
      {{ id: "ndvi", bands: 1, sampleType: "FLOAT32" }},
      {{ id: "ndmi", bands: 1, sampleType: "FLOAT32" }},
      {{ id: "ndre", bands: 1, sampleType: "FLOAT32" }},
      {{ id: "msi", bands: 1, sampleType: "FLOAT32" }},
      {{ id: "ndwi", bands: 1, sampleType: "FLOAT32" }},
      {{ id: "nbr2", bands: 1, sampleType: "FLOAT32" }},
      {{ id: "dataMask", bands: 1 }}
    ]
  }};
}}

var EXCLUDED_SCL = {excluded_scl};

function safeRatio(numerator, denominator) {{
  if (Math.abs(denominator) < 1e-6) return 0;
  return numerator / denominator;
}}

function evaluatePixel(sample) {{
  var maskedOut = sample.dataMask === 0 || EXCLUDED_SCL.indexOf(sample.SCL) !== -1;
  var mask = maskedOut ? 0 : 1;

  return {{
    ndvi: [safeRatio(sample.B08 - sample.B04, sample.B08 + sample.B04)],
    ndmi: [safeRatio(sample.B08 - sample.B11, sample.B08 + sample.B11)],
    ndre: [safeRatio(sample.B08 - sample.B05, sample.B08 + sample.B05)],
    msi: [safeRatio(sample.B11, sample.B08)],
    ndwi: [safeRatio(sample.B03 - sample.B08, sample.B03 + sample.B08)],
    nbr2: [safeRatio(sample.B11 - sample.B12, sample.B11 + sample.B12)],
    dataMask: [mask]
  }};
}}
"""


def build_evalscript() -> str:
    return _EVALSCRIPT_TEMPLATE.format(excluded_scl=build_scl_exclusion_js_array())


@dataclass(frozen=True)
class IntervalStatistics:
    interval_start: date
    interval_end: date
    index_stats: dict[str, dict[str, float]]  # index name -> {p25,p50,p75,mean,std,min,max}
    valid_pixel_count: int
    invalid_pixel_count: int


def _is_finite(value: float) -> bool:
    return not (math.isnan(value) or math.isinf(value))


class CdseStatisticsClient:
    def __init__(
        self,
        *,
        statistics_url: str,
        token_client: CdseTokenClient,
        timeout_seconds: float,
        max_retries: int,
        retry_base_delay_seconds: float,
        retry_max_delay_seconds: float,
    ) -> None:
        self._statistics_url = statistics_url
        self._token_client = token_client
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds

    async def get_parcel_statistics(
        self,
        polygon: dict,
        *,
        start_date: date,
        end_date: date,
    ) -> list[IntervalStatistics]:
        if not isinstance(polygon, dict) or polygon.get("type") != "Polygon":
            raise UnsupportedGeometryError(
                provider=PROVIDER_NAME,
                message_en="Statistical API requires a GeoJSON Polygon geometry.",
                message_uz="Statistik hisoblash uchun GeoJSON Polygon geometriyasi kerak.",
            )

        request_body = {
            "input": {
                "bounds": {
                    "geometry": polygon,
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [{"type": COLLECTION}],
            },
            "aggregation": {
                "timeRange": {
                    "from": f"{start_date.isoformat()}T00:00:00Z",
                    "to": f"{end_date.isoformat()}T23:59:59Z",
                },
                "aggregationInterval": {"of": "P1D"},
                "evalscript": build_evalscript(),
                "resx": 10,
                "resy": 10,
            },
            "calculations": {
                index: {"statistics": {"default": {"percentiles": {"k": [25, 50, 75]}}}}
                for index in INDEX_NAMES
            },
        }

        async with RetryingHttpClient(
            provider=PROVIDER_NAME,
            timeout_seconds=self._timeout_seconds,
            max_retries=self._max_retries,
            retry_base_delay_seconds=self._retry_base_delay_seconds,
            retry_max_delay_seconds=self._retry_max_delay_seconds,
        ) as client:
            response = await self._token_client.request_with_auth(
                client, "POST", self._statistics_url, json=request_body
            )

        if response.status_code != 200:
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en=f"Statistical API returned HTTP {response.status_code}.",
                message_uz="Statistik API kutilmagan javob qaytardi.",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en="Statistical API response was not valid JSON.",
                message_uz="Statistik API javobi noto'g'ri formatda.",
            ) from exc

        return self._parse_response(payload)

    def _parse_response(self, payload: object) -> list[IntervalStatistics]:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ProviderMalformedResponseError(
                provider=PROVIDER_NAME,
                message_en="Statistical API response is missing a 'data' array.",
                message_uz="Statistik API javobida 'data' massivi yo'q.",
            )

        results: list[IntervalStatistics] = []
        for interval_entry in data:
            parsed = self._parse_interval(interval_entry)
            if parsed is not None:
                results.append(parsed)

        results.sort(key=lambda r: r.interval_start)
        return results

    def _parse_interval(self, entry: object) -> IntervalStatistics | None:
        if not isinstance(entry, dict):
            return None
        interval = entry.get("interval")
        outputs = entry.get("outputs")
        if not isinstance(interval, dict) or not isinstance(outputs, dict):
            return None

        try:
            interval_start = datetime.fromisoformat(
                str(interval["from"]).replace("Z", "+00:00")
            ).date()
            interval_end = datetime.fromisoformat(str(interval["to"]).replace("Z", "+00:00")).date()
        except (KeyError, ValueError):
            return None

        index_stats: dict[str, dict[str, float]] = {}
        valid_pixel_count = 0
        invalid_pixel_count = 0

        for index_name in INDEX_NAMES:
            band_output = outputs.get(index_name)
            stats = self._extract_band_stats(band_output)
            if stats is None:
                # This index had no usable pixels for this interval — the
                # whole interval is dropped rather than reporting an
                # invented value for one index and real ones for the rest.
                return None
            index_stats[index_name] = stats["values"]
            valid_pixel_count = max(valid_pixel_count, stats["valid_pixel_count"])
            invalid_pixel_count = max(invalid_pixel_count, stats["invalid_pixel_count"])

        return IntervalStatistics(
            interval_start=interval_start,
            interval_end=interval_end,
            index_stats=index_stats,
            valid_pixel_count=valid_pixel_count,
            invalid_pixel_count=invalid_pixel_count,
        )

    def _extract_band_stats(self, band_output: object) -> dict | None:
        if not isinstance(band_output, dict):
            return None
        bands = band_output.get("bands")
        if not isinstance(bands, dict):
            return None
        band_zero = bands.get("B0")
        if not isinstance(band_zero, dict):
            return None
        raw_stats = band_zero.get("stats")
        if not isinstance(raw_stats, dict):
            return None

        sample_count = raw_stats.get("sampleCount")
        no_data_count = raw_stats.get("noDataCount")
        if not isinstance(sample_count, int) or not isinstance(no_data_count, int):
            return None
        if sample_count < 0 or no_data_count < 0:
            return None
        if sample_count == 0:
            # No valid pixels at all for this index/interval.
            return None

        percentiles = raw_stats.get("percentiles")
        if not isinstance(percentiles, dict):
            return None

        try:
            values = {
                "p25": float(percentiles["25.0"]),
                "p50": float(percentiles["50.0"]),
                "p75": float(percentiles["75.0"]),
                "mean": float(raw_stats["mean"]),
                "std": float(raw_stats["stDev"]),
                "min": float(raw_stats["min"]),
                "max": float(raw_stats["max"]),
            }
        except (KeyError, TypeError, ValueError):
            return None

        if not all(_is_finite(v) for v in values.values()):
            return None

        return {
            "values": values,
            "valid_pixel_count": sample_count,
            "invalid_pixel_count": no_data_count,
        }
