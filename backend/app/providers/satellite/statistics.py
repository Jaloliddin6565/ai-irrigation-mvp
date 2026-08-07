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

Bands are requested as raw digital numbers (DN) — no `units` field at all
— and reflectance bands (B03/B04/B05/B08/B11/B12) are converted to
reflectance in-script by dividing by 10000 (the standard Sentinel-2 L2A DN
scale factor) before computing any index; SCL's raw DN value is used
directly for masking, unconverted. Two other request shapes were tried
against the real CDSE Statistical API during the Phase 4.5 live
connectivity check and both failed: requesting `units: "REFLECTANCE"` for
every band (including SCL) is rejected outright ("Invalid script! Band
'SCL' ... requested in unsupported units 'REFLECTANCE'"); requesting
per-band units via an object-array `bands` (`{name, units}` entries, mixing
REFLECTANCE and DN in one `input` block) causes a generic, unhelpful
"Script must return an array" failure with no indication the actual
problem was the band specification, not `evaluatePixel`'s return shape. A
second `input` array entry to separate REFLECTANCE bands from DN bands
(the multi-input-block pattern used to combine different datasets) also
fails here with "Dataset with id: 1 not found" — that pattern is for
combining multiple *data sources*, not splitting band-groups within one.
The plain-band-list-plus-manual-scaling form below is the one verified to
work end to end against the real API.

The full field polygon (never a centroid or an arbitrary bounding box) is
sent as the aggregation geometry, so returned percentiles/mean/std describe
the whole parcel.

Spatial resolution note: the request geometry is WGS84 / EPSG:4326, so the
Statistical API's ``resx``/``resy`` values are expressed in degrees, not
metres. We therefore convert the desired ~10 m Sentinel-2 sampling resolution
to degree resolution at the parcel latitude instead of sending ``10`` (which
would mean roughly ten degrees per pixel).
"""

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from app.core.http_client import RetryingHttpClient
from app.core.provider_errors import ProviderMalformedResponseError, UnsupportedGeometryError
from app.providers.satellite.cdse_auth import CdseTokenClient
from app.providers.satellite.scl import build_scl_exclusion_js_array

logger = logging.getLogger(__name__)

PROVIDER_NAME = "cdse-statistics"
COLLECTION = "sentinel-2-l2a"
TARGET_RESOLUTION_METERS = 10.0
METERS_PER_DEGREE_LATITUDE = 111_320.0
MIN_LONGITUDE_SCALE = 1e-6

INDEX_NAMES = ("ndvi", "ndmi", "ndre", "msi", "ndwi", "nbr2")

_EVALSCRIPT_TEMPLATE = """//VERSION=3
function setup() {{
  return {{
    input: [{{
      bands: ["B03", "B04", "B05", "B08", "B11", "B12", "SCL", "dataMask"]
    }}],
    output: [
      {{ id: "ndvi", bands: 1 }},
      {{ id: "ndmi", bands: 1 }},
      {{ id: "ndre", bands: 1 }},
      {{ id: "msi", bands: 1 }},
      {{ id: "ndwi", bands: 1 }},
      {{ id: "nbr2", bands: 1 }},
      {{ id: "dataMask", bands: 1 }}
    ]
  }};
}}

// Sentinel-2 L2A bands arrive as raw DN (digital number); the standard
// scale factor to reflectance (0.0-1.0) is 10000. SCL is a classification
// code, not a reflectance value, so it is never divided.
var REFLECTANCE_SCALE = 10000;
var EXCLUDED_SCL = {excluded_scl};

function safeRatio(numerator, denominator) {{
  if (Math.abs(denominator) < 1e-6) return 0;
  return numerator / denominator;
}}

function evaluatePixel(sample) {{
  var b03 = sample.B03 / REFLECTANCE_SCALE;
  var b04 = sample.B04 / REFLECTANCE_SCALE;
  var b05 = sample.B05 / REFLECTANCE_SCALE;
  var b08 = sample.B08 / REFLECTANCE_SCALE;
  var b11 = sample.B11 / REFLECTANCE_SCALE;
  var b12 = sample.B12 / REFLECTANCE_SCALE;

  var maskedOut = sample.dataMask === 0 || EXCLUDED_SCL.indexOf(sample.SCL) !== -1;
  var mask = maskedOut ? 0 : 1;

  return {{
    ndvi: [safeRatio(b08 - b04, b08 + b04)],
    ndmi: [safeRatio(b08 - b11, b08 + b11)],
    ndre: [safeRatio(b08 - b05, b08 + b05)],
    msi: [safeRatio(b11, b08)],
    ndwi: [safeRatio(b03 - b08, b03 + b08)],
    nbr2: [safeRatio(b11 - b12, b11 + b12)],
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


def _polygon_reference_latitude(polygon: dict) -> float:
    """Return a stable representative latitude for WGS84 resolution conversion."""
    coordinates = polygon.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise UnsupportedGeometryError(
            provider=PROVIDER_NAME,
            message_en="Statistical API polygon is missing coordinates.",
            message_uz="Statistik hisoblash uchun dala koordinatalari topilmadi.",
        )

    exterior_ring = coordinates[0]
    if not isinstance(exterior_ring, list) or not exterior_ring:
        raise UnsupportedGeometryError(
            provider=PROVIDER_NAME,
            message_en="Statistical API polygon exterior ring is empty.",
            message_uz="Dala chegarasi koordinatalari bo'sh.",
        )

    latitudes: list[float] = []
    for point in exterior_ring:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise UnsupportedGeometryError(
                provider=PROVIDER_NAME,
                message_en="Statistical API polygon contains an invalid coordinate.",
                message_uz="Dala chegarasida noto'g'ri koordinata mavjud.",
            )
        lon, lat = point[0], point[1]
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            raise UnsupportedGeometryError(
                provider=PROVIDER_NAME,
                message_en="Statistical API polygon coordinates must be numeric.",
                message_uz="Dala chegarasi koordinatalari son bo'lishi kerak.",
            )
        if not math.isfinite(float(lon)) or not math.isfinite(float(lat)):
            raise UnsupportedGeometryError(
                provider=PROVIDER_NAME,
                message_en="Statistical API polygon contains non-finite coordinates.",
                message_uz="Dala chegarasida yaroqsiz koordinata mavjud.",
            )
        if not -90.0 <= float(lat) <= 90.0:
            raise UnsupportedGeometryError(
                provider=PROVIDER_NAME,
                message_en="Statistical API polygon latitude is outside WGS84 bounds.",
                message_uz="Dala koordinatasi WGS84 kenglik chegarasidan tashqarida.",
            )
        latitudes.append(float(lat))

    return (min(latitudes) + max(latitudes)) / 2.0


def _resolution_degrees_for_polygon(
    polygon: dict, resolution_meters: float = TARGET_RESOLUTION_METERS
) -> tuple[float, float]:
    """Convert a metre target resolution to EPSG:4326 degree resolution.

    The approximation is intentionally lightweight and appropriate for parcel-scale
    MVP use in Uzbekistan. It avoids adding a projection dependency while keeping
    the request geometry and declared CRS consistent.
    """
    if resolution_meters <= 0 or not math.isfinite(resolution_meters):
        raise ValueError("resolution_meters must be a finite positive number")

    reference_latitude = _polygon_reference_latitude(polygon)
    longitude_scale = abs(math.cos(math.radians(reference_latitude)))
    if longitude_scale < MIN_LONGITUDE_SCALE:
        raise UnsupportedGeometryError(
            provider=PROVIDER_NAME,
            message_en="Parcel latitude is too close to a pole for EPSG:4326 resolution conversion.",
            message_uz="Dala koordinatasi qutbga juda yaqin; statistik hisoblash bajarilmadi.",
        )

    resy = resolution_meters / METERS_PER_DEGREE_LATITUDE
    resx = resolution_meters / (METERS_PER_DEGREE_LATITUDE * longitude_scale)
    return resx, resy


def _safe_provider_error_summary(response: httpx.Response) -> str | None:
    """Extract only non-sensitive CDSE error fields for server logs."""
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None

    candidate = payload.get("error", payload)
    if not isinstance(candidate, dict):
        return None

    parts: list[str] = []
    for key in ("code", "reason", "message"):
        value = candidate.get(key)
        if isinstance(value, (str, int, float)):
            text = str(value).strip()
            if text:
                parts.append(f"{key}={text}")

    if not parts:
        return None
    return "; ".join(parts)[:500]


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

        resx, resy = _resolution_degrees_for_polygon(polygon)
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
                "resx": resx,
                "resy": resy,
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
            summary = _safe_provider_error_summary(response)
            if summary:
                logger.warning(
                    "CDSE Statistical API returned HTTP %s: %s",
                    response.status_code,
                    summary,
                )
            else:
                logger.warning(
                    "CDSE Statistical API returned HTTP %s with no structured error detail",
                    response.status_code,
                )
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
