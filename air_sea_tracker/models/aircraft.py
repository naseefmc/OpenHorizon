"""Aircraft domain model (SDR §6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Aircraft:
    icao24: str
    callsign: str | None = None
    registration: str | None = None
    aircraft_type: str | None = None
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: float | None = None
    ground_speed: float | None = None
    vertical_rate: float | None = None
    track: float | None = None
    squawk: str | None = None
    origin_country: str | None = None
    on_ground: bool = False
    last_update: datetime | None = None
    source: str = "opensky"

    @property
    def target_id(self) -> str:
        return self.icao24
