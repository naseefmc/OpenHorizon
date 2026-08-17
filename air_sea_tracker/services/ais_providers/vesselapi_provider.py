"""VesselAPI REST provider (SDR §5, §22) — the "Other REST API" fallback slot.

Radius-query REST source (https://vesselapi.com/docs), useful as a
fallback/development source rather than a primary continuous feed: the
free tier caps at 150 calls/month, so this provider is gated by a
MonthlyRateLimiter (persisted, not just in-memory) and polls on a
deliberately slow cadence — left running non-stop at the default
interval it would still exhaust the whole monthly budget in a few
days, which is expected for a fallback source, not a bug.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp

from config.credentials import VESSELAPI_API_KEY, get_credential
from models.vessel import Vessel
from services.ais_providers.base import AISProvider, ProviderStatus
from services.rate_limiter import MonthlyRateLimiter, PersistentPollGate

logger = logging.getLogger(__name__)

RADIUS_URL = "https://api.vesselapi.com/v1/location/vessels/radius"
INBOUND_URL_TEMPLATE = "https://api.vesselapi.com/v1/port/{unlocode}/inbound"
POLL_INTERVAL_SECONDS = 1800  # 30 min — see module docstring re: 150 calls/month budget
MONTHLY_CALL_LIMIT = 150
MAX_RADIUS_M = 100_000  # API-enforced ceiling


class VesselApiProvider(AISProvider):
    name = "VesselAPI"
    is_free_tier = False

    def __init__(self) -> None:
        super().__init__()
        self._rate_limiter = MonthlyRateLimiter(name="vesselapi", monthly_limit=MONTHLY_CALL_LIMIT)
        self._poll_gate = PersistentPollGate(name="vesselapi", min_interval_seconds=POLL_INTERVAL_SECONDS)

    def is_configured(self) -> bool:
        return bool(get_credential(VESSELAPI_API_KEY))

    def quota_summary(self) -> str:
        return self._rate_limiter.quota_summary()

    async def _run(self, bbox: tuple[float, float, float, float]) -> None:
        api_key = get_credential(VESSELAPI_API_KEY)
        lat_min, lon_min, lat_max, lon_max = bbox
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2
        radius_m = min(MAX_RADIUS_M, int(_haversine_km(center_lat, center_lon, lat_max, lon_max) * 1000))

        wait = self._poll_gate.seconds_until_ready(center_lat, center_lon)
        if wait > 0:
            logger.info("VesselAPI: waiting %.0fs (relaunched within the poll interval)", wait)
            await asyncio.sleep(wait)

        async with aiohttp.ClientSession() as session:
            while not self._stop.is_set():
                if not self._rate_limiter.can_call():
                    logger.info("VesselAPI monthly quota exhausted: %s", self._rate_limiter.quota_summary())
                    self._set_status(ProviderStatus.RATE_LIMITED)
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                if self.is_free_source_live and self.is_free_source_live():
                    logger.info("VesselAPI: skipping poll, a free source is already live")
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                try:
                    async with session.get(
                        RADIUS_URL,
                        params={
                            "filter.latitude": center_lat,
                            "filter.longitude": center_lon,
                            "filter.radius": radius_m,
                            "pagination.limit": 50,
                        },
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        self._rate_limiter.record_call()
                        self._poll_gate.record_call(center_lat, center_lon)
                        if resp.status == 429:
                            self._set_status(ProviderStatus.RATE_LIMITED)
                        elif resp.status == 401:
                            logger.warning("VesselAPI rejected the API key (401)")
                            self._set_status(ProviderStatus.OFFLINE)
                        elif resp.status != 200:
                            logger.warning("VesselAPI request failed: %s", resp.status)
                            self._set_status(ProviderStatus.OFFLINE)
                        else:
                            payload = await resp.json()
                            for row in payload.get("vessels") or []:
                                vessel = self._parse(row)
                                if vessel is not None:
                                    self._emit(vessel)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("VesselAPI poll error")
                    self._set_status(ProviderStatus.OFFLINE)

                await asyncio.sleep(POLL_INTERVAL_SECONDS)

    @staticmethod
    def _parse(row: dict) -> Vessel | None:
        # Live response uses snake_case (vessel_name, nav_status), unlike the
        # camelCase shown in VesselAPI's general docs example — confirmed
        # against an actual response rather than assumed.
        mmsi = row.get("mmsi")
        latitude, longitude = row.get("latitude"), row.get("longitude")
        if mmsi is None or latitude is None or longitude is None:
            return None
        imo = row.get("imo")
        nav_status = row.get("nav_status")
        return Vessel(
            mmsi=str(mmsi),
            imo=str(imo) if imo else None,
            name=(row.get("vessel_name") or "").strip() or None,
            latitude=float(latitude),
            longitude=float(longitude),
            speed_over_ground=row.get("sog"),
            course_over_ground=row.get("cog"),
            heading=row.get("heading"),
            navigation_status=str(nav_status) if nav_status is not None else None,
            source="vesselapi",
        )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from utils.distance import haversine_km

    return haversine_km(lat1, lon1, lat2, lon2)


class VesselApiError(Exception):
    pass


@dataclass
class InboundVessel:
    mmsi: str
    name: str | None
    destination: str | None
    eta: str | None  # RFC3339, as returned — display formatting is the GUI's job
    draught: float | None


async def fetch_inbound(unlocode: str, api_key: str, timeout_seconds: float = 40.0) -> list[InboundVessel]:
    """GET /v1/port/{unlocode}/inbound — vessels with a declared AIS
    destination matching this port, sorted by ETA. Confirmed live: takes
    20-30s to respond (much slower than the radius endpoint), so callers
    must not run this on the GUI thread or on a short polling timer.

    Complementary to RADIUS_URL, not a replacement: radius returns nearby
    *position reports* regardless of declared destination; this returns
    *declared-destination* vessels regardless of current distance from the
    port. Neither alone is "current port traffic."
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            INBOUND_URL_TEMPLATE.format(unlocode=unlocode),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=aiohttp.ClientTimeout(total=timeout_seconds),
        ) as resp:
            if resp.status != 200:
                raise VesselApiError(f"VesselAPI inbound lookup failed: HTTP {resp.status}")
            payload = await resp.json()

    results = []
    for row in payload.get("vesselETAs") or []:
        mmsi = row.get("mmsi")
        if mmsi is None:
            continue
        results.append(InboundVessel(
            mmsi=str(mmsi),
            name=(row.get("vessel_name") or "").strip() or None,
            destination=row.get("destination"),
            eta=row.get("eta"),
            draught=row.get("draught"),
        ))
    return results
