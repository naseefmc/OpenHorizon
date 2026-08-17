"""Port domain model (SDR §9-§10)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Port:
    port_id: str
    name: str
    country: str | None = None
    latitude: float = 0.0
    longitude: float = 0.0
    geofence_radius_km: float = 5.0
    unlocode: str | None = None  # UN/LOCODE, user-entered (SDR has no source for this) — powers VesselAPI inbound lookup
