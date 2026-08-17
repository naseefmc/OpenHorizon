"""Write-through persistence for the live target cache (SDR §21, §26.4).

TargetManager's in-memory LiveTargetCache is wiped on every restart,
which meant relaunching the app always started from zero and, for
quota/rate-limited AIS providers, re-triggered an immediate API call
just to repopulate what was already known moments earlier. These
functions let TargetManager flush its current cache to SQLite on a
batched interval and reload it on startup, restoring last-known
positions instantly while the live providers reconnect in the
background.

Writes are batched (called periodically, not per-packet) per SDR §26.4
rather than firing on every single position update.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from models.aircraft import Aircraft
from models.vessel import Vessel


def save_vessel(conn: sqlite3.Connection, vessel: Vessel) -> None:
    updated_at = (vessel.last_update or datetime.now(timezone.utc)).isoformat()
    conn.execute(
        "INSERT INTO targets (target_id, target_type) VALUES (?, 'vessel') "
        "ON CONFLICT(target_id) DO NOTHING",
        (vessel.target_id,),
    )
    conn.execute(
        """INSERT INTO current_positions
               (target_id, latitude, longitude, speed, heading, destination, source, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(target_id) DO UPDATE SET
               latitude=excluded.latitude, longitude=excluded.longitude,
               speed=excluded.speed, heading=excluded.heading,
               destination=excluded.destination, source=excluded.source,
               updated_at=excluded.updated_at""",
        (
            vessel.target_id, vessel.latitude, vessel.longitude,
            vessel.speed_over_ground, vessel.effective_heading,
            vessel.destination, vessel.source, updated_at,
        ),
    )
    conn.execute(
        """INSERT INTO vessels
               (mmsi, imo, target_id, name, callsign, ship_type, flag, ais_class, length_m, width_m, draught_m, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(target_id) DO UPDATE SET
               mmsi=excluded.mmsi, imo=excluded.imo,
               name=COALESCE(NULLIF(excluded.name, ''), vessels.name),
               callsign=COALESCE(excluded.callsign, vessels.callsign),
               ship_type=COALESCE(excluded.ship_type, vessels.ship_type),
               flag=COALESCE(excluded.flag, vessels.flag),
               ais_class=COALESCE(excluded.ais_class, vessels.ais_class),
               length_m=COALESCE(excluded.length_m, vessels.length_m),
               width_m=COALESCE(excluded.width_m, vessels.width_m),
               draught_m=COALESCE(excluded.draught_m, vessels.draught_m),
               updated_at=excluded.updated_at""",
        (
            vessel.mmsi, vessel.imo, vessel.target_id, vessel.name, vessel.callsign,
            vessel.ship_type, vessel.flag, vessel.ais_class,
            vessel.length_m, vessel.width_m, vessel.draught_m, updated_at,
        ),
    )


def save_aircraft(conn: sqlite3.Connection, aircraft: Aircraft) -> None:
    updated_at = (aircraft.last_update or datetime.now(timezone.utc)).isoformat()
    conn.execute(
        "INSERT INTO targets (target_id, target_type) VALUES (?, 'aircraft') "
        "ON CONFLICT(target_id) DO NOTHING",
        (aircraft.target_id,),
    )
    conn.execute(
        """INSERT INTO current_positions
               (target_id, latitude, longitude, altitude_m, speed, heading, source, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(target_id) DO UPDATE SET
               latitude=excluded.latitude, longitude=excluded.longitude,
               altitude_m=excluded.altitude_m, speed=excluded.speed, heading=excluded.heading,
               source=excluded.source, updated_at=excluded.updated_at""",
        (
            aircraft.target_id, aircraft.latitude, aircraft.longitude, aircraft.altitude_m,
            aircraft.ground_speed, aircraft.track, aircraft.source, updated_at,
        ),
    )
    conn.execute(
        """INSERT INTO aircraft (icao24, registration, callsign, aircraft_type, origin_country, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(icao24) DO UPDATE SET
               registration=COALESCE(excluded.registration, aircraft.registration),
               callsign=COALESCE(excluded.callsign, aircraft.callsign),
               aircraft_type=COALESCE(excluded.aircraft_type, aircraft.aircraft_type),
               origin_country=COALESCE(excluded.origin_country, aircraft.origin_country),
               updated_at=excluded.updated_at""",
        (aircraft.icao24, aircraft.registration, aircraft.callsign, aircraft.aircraft_type,
         aircraft.origin_country, updated_at),
    )


def load_vessels(conn: sqlite3.Connection) -> list[Vessel]:
    rows = conn.execute(
        """SELECT v.mmsi, v.imo, v.name, v.callsign, v.ship_type, v.flag, v.ais_class,
                  v.length_m, v.width_m, v.draught_m,
                  cp.latitude, cp.longitude, cp.speed, cp.heading, cp.destination, cp.source, cp.updated_at
           FROM vessels v JOIN current_positions cp ON cp.target_id = v.target_id"""
    ).fetchall()
    vessels = []
    for row in rows:
        vessels.append(Vessel(
            mmsi=row["mmsi"] or "",
            imo=row["imo"],
            name=row["name"],
            callsign=row["callsign"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            speed_over_ground=row["speed"],
            heading=row["heading"],
            destination=row["destination"],
            ship_type=row["ship_type"],
            flag=row["flag"],
            ais_class=row["ais_class"],
            length_m=row["length_m"],
            width_m=row["width_m"],
            draught_m=row["draught_m"],
            last_update=_parse_ts(row["updated_at"]),
            source=row["source"] or "cache",
        ))
    return [v for v in vessels if v.mmsi]


def load_aircraft(conn: sqlite3.Connection) -> list[Aircraft]:
    rows = conn.execute(
        """SELECT a.icao24, a.registration, a.callsign, a.aircraft_type, a.origin_country,
                  cp.latitude, cp.longitude, cp.altitude_m, cp.speed, cp.heading, cp.source, cp.updated_at
           FROM aircraft a JOIN current_positions cp ON cp.target_id = a.icao24"""
    ).fetchall()
    result = []
    for row in rows:
        result.append(Aircraft(
            icao24=row["icao24"],
            callsign=row["callsign"],
            registration=row["registration"],
            aircraft_type=row["aircraft_type"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            altitude_m=row["altitude_m"],
            ground_speed=row["speed"],
            track=row["heading"],
            origin_country=row["origin_country"],
            last_update=_parse_ts(row["updated_at"]),
            source=row["source"] or "cache",
        ))
    return result


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# --- position_history (SDR §8: track history, §26.5: duplicate filtering) ---

def insert_history_point(
    conn: sqlite3.Connection,
    target_id: str,
    target_type: str,
    latitude: float,
    longitude: float,
    altitude_m: float | None,
    speed: float | None,
    heading: float | None,
    destination: str | None,
    source: str | None,
) -> None:
    conn.execute(
        "INSERT INTO targets (target_id, target_type) VALUES (?, ?) ON CONFLICT(target_id) DO NOTHING",
        (target_id, target_type),
    )
    conn.execute(
        """INSERT INTO position_history
               (target_id, target_type, timestamp, latitude, longitude, altitude_m, speed, heading, destination, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            target_id, target_type, datetime.now(timezone.utc).isoformat(),
            latitude, longitude, altitude_m, speed, heading, destination, source,
        ),
    )


def purge_history_older_than(conn: sqlite3.Connection, retention_days: int) -> int:
    """Default retention 7 days, configurable 1/3/7/30/unlimited (SDR §8).
    Unlimited retention is represented by retention_days <= 0 — skip purging."""
    if retention_days <= 0:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    cur = conn.execute("DELETE FROM position_history WHERE timestamp < ?", (cutoff,))
    return cur.rowcount


def list_known_targets(conn: sqlite3.Connection) -> list[dict]:
    """Distinct targets with history, for the History Mode picker (SDR §8).

    last_seen is the most recent position_history timestamp for the target
    (not current_positions.updated_at) so it reflects an actual logged
    detection and survives even if the target has since expired out of the
    live cache."""
    rows = conn.execute(
        """SELECT DISTINCT t.target_id, t.target_type,
                  COALESCE(v.name, v.mmsi, a.registration, a.callsign, t.target_id) AS name,
                  (SELECT MAX(h.timestamp) FROM position_history h WHERE h.target_id = t.target_id) AS last_seen
           FROM targets t
           LEFT JOIN vessels v ON v.target_id = t.target_id
           LEFT JOIN aircraft a ON a.icao24 = t.target_id
           WHERE EXISTS (SELECT 1 FROM position_history h WHERE h.target_id = t.target_id)
           ORDER BY last_seen DESC"""
    ).fetchall()
    return [
        {"target_id": r["target_id"], "target_type": r["target_type"], "name": r["name"], "last_seen": r["last_seen"]}
        for r in rows
    ]


def load_track(conn: sqlite3.Connection, target_id: str, since: datetime | None = None) -> list[dict]:
    """Returns [{lat, lon, timestamp, speed, heading, altitude_m}, ...] oldest first."""
    if since is not None:
        rows = conn.execute(
            "SELECT * FROM position_history WHERE target_id = ? AND timestamp >= ? ORDER BY timestamp",
            (target_id, since.isoformat()),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM position_history WHERE target_id = ? ORDER BY timestamp", (target_id,)
        ).fetchall()
    return [
        {
            "lat": r["latitude"], "lon": r["longitude"], "timestamp": r["timestamp"],
            "speed": r["speed"], "heading": r["heading"], "altitude_m": r["altitude_m"],
        }
        for r in rows
    ]


def track_stats(points: list[dict]) -> dict:
    """Distance travelled, max/avg speed, time stationary (SDR §8)."""
    from utils.distance import haversine_km

    if not points:
        return {"distance_km": 0.0, "max_speed": None, "avg_speed": None, "stationary_seconds": 0}

    distance_km = 0.0
    for a, b in zip(points, points[1:]):
        distance_km += haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])

    speeds = [p["speed"] for p in points if p["speed"] is not None]
    stationary_seconds = 0
    for a, b in zip(points, points[1:]):
        if (a["speed"] or 0) < 0.5:  # ~stopped, in knots
            ta, tb = _parse_ts(a["timestamp"]), _parse_ts(b["timestamp"])
            if ta and tb:
                stationary_seconds += int((tb - ta).total_seconds())

    return {
        "distance_km": distance_km,
        "max_speed": max(speeds) if speeds else None,
        "avg_speed": (sum(speeds) / len(speeds)) if speeds else None,
        "stationary_seconds": stationary_seconds,
    }
