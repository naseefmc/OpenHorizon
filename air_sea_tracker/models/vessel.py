"""Vessel domain model (SDR §5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Vessel:
    mmsi: str
    imo: str | None = None
    name: str | None = None
    callsign: str | None = None
    latitude: float = 0.0
    longitude: float = 0.0
    speed_over_ground: float | None = None
    course_over_ground: float | None = None
    heading: float | None = None
    navigation_status: str | None = None
    destination: str | None = None
    eta: str | None = None
    ship_type: str | None = None
    draught_m: float | None = None
    length_m: float | None = None
    width_m: float | None = None
    flag: str | None = None
    ais_class: str | None = None  # "A" (mandatory, larger commercial) or "B" (lower-power, leisure/small craft)
    last_update: datetime | None = None
    source: str = "aisstream"

    @property
    def target_id(self) -> str:
        # IMO is the stable identifier where known (SDR §21); MMSI as fallback.
        return f"imo:{self.imo}" if self.imo else f"mmsi:{self.mmsi}"
