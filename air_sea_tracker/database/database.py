"""SQLite database setup (SDR §21).

MVP database. Core tables: targets, current_positions,
position_history, vessels, aircraft, ports, airports, enrichment,
user_locations, alerts.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from platformdirs import user_data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    target_id       TEXT PRIMARY KEY,      -- ICAO24 or IMO/MMSI-derived stable id
    target_type     TEXT NOT NULL,         -- 'aircraft' | 'vessel'
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS current_positions (
    target_id       TEXT PRIMARY KEY REFERENCES targets(target_id),
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    altitude_m      REAL,
    speed           REAL,
    heading         REAL,
    destination     TEXT,
    source          TEXT,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS position_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id       TEXT NOT NULL REFERENCES targets(target_id),
    target_type     TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    altitude_m      REAL,
    speed           REAL,
    heading         REAL,
    destination     TEXT,
    source          TEXT
);
CREATE INDEX IF NOT EXISTS idx_position_history_target_ts
    ON position_history(target_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_position_history_latlon
    ON position_history(latitude, longitude);

CREATE TABLE IF NOT EXISTS vessels (
    mmsi            TEXT,
    imo             TEXT,
    target_id       TEXT PRIMARY KEY REFERENCES targets(target_id),
    name            TEXT,
    callsign        TEXT,
    ship_type       TEXT,
    flag            TEXT,
    ais_class       TEXT,
    length_m        REAL,
    width_m         REAL,
    draught_m       REAL,
    updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_vessels_mmsi ON vessels(mmsi);
CREATE INDEX IF NOT EXISTS idx_vessels_imo ON vessels(imo);

CREATE TABLE IF NOT EXISTS aircraft (
    icao24          TEXT PRIMARY KEY REFERENCES targets(target_id),
    registration    TEXT,
    callsign        TEXT,
    aircraft_type   TEXT,
    origin_country  TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS ports (
    port_id         TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    country         TEXT,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    geofence_radius_km REAL DEFAULT 5.0,
    unlocode        TEXT
);

CREATE TABLE IF NOT EXISTS airports (
    airport_id      TEXT PRIMARY KEY,   -- ICAO/IATA code
    name            TEXT NOT NULL,
    country         TEXT,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS enrichment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id       TEXT NOT NULL REFERENCES targets(target_id),
    field           TEXT NOT NULL,       -- e.g. 'registered_owner'
    value           TEXT,
    confidence      TEXT,                -- HIGH | MEDIUM | LOW | UNVERIFIED
    source          TEXT,
    retrieved_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_enrichment_target ON enrichment(target_id);

CREATE TABLE IF NOT EXISTS user_locations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    is_default      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    rule_json       TEXT NOT NULL,       -- serialized alert condition
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def default_db_path() -> Path:
    data_dir = Path(user_data_dir("AirSeaLiveTracker", "AirSeaTracker"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "air_sea_tracker.db"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or default_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    _apply_column_migrations(conn)
    conn.commit()

    from database.seed import seed_if_empty

    seed_if_empty(conn)
    return conn


def _apply_column_migrations(conn: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS doesn't add new columns to a table that
    already exists from an earlier version of SCHEMA — there's no formal
    migrations/ system yet (SDR §21), so new columns are added here,
    idempotently, until one exists."""
    try:
        conn.execute("ALTER TABLE vessels ADD COLUMN ais_class TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        conn.execute("ALTER TABLE ports ADD COLUMN unlocode TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
