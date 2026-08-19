"""Global Fishing Watch fishing-activity provider (Ocean & Environment SDR §11).

Needs a free GFW API token — register at globalfishingwatch.org/our-apis,
no cost, then paste the token into Settings > Data Sources. GFW's own
data pipeline runs a few days behind real time (not live), so this
queries apparent AIS fishing effort over the last 30 days in a box
around the clicked point via the 4Wings Report API, verified against
GFW's own python-client source/fixtures (v3 wire format: hyphenated
query param aliases, `datasets[N]`/`filters[N]` indexed array params,
POST body carrying the area as GeoJSON) — https://github.com/GlobalFishingWatch/gfw-api-python-client.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone

import aiohttp

from config.credentials import GFW_API_KEY, get_credential
from ocean.models.ocean_data import STATUS_HISTORICAL, SourcedValue
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider

logger = logging.getLogger(__name__)

REPORT_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
DATASET = "public-global-fishing-effort:latest"
RADIUS_KM = 25.0
LOOKBACK_DAYS = 30
# GFW's processing pipeline lags real time by a few days (per GFW's own
# docs); querying right up to "today" reliably returns an incomplete tail.
PROCESSING_LAG_DAYS = 3


def _bbox_polygon(lat: float, lon: float, radius_km: float) -> dict:
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.1))
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon - dlon, lat - dlat],
                [lon + dlon, lat - dlat],
                [lon + dlon, lat + dlat],
                [lon - dlon, lat + dlat],
                [lon - dlon, lat - dlat],
            ]
        ],
    }


def _date_range(today: date) -> str:
    end = today - timedelta(days=PROCESSING_LAG_DAYS)
    start = end - timedelta(days=LOOKBACK_DAYS)
    return f"{start.isoformat()},{end.isoformat()}"


class FishingActivityProvider(OceanProvider):
    name = "Global Fishing Watch"

    def is_available(self) -> bool:
        return get_credential(GFW_API_KEY) is not None

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict[str, SourcedValue]:
        token = get_credential(GFW_API_KEY)
        if not token:
            return {
                "fishing_activity_hours": SourcedValue.unavailable(
                    self.name, "No Global Fishing Watch API key configured (Settings > Data Sources)"
                )
            }

        params = [
            ("date-range", _date_range((when or datetime.now(timezone.utc)).date())),
            ("datasets[0]", DATASET),
            ("format", "JSON"),
            ("temporal-resolution", "ENTIRE"),
            ("spatial-resolution", "LOW"),
            ("spatial-aggregation", "true"),
        ]
        body = {"geojson": _bbox_polygon(lat, lon, RADIUS_KM)}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    REPORT_URL,
                    params=params,
                    json=body,
                    headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"},
                    timeout=DEFAULT_TIMEOUT,
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
        except Exception:
            logger.exception("Global Fishing Watch query failed")
            return {
                "fishing_activity_hours": SourcedValue.unavailable(self.name, "Global Fishing Watch service unreachable")
            }

        total_hours = 0.0
        # Response shape: {"entries": [{"<dataset_name>": [{...,"hours": n}, ...]}]}
        for entry in data.get("entries", []) or []:
            if not isinstance(entry, dict):
                continue
            for rows in entry.values():
                for row in rows or []:
                    if isinstance(row, dict):
                        total_hours += row.get("hours") or 0

        return {
            "fishing_activity_hours": SourcedValue(
                value=round(total_hours, 1),
                unit="vessel-hours",
                source=self.name,
                status=STATUS_HISTORICAL,
                note=f"Apparent AIS fishing effort within {RADIUS_KM:.0f} km, last {LOOKBACK_DAYS} days (a few days delayed)",
            )
        }
