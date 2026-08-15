"""AISStream WebSocket provider (SDR §5, §22).

Push-based global feed via a long-lived WebSocket. AISStream accepts a
subscription even for an invalid/unactivated API key and never sends an
explicit auth error — it just never forwards packets — which is exactly
the silent-connection case the base class's LIVE/NO_DATA health rule
(AISProvider.check_silence) exists to surface, rather than the provider
looking permanently "connected" with nothing to show for it.
"""

from __future__ import annotations

import asyncio
import json
import logging

import websockets

from config.credentials import AISSTREAM_API_KEY, get_credential
from models.vessel import Vessel
from services.ais_providers.base import AISProvider, ProviderStatus

logger = logging.getLogger(__name__)

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"


class AISStreamProvider(AISProvider):
    name = "AISStream"

    def is_configured(self) -> bool:
        return bool(get_credential(AISSTREAM_API_KEY))

    async def _run(self, bbox: tuple[float, float, float, float]) -> None:
        api_key = get_credential(AISSTREAM_API_KEY)
        lat_min, lon_min, lat_max, lon_max = bbox
        bounding_boxes = [[[lat_min, lon_min], [lat_max, lon_max]]]

        while not self._stop.is_set():
            try:
                async with websockets.connect(AISSTREAM_URL) as ws:
                    await ws.send(json.dumps({"APIKey": api_key, "BoundingBoxes": bounding_boxes}))
                    async for message in ws:
                        if self._stop.is_set():
                            break
                        vessel = self._parse(json.loads(message))
                        if vessel is not None:
                            self._emit(vessel)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AISStream connection error; reconnecting in 5s")
                self._set_status(ProviderStatus.OFFLINE)
                await asyncio.sleep(5)

    @staticmethod
    def _parse(payload: dict) -> Vessel | None:
        meta = payload.get("MetaData") or {}
        mmsi = meta.get("MMSI")
        if mmsi is None:
            return None

        message_type = payload.get("MessageType")
        body = (payload.get("Message") or {}).get(message_type) or {}

        vessel = Vessel(
            mmsi=str(mmsi),
            name=(meta.get("ShipName") or "").strip() or None,
            latitude=meta.get("latitude") or 0.0,
            longitude=meta.get("longitude") or 0.0,
            source="aisstream",
        )

        if message_type == "PositionReport":
            vessel.ais_class = "A"
            vessel.speed_over_ground = body.get("Sog")
            vessel.course_over_ground = body.get("Cog")
            vessel.heading = _true_heading(body.get("TrueHeading"))
            vessel.navigation_status = body.get("NavigationalStatus")
        elif message_type == "StandardClassBPositionReport":
            # Lower-power transceivers (leisure/small craft): same position
            # fields as PositionReport, but no NavigationalStatus field.
            vessel.ais_class = "B"
            vessel.speed_over_ground = body.get("Sog")
            vessel.course_over_ground = body.get("Cog")
            vessel.heading = _true_heading(body.get("TrueHeading"))
        elif message_type == "ShipStaticData":
            imo = body.get("ImoNumber")
            vessel.imo = str(imo) if imo else None
            vessel.callsign = body.get("CallSign")
            vessel.ship_type = str(body.get("Type")) if body.get("Type") is not None else None
            vessel.destination = body.get("Destination")
            vessel.eta = body.get("Eta")
            dim = body.get("Dimension") or {}
            if dim:
                a, b, c, d = dim.get("A", 0), dim.get("B", 0), dim.get("C", 0), dim.get("D", 0)
                vessel.length_m = (a + b) or None
                vessel.width_m = (c + d) or None
        else:
            return None  # other message types not yet mapped

        return vessel


def _true_heading(value) -> float | None:
    # 511 is the AIS sentinel for "heading not available" (both Class A and B).
    return value if value is not None and value != 511 else None
