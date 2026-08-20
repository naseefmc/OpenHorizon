"""Spatial TTL cache for ocean/environment provider results (Ocean & Environment SDR §17).

Keys combine a data-kind tag with coordinates rounded to 3 decimal
places (~110m at the equator) so repeated clicks within roughly the
same spot reuse cached data instead of re-hitting external providers.
Same shape as services/cache_service.LiveTargetCache, but keyed
spatially rather than by target id, per SDR §17's suggested key.

Backed by a SQLite file (same `platformdirs` user-data location as the
main app database — see database/database.py) rather than an in-memory
dict, so cached results survive an app restart: re-opening the app and
re-clicking a point you looked at yesterday can still be served from
disk instead of re-querying the provider, as long as the entry's TTL
hasn't expired. Values are arbitrary provider result objects (nested
dataclasses like SourcedValue/WaveData/SpeciesResult), so entries are
pickled — this is our own cache file, not untrusted external input.
"""

from __future__ import annotations

import pickle
import sqlite3
import time
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

# Suggested cache lifetimes (SDR §17 table), in seconds.
BATHYMETRY_TTL_SECONDS = 30 * 24 * 3600  # "days/months"
COASTLINE_TTL_SECONDS = 7 * 24 * 3600
WATER_BODY_TTL_SECONDS = 7 * 24 * 3600  # static-ish gazetteer lookup, same bucket as coastline
SST_TTL_SECONDS = 3 * 3600  # "1-6 hours"
WAVES_TTL_SECONDS = 2 * 3600  # "1-3 hours"
CURRENTS_TTL_SECONDS = 2 * 3600
WIND_TTL_SECONDS = 45 * 60  # "30-60 minutes"
RAIN_CLOUDS_TTL_SECONDS = 45 * 60
SPECIES_TTL_SECONDS = 24 * 3600
SALINITY_TTL_SECONDS = 3 * 3600  # SMOS is a daily composite, same bucket as SST
SEA_LEVEL_TTL_SECONDS = 3 * 3600  # altimetry is also ~daily
FISHING_ACTIVITY_TTL_SECONDS = 6 * 3600  # GFW's own pipeline is already days-delayed
MPA_TTL_SECONDS = 30 * 24 * 3600  # WDPA is updated monthly

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache_entries (
    key         TEXT PRIMARY KEY,
    value       BLOB NOT NULL,
    expires_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_entries_expires ON cache_entries(expires_at);
"""


def default_cache_db_path() -> Path:
    data_dir = Path(user_data_dir("AirSeaLiveTracker", "AirSeaTracker"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "ocean_cache.db"


class OceanCache:
    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or default_cache_db_path()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self.purge_expired()

    @staticmethod
    def spatial_key(kind: str, lat: float, lon: float, extra: str = "") -> str:
        return f"{kind}:{round(lat, 3)}:{round(lon, 3)}:{extra}"

    def get(self, key: str) -> Any | None:
        row = self._conn.execute(
            "SELECT value, expires_at FROM cache_entries WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value_blob, expires_at = row
        if time.time() > expires_at:
            self._conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            self._conn.commit()
            return None
        return pickle.loads(value_blob)

    def put(self, key: str, value: Any, ttl_seconds: float) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO cache_entries (key, value, expires_at) VALUES (?, ?, ?)",
            (key, pickle.dumps(value), time.time() + ttl_seconds),
        )
        self._conn.commit()

    def purge_expired(self) -> int:
        cursor = self._conn.execute("DELETE FROM cache_entries WHERE expires_at < ?", (time.time(),))
        self._conn.commit()
        return cursor.rowcount

    def __len__(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
