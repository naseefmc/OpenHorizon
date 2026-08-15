"""Nearest-port search and port traffic/geofencing (SDR §9-10, Phase 3)."""

from __future__ import annotations

from models.port import Port


def nearest_ports(observer_lat: float, observer_lon: float, count: int = 5) -> list[Port]:
    # TODO(Phase 3): query ports table, order by geo_service distance
    raise NotImplementedError
