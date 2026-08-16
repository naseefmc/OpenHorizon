"""Nearest-airport search and observed-vs-scheduled traffic (SDR §9, §11, Phase 3)."""

from __future__ import annotations

import sqlite3

from models.airport import Airport
from utils.distance import haversine_km


def nearest_airports(
    conn: sqlite3.Connection, observer_lat: float, observer_lon: float, count: int = 5
) -> list[Airport]:
    rows = conn.execute("SELECT * FROM airports").fetchall()
    scored = []
    for r in rows:
        distance_km = haversine_km(observer_lat, observer_lon, r["latitude"], r["longitude"])
        scored.append((distance_km, r))
    scored.sort(key=lambda t: t[0])
    return [
        Airport(
            airport_id=r["airport_id"], name=r["name"], country=r["country"],
            latitude=r["latitude"], longitude=r["longitude"],
        )
        for _distance, r in scored[:count]
    ]
