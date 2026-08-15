"""AISHub REST provider (SDR §5, §22).

Global coverage, but access is granted per AISHub's reciprocal-data
policy: a username is only issued/kept active if the account also
contributes a terrestrial AIS feed to the network, so this stays
DISABLED until a username is configured — it is not a plain sign-up
key like AISStream's. The service also hard-throttles at one request
per minute (undocumented consequence: it silently returns nothing if
polled faster, not an error), so the poll interval here is fixed at
60s and must not be lowered.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from config.credentials import AISHUB_USERNAME, get_credential
from models.vessel import Vessel
from services.ais_providers.base import AISProvider, ProviderStatus
from services.rate_limiter import PersistentPollGate

logger = logging.getLogger(__name__)

POSITIONS_URL = "https://data.aishub.net/ws.php"
POLL_INTERVAL_SECONDS = 60  # AISHub: do not poll more than once/minute


class AISHubProvider(AISProvider):
    name = "AISHub"

    def __init__(self) -> None:
        super().__init__()
        self._poll_gate = PersistentPollGate(name="aishub", min_interval_seconds=POLL_INTERVAL_SECONDS)

    def is_configured(self) -> bool:
        return bool(get_credential(AISHUB_USERNAME))

    async def _run(self, bbox: tuple[float, float, float, float]) -> None:
        lat_min, lon_min, lat_max, lon_max = bbox
        center_lat, center_lon = (lat_min + lat_max) / 2, (lon_min + lon_max) / 2

        wait = self._poll_gate.seconds_until_ready(center_lat, center_lon)
        if wait > 0:
            logger.info("AISHub: waiting %.0fs (relaunched within the poll interval)", wait)
            await asyncio.sleep(wait)

        username = get_credential(AISHUB_USERNAME)
        params = {
            "username": username,
            "format": "1",
            "output": "json",
            "compress": "0",
            "latmin": str(lat_min),
            "latmax": str(lat_max),
            "lonmin": str(lon_min),
            "lonmax": str(lon_max),
        }

        async with aiohttp.ClientSession() as session:
            while not self._stop.is_set():
                try:
                    async with session.get(
                        POSITIONS_URL, params=params, timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        self._poll_gate.record_call(center_lat, center_lon)
                        if resp.status != 200:
                            logger.warning("AISHub request failed: %s", resp.status)
                            self._set_status(ProviderStatus.OFFLINE)
                        else:
                            payload = await resp.json()
                            self._handle_payload(payload)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("AISHub poll error")
                    self._set_status(ProviderStatus.OFFLINE)

                await asyncio.sleep(POLL_INTERVAL_SECONDS)

    def _handle_payload(self, payload: list) -> None:
        # [{"ERROR": bool, "RECORDS": n, ...}, [ {vessel}, ... ]]
        if not isinstance(payload, list) or len(payload) < 2:
            logger.warning("AISHub returned an unexpected payload shape")
            return
        status, records = payload[0], payload[1]
        if status.get("ERROR"):
            logger.warning("AISHub error response: %s", status)
            self._set_status(ProviderStatus.OFFLINE)
            return
        for row in records or []:
            vessel = self._parse(row)
            if vessel is not None:
                self._emit(vessel)

    @staticmethod
    def _parse(row: dict) -> Vessel | None:
        mmsi = row.get("MMSI")
        latitude, longitude = row.get("LATITUDE"), row.get("LONGITUDE")
        if mmsi is None or latitude is None or longitude is None:
            return None
        a, b, c, d = row.get("A", 0), row.get("B", 0), row.get("C", 0), row.get("D", 0)
        imo = row.get("IMO")
        return Vessel(
            mmsi=str(mmsi),
            imo=str(imo) if imo else None,
            name=(row.get("NAME") or "").strip() or None,
            callsign=row.get("CALLSIGN") or None,
            latitude=float(latitude),
            longitude=float(longitude),
            speed_over_ground=row.get("SOG"),
            course_over_ground=row.get("COG"),
            heading=row.get("HEADING"),
            navigation_status=str(row.get("NAVSTAT")) if row.get("NAVSTAT") is not None else None,
            destination=row.get("DEST") or None,
            eta=row.get("ETA") or None,
            ship_type=str(row.get("TYPE")) if row.get("TYPE") is not None else None,
            draught_m=row.get("DRAUGHT"),
            length_m=(a + b) or None,
            width_m=(c + d) or None,
            source="aishub",
        )
