"""Owns the live target set and reconciles collector updates (SDR §22, §24).

Applies duplicate/staleness filtering via the TTL cache (§26.1, §26.5)
and exposes the observer-relative nearby set to the GUI. This class
does no network I/O itself — collectors call ingest_* as messages
arrive on the asyncio loop.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import replace
from datetime import datetime, timezone

from database import repository
from models.aircraft import Aircraft
from models.vessel import Vessel
from services.cache_service import AIRCRAFT_TTL_SECONDS, VESSEL_TTL_SECONDS, LiveTargetCache
from services.geo_service import distance_and_bearing
from utils.distance import haversine_km
from utils.time_format import age_label
from utils.units import ms_to_kt, speed_label

# SDR §26.5: skip a history point unless position/speed/heading changed
# meaningfully or enough time passed — avoids a history row per packet
# for a target that's barely moving.
HISTORY_MIN_INTERVAL_SECONDS = 60.0
HISTORY_MIN_DISTANCE_KM = 0.1
HISTORY_MIN_HEADING_DELTA = 10.0
HISTORY_MIN_SPEED_DELTA = 2.0

# SDR §26.1's 600s default vessel TTL assumes a live push feed (AISStream)
# keeps re-refreshing well within that window. Poll-based sources have a
# real gap between updates — VesselAPI polls every 1800s (§1.1: rate-
# limited fallback) — so a flat 600s TTL guarantees every VesselAPI vessel
# "expires" and vanishes from the live cache, map, and every page reading
# it (Ports/Airports/Global) for the ~20 minutes between polls. Per-source
# overrides keep the tight default for genuinely fast sources while giving
# slow pollers enough TTL to survive to their own next update.
VESSEL_TTL_OVERRIDES = {"vesselapi": 2400}  # 1800s poll interval + margin


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
        self._last_history: dict[str, tuple[float, float, float | None, float | None, float]] = {}
        self._db_conn = db_conn
        if db_conn is not None:
            self._load_persisted(db_conn)

    @property
    def db_conn(self) -> sqlite3.Connection | None:
        return self._db_conn

    def all_vessels(self) -> list[Vessel]:
        return [t for t in self.cache.values() if isinstance(t, Vessel)]

    def all_aircraft(self) -> list[Aircraft]:
        return [t for t in self.cache.values() if isinstance(t, Aircraft)]

    def get_target(self, target_id: str) -> Aircraft | Vessel | None:
        for t in self.cache.values():
            if t.target_id == target_id:
                return t
        return None

    def _load_persisted(self, db_conn: sqlite3.Connection) -> None:
        """Restore last-known positions from disk on startup (SDR §26.6,
        §26.4) so the map/table aren't empty while providers reconnect,
        and quota-limited providers aren't the only way to repopulate
        data that was already known moments before the app was closed.
        Entries past their normal TTL are dropped rather than loaded."""
        now = datetime.now(timezone.utc)
        for vessel in repository.load_vessels(db_conn):
            ttl = VESSEL_TTL_OVERRIDES.get(vessel.source, VESSEL_TTL_SECONDS)
            remaining = self._remaining_ttl(vessel.last_update, now, ttl)
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

    def purge_old_history(self, retention_days: int) -> int:
        """SDR §8: default 7-day retention, configurable 1/3/7/30/unlimited."""
        if self._db_conn is None:
            return 0
        removed = repository.purge_history_older_than(self._db_conn, retention_days)
        self._db_conn.commit()
        return removed

    def track(self, target_id: str, since: datetime | None = None) -> list[dict]:
        if self._db_conn is None:
            return []
        return repository.load_track(self._db_conn, target_id, since)

    def known_targets(self) -> list[dict]:
        if self._db_conn is None:
            return []
        return repository.list_known_targets(self._db_conn)

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
        self._maybe_record_history(
            aircraft.target_id, "aircraft", aircraft.latitude, aircraft.longitude,
            aircraft.altitude_m, aircraft.ground_speed, aircraft.track, None, aircraft.source,
        )

    def update_vessel(self, vessel: Vessel) -> None:
        vessel.last_update = datetime.now(timezone.utc)
        key = f"vessel:{vessel.target_id}"
        existing = self.cache.get(key)
        if isinstance(existing, Vessel):
            # Merge so a PositionReport doesn't wipe fields only ShipStaticData
            # carries. Excludes None/"" only — NOT 0.0, which is a legitimate
            # value for course/heading (due north) and speed (stopped); with
            # providers now using None (not 0.0) as their own missing-data
            # sentinel, a real 0.0 here is trustworthy and must not be dropped.
            updates = {k: v for k, v in vessel.__dict__.items() if v not in (None, "")}
            vessel = replace(existing, **updates)
        self.cache.put(key, vessel, VESSEL_TTL_OVERRIDES.get(vessel.source, VESSEL_TTL_SECONDS))
        heading = vessel.effective_heading
        self._maybe_record_history(
            vessel.target_id, "vessel", vessel.latitude, vessel.longitude,
            None, vessel.speed_over_ground, heading, vessel.destination, vessel.source,
        )

    def _maybe_record_history(
        self, target_id: str, target_type: str, lat: float, lon: float,
        altitude_m: float | None, speed: float | None, heading: float | None,
        destination: str | None, source: str | None,
    ) -> None:
        if self._db_conn is None:
            return
        now = time.monotonic()
        prev = self._last_history.get(target_id)
        if prev is not None:
            prev_lat, prev_lon, prev_speed, prev_heading, prev_time = prev
            distance_km = haversine_km(prev_lat, prev_lon, lat, lon)
            speed_delta = abs((speed or 0) - (prev_speed or 0))
            heading_delta = abs((heading or 0) - (prev_heading or 0)) if heading is not None and prev_heading is not None else 0
            elapsed = now - prev_time
            if (
                elapsed < HISTORY_MIN_INTERVAL_SECONDS
                and distance_km < HISTORY_MIN_DISTANCE_KM
                and speed_delta < HISTORY_MIN_SPEED_DELTA
                and heading_delta < HISTORY_MIN_HEADING_DELTA
            ):
                return
        self._last_history[target_id] = (lat, lon, speed, heading, now)
        repository.insert_history_point(
            self._db_conn, target_id, target_type, lat, lon, altitude_m, speed, heading, destination, source
        )

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

    def all_targets(self, air_enabled: bool = True, sea_enabled: bool = True) -> list[Aircraft | Vessel]:
        """Unfiltered-by-observer set for Global Mode (SDR §7)."""
        results = []
        for target in self.cache.values():
            is_aircraft = isinstance(target, Aircraft)
            if is_aircraft and not air_enabled:
                continue
            if not is_aircraft and not sea_enabled:
                continue
            results.append(target)
        return results

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
                    "updated": age_label(target.last_update),
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
                    "updated": age_label(target.last_update),
                })
        return rows
