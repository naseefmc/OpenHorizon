"""Owns the live target set and reconciles collector updates (SDR §22, §24).

Applies duplicate/staleness filtering via the TTL cache (§26.1, §26.5)
and exposes the observer-relative nearby set to the GUI. This class
does no network I/O itself — collectors call ingest_* as messages
arrive on the asyncio loop.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timezone

from database import repository
from models.aircraft import Aircraft
from models.vessel import Vessel
from services.cache_service import AIRCRAFT_TTL_SECONDS, VESSEL_TTL_SECONDS, LiveTargetCache
from services.geo_service import distance_and_bearing
from utils.units import ms_to_kt, speed_label


class TargetManager:
    def __init__(self, db_conn: sqlite3.Connection | None = None) -> None:
        self.cache = LiveTargetCache()
        self.observer_lat: float | None = None
        self.observer_lon: float | None = None
        self.radius_km: float = 100.0
        self.air_enabled: bool = True
        self.sea_enabled: bool = True
        self.class_a_enabled: bool = True
        self.class_b_enabled: bool = True
        self._db_conn = db_conn
        if db_conn is not None:
            self._load_persisted(db_conn)

    def _load_persisted(self, db_conn: sqlite3.Connection) -> None:
        """Restore last-known positions from disk on startup (SDR §26.6,
        §26.4) so the map/table aren't empty while providers reconnect,
        and quota-limited providers aren't the only way to repopulate
        data that was already known moments before the app was closed.
        Entries past their normal TTL are dropped rather than loaded."""
        now = datetime.now(timezone.utc)
        for vessel in repository.load_vessels(db_conn):
            remaining = self._remaining_ttl(vessel.last_update, now, VESSEL_TTL_SECONDS)
            if remaining > 0:
                self.cache.put(f"vessel:{vessel.target_id}", vessel, remaining)
        for aircraft in repository.load_aircraft(db_conn):
            remaining = self._remaining_ttl(aircraft.last_update, now, AIRCRAFT_TTL_SECONDS)
            if remaining > 0:
                self.cache.put(f"aircraft:{aircraft.icao24}", aircraft, remaining)

    @staticmethod
    def _remaining_ttl(last_update: datetime | None, now: datetime, ttl_seconds: float) -> float:
        if last_update is None:
            return 0.0
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)
        return ttl_seconds - (now - last_update).total_seconds()

    def flush_to_db(self) -> None:
        """Batched write-through to SQLite (SDR §26.4) — called periodically,
        not per-packet, so quota-limited providers don't need to be
        re-polled just because the app was relaunched shortly after."""
        if self._db_conn is None:
            return
        for target in self.cache.values():
            if isinstance(target, Aircraft):
                repository.save_aircraft(self._db_conn, target)
            else:
                repository.save_vessel(self._db_conn, target)
        self._db_conn.commit()

    # --- observer/filter state (driven by ObserverPanel) ---

    def set_observer(self, lat: float, lon: float) -> None:
        self.observer_lat = lat
        self.observer_lon = lon

    def set_radius(self, radius_km: float) -> None:
        self.radius_km = radius_km

    def set_filters(self, air_enabled: bool, sea_enabled: bool) -> None:
        self.air_enabled = air_enabled
        self.sea_enabled = sea_enabled

    def set_vessel_class_filter(self, class_a_enabled: bool, class_b_enabled: bool) -> None:
        self.class_a_enabled = class_a_enabled
        self.class_b_enabled = class_b_enabled

    # --- ingest from collectors ---

    def update_aircraft(self, aircraft: Aircraft) -> None:
        aircraft.last_update = datetime.now(timezone.utc)
        self.cache.put(f"aircraft:{aircraft.icao24}", aircraft, AIRCRAFT_TTL_SECONDS)

    def update_vessel(self, vessel: Vessel) -> None:
        vessel.last_update = datetime.now(timezone.utc)
        key = f"vessel:{vessel.target_id}"
        existing = self.cache.get(key)
        if isinstance(existing, Vessel):
            # Merge so a PositionReport doesn't wipe fields only ShipStaticData carries.
            updates = {k: v for k, v in vessel.__dict__.items() if v not in (None, "", 0.0)}
            vessel = replace(existing, **updates)
        self.cache.put(key, vessel, VESSEL_TTL_SECONDS)

    def ingest_opensky_states(self, payload: dict) -> None:
        """Parses OpenSky /states/all response (SDR §6)."""
        for state in payload.get("states") or []:
            icao24 = state[0]
            longitude, latitude = state[5], state[6]
            if icao24 is None or latitude is None or longitude is None:
                continue
            aircraft = Aircraft(
                icao24=icao24,
                callsign=(state[1] or "").strip() or None,
                latitude=latitude,
                longitude=longitude,
                altitude_m=state[7] if state[7] is not None else state[13],
                # OpenSky's "velocity" field is m/s; convert to knots here so
                # ground_speed is in the same unit as Vessel.speed_over_ground
                # (both AIS-standard knots) rather than mixed units reaching the GUI.
                ground_speed=ms_to_kt(state[9]) if state[9] is not None else None,
                vertical_rate=state[11],
                track=state[10],
                squawk=state[14],
                origin_country=state[2],
                on_ground=bool(state[8]),
            )
            self.update_aircraft(aircraft)

    # --- query for GUI ---

    def nearby(self) -> list[tuple[Aircraft | Vessel, float, float]]:
        """Returns (target, distance_km, bearing_deg) within radius, nearest first."""
        if self.observer_lat is None or self.observer_lon is None:
            return []

        results: list[tuple[Aircraft | Vessel, float, float]] = []
        for target in self.cache.values():
            is_aircraft = isinstance(target, Aircraft)
            if is_aircraft and not self.air_enabled:
                continue
            if not is_aircraft and not self.sea_enabled:
                continue
            if not is_aircraft:
                # Unknown class (providers that don't report it) always shows.
                if target.ais_class == "A" and not self.class_a_enabled:
                    continue
                if target.ais_class == "B" and not self.class_b_enabled:
                    continue

            distance_km, bearing = distance_and_bearing(
                self.observer_lat, self.observer_lon, target.latitude, target.longitude
            )
            if distance_km <= self.radius_km:
                results.append((target, distance_km, bearing))

        results.sort(key=lambda r: r[1])
        return results

    def table_rows(self) -> list[dict]:
        rows = []
        for target, distance_km, _bearing in self.nearby():
            is_aircraft = isinstance(target, Aircraft)
            if is_aircraft:
                rows.append({
                    "target_id": target.target_id,
                    "type": "Aircraft",
                    "name": target.callsign or target.registration or target.icao24,
                    "distance": f"{distance_km:.1f} km",
                    "speed": speed_label(target.ground_speed),
                    "heading": f"{target.track:.0f}°" if target.track is not None else "—",
                    "altitude_status": (
                        "On ground" if target.on_ground
                        else (f"{target.altitude_m:.0f} m" if target.altitude_m is not None else "—")
                    ),
                    "destination": "—",
                    "updated": self._age_label(target.last_update),
                })
            else:
                rows.append({
                    "target_id": target.target_id,
                    "type": f"Vessel ({target.ais_class})" if target.ais_class else "Vessel",
                    "name": target.name or target.mmsi,
                    "distance": f"{distance_km:.1f} km",
                    "speed": speed_label(target.speed_over_ground),
                    "heading": (
                        f"{target.course_over_ground:.0f}°" if target.course_over_ground is not None
                        else (f"{target.heading:.0f}°" if target.heading is not None else "—")
                    ),
                    "altitude_status": target.navigation_status or "—",
                    "destination": target.destination or "—",
                    "updated": self._age_label(target.last_update),
                })
        return rows

    @staticmethod
    def _age_label(last_update: datetime | None) -> str:
        if last_update is None:
            return "—"
        now = datetime.now(timezone.utc)
        ts = last_update if last_update.tzinfo else last_update.replace(tzinfo=timezone.utc)
        age = (now - ts).total_seconds()
        if age < 5:
            return "live"
        if age < 60:
            return f"{int(age)}s ago"
        return f"{int(age // 60)}m ago"
