"""Airport domain model (SDR §9, §11)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Airport:
    airport_id: str  # ICAO/IATA code
    name: str
    country: str | None = None
    latitude: float = 0.0
    longitude: float = 0.0
