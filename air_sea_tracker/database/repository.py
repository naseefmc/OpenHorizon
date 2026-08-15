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
from datetime import datetime, timezone

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
            vessel.speed_over_ground, vessel.course_over_ground or vessel.heading,
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
