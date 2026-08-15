"""BarentsWatch Live AIS provider (SDR §5, §22).

Free, no-quota live AIS for Norwegian waters and the surrounding EEZ,
published by the Norwegian Coastal Administration. Requires a free
client registration (https://developer.barentswatch.no/docs/appreg)
for OAuth2 client-credentials auth — there is no anonymous tier, so
this provider stays DISABLED until a client ID/secret is configured.

Coverage is intentionally partial: fishing vessels under 15 m and
leisure/sailing craft under 45 m are excluded from this feed, and
positions are restricted to the Norwegian economic zone. That's a
BarentsWatch data-policy limit, not a bug in this provider.

REST/poll-based (there is no public live websocket), so this follows
the same poll-loop shape as ADSBCollector rather than AISStreamProvider's
websocket reader.
"""

from __future__ import annotations

import asyncio
import logging
import time

import aiohttp

from config.credentials import BARENTSWATCH_CLIENT_ID, BARENTSWATCH_CLIENT_SECRET, get_credential
from models.vessel import Vessel
from services.ais_providers.base import AISProvider, ProviderStatus
from services.geo_service import is_within_radius
from services.rate_limiter import PersistentPollGate

logger = logging.getLogger(__name__)

TOKEN_URL = "https://id.barentswatch.no/connect/token"
POSITIONS_URL = "https://live.ais.barentswatch.no/v1/latest/combined"
POLL_INTERVAL_SECONDS = 15


def _get(d: dict, *keys: str):
    """BarentsWatch's public docs don't show a JSON sample; try both the
    camelCase (typical ASP.NET default) and PascalCase (shown in the Go
    client bindings) forms of each field rather than guessing one."""
    for key in keys:
        if key in d:
            return d[key]
    return None


class BarentsWatchProvider(AISProvider):
    name = "BarentsWatch"

    def __init__(self) -> None:
        super().__init__()
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._poll_gate = PersistentPollGate(name="barentswatch", min_interval_seconds=POLL_INTERVAL_SECONDS)

    def is_configured(self) -> bool:
        return bool(get_credential(BARENTSWATCH_CLIENT_ID) and get_credential(BARENTSWATCH_CLIENT_SECRET))

    async def _fetch_token(self, session: aiohttp.ClientSession) -> bool:
        client_id = get_credential(BARENTSWATCH_CLIENT_ID)
        client_secret = get_credential(BARENTSWATCH_CLIENT_SECRET)
        try:
            async with session.post(
                TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "ais",
                    "grant_type": "client_credentials",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning("BarentsWatch token request failed: %s", resp.status)
                    return False
                data = await resp.json()
                self._token = data["access_token"]
                self._token_expires_at = time.monotonic() + float(data.get("expires_in", 3600)) - 60
                return True
        except Exception:
            logger.exception("BarentsWatch token request error")
            return False

    async def _run(self, bbox: tuple[float, float, float, float]) -> None:
        lat_min, lon_min, lat_max, lon_max = bbox
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2
        radius_km = max(
            _haversine_corner(center_lat, center_lon, lat_min, lon_min),
            _haversine_corner(center_lat, center_lon, lat_max, lon_max),
        )

        wait = self._poll_gate.seconds_until_ready(center_lat, center_lon)
        if wait > 0:
            logger.info("BarentsWatch: waiting %.0fs (relaunched within the poll interval)", wait)
            await asyncio.sleep(wait)

        async with aiohttp.ClientSession() as session:
            while not self._stop.is_set():
                if self._token is None or time.monotonic() > self._token_expires_at:
                    if not await self._fetch_token(session):
                        self._set_status(ProviderStatus.OFFLINE)
                        await asyncio.sleep(30)
                        continue

                try:
                    async with session.get(
                        POSITIONS_URL,
                        headers={"Authorization": f"bearer {self._token}"},
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        self._poll_gate.record_call(center_lat, center_lon)
                        if resp.status == 401:
                            self._token = None  # force refresh next loop
                            continue
                        if resp.status == 429:
                            self._set_status(ProviderStatus.RATE_LIMITED)
                            await asyncio.sleep(60)
                            continue
                        if resp.status != 200:
                            logger.warning("BarentsWatch positions request failed: %s", resp.status)
                            self._set_status(ProviderStatus.OFFLINE)
                            await asyncio.sleep(30)
                            continue

                        rows = await resp.json()
                        for row in rows or []:
                            vessel = self._parse(row)
                            if vessel is not None and is_within_radius(
                                center_lat, center_lon, vessel.latitude, vessel.longitude, radius_km
                            ):
                                self._emit(vessel)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("BarentsWatch poll error")
                    self._set_status(ProviderStatus.OFFLINE)

                await asyncio.sleep(POLL_INTERVAL_SECONDS)

    @staticmethod
    def _parse(row: dict) -> Vessel | None:
        mmsi = _get(row, "mmsi", "Mmsi")
        latitude = _get(row, "latitude", "Latitude")
        longitude = _get(row, "longitude", "Longitude")
        if mmsi is None or latitude is None or longitude is None:
            return None
        return Vessel(
            mmsi=str(mmsi),
            name=(_get(row, "name", "Name") or "").strip() or None,
            latitude=float(latitude),
            longitude=float(longitude),
            speed_over_ground=_get(row, "speedOverGround", "SpeedOverGround"),
            course_over_ground=_get(row, "courseOverGround", "CourseOverGround"),
            heading=_get(row, "trueHeading", "TrueHeading"),
            source="barentswatch",
        )


def _haversine_corner(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from utils.distance import haversine_km

    return haversine_km(lat1, lon1, lat2, lon2)
