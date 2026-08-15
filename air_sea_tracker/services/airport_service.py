"""Nearest-airport search and observed-vs-scheduled traffic (SDR §9, §11, Phase 3)."""

from __future__ import annotations

from models.airport import Airport


def nearest_airports(observer_lat: float, observer_lon: float, count: int = 5) -> list[Airport]:
    # TODO(Phase 3): query airports table, order by geo_service distance
    raise NotImplementedError
