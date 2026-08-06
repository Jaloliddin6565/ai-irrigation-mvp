"""CDSE Sentinel Hub Catalog API client — Sentinel-2 L2A acquisition
discovery (STAC-based search).

Always searches the field's actual, complete polygon — never a centroid
point or an arbitrary bounding box — so acquisition discovery reflects what
the field really looks like. Never fabricates an acquisition date: every
`AcquisitionRecord` this module returns carries the provider's own reported
datetime, and an acquisition over the configured cloud-cover threshold is
recorded as rejected (with a reason) rather than silently dropped.

Pagination (verified live during Phase 4.5): the real CDSE Catalog API's
`links` "next" entry is not a distinctly-queried follow-up URL — it is an
opaque cursor fragment (e.g. `{"next": "2"}`) that must be merged into the
*original* request body (`"merge": true`) and POSTed back to the same
`href`. `_next_page_link` returns the whole link object so `search()` can
apply that merge; a page limit of 100 in normal use means most searches
never actually paginate (a single field's Sentinel-2 revisit history over
the ~90-day lookback window is well under 100 scenes), but the mechanism
is exercised and confirmed correct.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from shapely.geometry import shape

from app.core.http_client import RetryingHttpClient
from app.core.provider_errors import (
    ProviderMalformedResponseError,
    UnsupportedGeometryError,
)
from app.providers.satellite.cdse_auth import CdseTokenClient

logger = logging.getLogger("app.providers.satellite.catalog")

PROVIDER_NAME = "cdse-catalog"
COLLECTION = "sentinel-2-l2a"

# Defends against a misbehaving/looping "next" link — this is a hard,
# documented bound, not a silent infinite loop.
MAX_PAGES = 5


@dataclass(frozen=True)
class AcquisitionRecord:
    acquisition_date: date
    acquisition_datetime: datetime
    scene_id: str | None
    cloud_cover_pct: float | None
    collection: str


@dataclass(frozen=True)
class RejectedAcquisitionRecord:
    acquisition_date: date
    reason: str


@dataclass(frozen=True)
class CatalogSearchResult:
    accepted: list[AcquisitionRecord] = field(default_factory=list)
    rejected: list[RejectedAcquisitionRecord] = field(default_factory=list)


def _validate_geometry(polygon: dict) -> None:
    if not isinstance(polygon, dict) or polygon.get("type") != "Polygon":
        raise UnsupportedGeometryError(
            provider=PROVIDER_NAME,
            message_en="Catalog search requires a GeoJSON Polygon geometry.",
            message_uz="Qidiruv uchun GeoJSON Polygon geometriyasi kerak.",
        )
    try:
        geom = shape(polygon)
    except (ValueError, TypeError) as exc:
        raise UnsupportedGeometryError(
            provider=PROVIDER_NAME,
            message_en=f"Could not parse field polygon for Catalog search: {exc}",
            message_uz="Dala poligonini tahlil qilib bo'lmadi.",
        ) from exc
    if geom.is_empty or not geom.is_valid:
        raise UnsupportedGeometryError(
            provider=PROVIDER_NAME,
            message_en="Field polygon is not a valid geometry.",
            message_uz="Dala poligoni yaroqsiz geometriya.",
        )


class CdseCatalogClient:
    def __init__(
        self,
        *,
        catalog_url: str,
        token_client: CdseTokenClient,
        timeout_seconds: float,
        max_retries: int,
        retry_base_delay_seconds: float,
        retry_max_delay_seconds: float,
    ) -> None:
        self._catalog_url = catalog_url
        self._token_client = token_client
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds

    async def search(
        self,
        polygon: dict,
        *,
        start_date: date,
        end_date: date,
        max_cloud_cover_pct: float,
    ) -> CatalogSearchResult:
        _validate_geometry(polygon)

        request_body = {
            "collections": [COLLECTION],
            "datetime": f"{start_date.isoformat()}T00:00:00Z/{end_date.isoformat()}T23:59:59Z",
            "intersects": polygon,
            "limit": 100,
        }

        accepted: dict[str, AcquisitionRecord] = {}
        rejected: list[RejectedAcquisitionRecord] = []
        url: str | None = self._catalog_url
        method = "POST"
        body: dict | None = request_body

        async with RetryingHttpClient(
            provider=PROVIDER_NAME,
            timeout_seconds=self._timeout_seconds,
            max_retries=self._max_retries,
            retry_base_delay_seconds=self._retry_base_delay_seconds,
            retry_max_delay_seconds=self._retry_max_delay_seconds,
        ) as client:
            for _page in range(MAX_PAGES):
                if url is None:
                    break
                response = await self._token_client.request_with_auth(
                    client, method, url, json=body
                )
                if response.status_code != 200:
                    raise ProviderMalformedResponseError(
                        provider=PROVIDER_NAME,
                        message_en=f"Catalog API returned HTTP {response.status_code}.",
                        message_uz="Catalog API kutilmagan javob qaytardi.",
                    )
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ProviderMalformedResponseError(
                        provider=PROVIDER_NAME,
                        message_en="Catalog API response was not valid JSON.",
                        message_uz="Catalog API javobi noto'g'ri formatda.",
                    ) from exc

                features = payload.get("features") if isinstance(payload, dict) else None
                if not isinstance(features, list):
                    raise ProviderMalformedResponseError(
                        provider=PROVIDER_NAME,
                        message_en="Catalog API response is missing a 'features' array.",
                        message_uz="Catalog API javobida 'features' massivi yo'q.",
                    )

                for feature in features:
                    record = self._parse_feature(feature)
                    if record is None:
                        continue
                    if record.cloud_cover_pct is not None and (
                        record.cloud_cover_pct > max_cloud_cover_pct
                    ):
                        rejected.append(
                            RejectedAcquisitionRecord(
                                acquisition_date=record.acquisition_date,
                                reason=(
                                    f"cloud_cover {record.cloud_cover_pct:.1f}% exceeds "
                                    f"threshold {max_cloud_cover_pct:.1f}%"
                                ),
                            )
                        )
                        continue
                    key = record.scene_id or record.acquisition_datetime.isoformat()
                    accepted[key] = record

                next_link = self._next_page_link(payload)
                if next_link is None:
                    url = None
                    continue
                url = next_link["href"]
                method = next_link.get("method") or "POST"
                # The real CDSE Catalog API paginates via an opaque cursor
                # merged into the *original* request body (e.g.
                # {"next": "2"}), not a distinctly-queried follow-up URL —
                # discovered during the Phase 4.5 live connectivity check.
                # `merge: true` means "merge this fragment into the request
                # that produced this page"; anything else replaces it
                # wholesale (defensive fallback, not observed live).
                cursor_fragment = next_link.get("body")
                if next_link.get("merge") and isinstance(cursor_fragment, dict):
                    body = {**request_body, **cursor_fragment}
                elif isinstance(cursor_fragment, dict):
                    body = cursor_fragment
                else:
                    body = request_body

        sorted_accepted = sorted(accepted.values(), key=lambda r: r.acquisition_datetime)
        return CatalogSearchResult(accepted=sorted_accepted, rejected=rejected)

    def _parse_feature(self, feature: object) -> AcquisitionRecord | None:
        if not isinstance(feature, dict):
            return None
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            return None
        raw_datetime = properties.get("datetime")
        if not isinstance(raw_datetime, str):
            return None
        try:
            acquisition_datetime = datetime.fromisoformat(raw_datetime.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Catalog API returned an unparseable datetime: %r", raw_datetime)
            return None
        if acquisition_datetime.tzinfo is None:
            acquisition_datetime = acquisition_datetime.replace(tzinfo=UTC)

        cloud_cover = properties.get("eo:cloud_cover")
        cloud_cover_pct = float(cloud_cover) if isinstance(cloud_cover, int | float) else None

        return AcquisitionRecord(
            acquisition_date=acquisition_datetime.date(),
            acquisition_datetime=acquisition_datetime,
            scene_id=feature.get("id") if isinstance(feature.get("id"), str) else None,
            cloud_cover_pct=cloud_cover_pct,
            collection=COLLECTION,
        )

    def _next_page_link(self, payload: dict) -> dict | None:
        links = payload.get("links")
        if not isinstance(links, list):
            return None
        for link in links:
            if isinstance(link, dict) and link.get("rel") == "next":
                href = link.get("href")
                if isinstance(href, str) and href:
                    return link
        return None
