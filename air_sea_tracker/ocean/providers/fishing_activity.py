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
from ocean.providers.base import USER_AGENT, OceanProvider
from services.rate_limiter import MonthlyRateLimiter, RateLimiter

logger = logging.getLogger(__name__)

REPORT_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
DATASET = "public-global-fishing-effort:latest"
RADIUS_KM = 25.0
LOOKBACK_DAYS = 30
# GFW's published non-commercial limits (License & rate limits) — shared
# across all of a user's tokens, enforced server-side with a 24h/30-day
# lockout on breach. Tracked locally (same RateLimiter/MonthlyRateLimiter
# used for OpenSky/VesselAPI, persisted via Settings — SDR §22/§27.6) so
# Settings can show usage and so this provider can back off before
# actually hitting a 429, rather than only reacting after one.
DAILY_CALL_LIMIT = 50_000
MONTHLY_CALL_LIMIT = 1_500_000
# GFW's 4Wings report endpoint is much slower than every other Ocean
# provider (measured ~22s for a busy area over a 30-day window, vs. the
# shared 15s DEFAULT_TIMEOUT other providers use) — a dedicated, longer
# timeout avoids spurious "service unreachable" results on busy fishing
# grounds.
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=45)
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


def _date_bounds(today: date) -> tuple[date, date]:
    end = today - timedelta(days=PROCESSING_LAG_DAYS)
    start = end - timedelta(days=LOOKBACK_DAYS)
    return start, end


class FishingActivityProvider(OceanProvider):
    name = "Global Fishing Watch"

    def __init__(self) -> None:
        self._daily_limiter = RateLimiter(name="gfw_daily", daily_limit=DAILY_CALL_LIMIT)
        self._monthly_limiter = MonthlyRateLimiter(name="gfw_monthly", monthly_limit=MONTHLY_CALL_LIMIT)

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

        if not self._daily_limiter.can_call() or not self._monthly_limiter.can_call():
            logger.warning(
                "Global Fishing Watch quota exhausted: %s / %s",
                self._daily_limiter.quota_summary(),
                self._monthly_limiter.quota_summary(),
            )
            return {
                "fishing_activity_hours": SourcedValue.unavailable(
                    self.name, "Global Fishing Watch daily/monthly API quota reached (see Settings > Data Sources)"
                )
            }

        start, end = _date_bounds((when or datetime.now(timezone.utc)).date())
        params = [
            ("date-range", f"{start.isoformat()},{end.isoformat()}"),
            ("datasets[0]", DATASET),
            ("format", "JSON"),
            ("temporal-resolution", "ENTIRE"),
            ("spatial-resolution", "LOW"),
            ("spatial-aggregation", "true"),
            # Required as of GFW's current v3 4Wings report API — omitting it
            # returns 422 Unprocessable Entity ("group-by could be VESSEL_ID,
            # FLAG,GEARTYPE,FLAGANDGEARTYPE,MMSI"), even though spatial
            # aggregation makes the grouping itself irrelevant to our total.
            ("group-by", "MMSI"),
        ]
        body = {"geojson": _bbox_polygon(lat, lon, RADIUS_KM)}
        self._daily_limiter.record_call()
        self._monthly_limiter.record_call()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    REPORT_URL,
                    params=params,
                    json=body,
                    headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"},
                    timeout=REQUEST_TIMEOUT,
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
                timestamp=end.isoformat(),
                note=(
                    f"Apparent AIS fishing effort within {RADIUS_KM:.0f} km, summed over the "
                    f"{LOOKBACK_DAYS} days from {start.isoformat()} to {end.isoformat()}. GFW's "
                    f"pipeline lags real time by ~{PROCESSING_LAG_DAYS} days, so nothing more "
                    f"recent than {end.isoformat()} is included yet."
                ),
            )
        }
