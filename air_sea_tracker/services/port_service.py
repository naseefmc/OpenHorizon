"""Nearest-port search and port traffic/geofencing (SDR §9-10, Phase 3)."""

from __future__ import annotations

import sqlite3

from models.port import Port
from utils.distance import haversine_km


def nearest_ports(conn: sqlite3.Connection, observer_lat: float, observer_lon: float, count: int = 5) -> list[Port]:
    rows = conn.execute("SELECT * FROM ports").fetchall()
    scored = []
    for r in rows:
        distance_km = haversine_km(observer_lat, observer_lon, r["latitude"], r["longitude"])
        scored.append((distance_km, r))
    scored.sort(key=lambda t: t[0])
    return [
        Port(
            port_id=r["port_id"], name=r["name"], country=r["country"],
            latitude=r["latitude"], longitude=r["longitude"],
            geofence_radius_km=r["geofence_radius_km"] or 5.0,
        )
        for _distance, r in scored[:count]
    ]
