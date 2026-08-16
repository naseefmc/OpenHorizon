"""One-time seed of the ports/airports tables from bundled CSVs (SDR §9-11).

Sources (both free/public-domain, verified before bundling — not guessed):
  - data/airports_seed.csv: OurAirports.com (CC0/Public Domain), filtered
    to large_airport + medium_airport (~5.3k of their ~85k rows — small
    strips/heliports excluded as out of scope for this app).
  - data/ports_seed.csv: NGA World Port Index / Pub 150 (US government,
    public domain), ~3.8k major world ports with surveyed coordinates.

Only runs if the corresponding table is empty, so it's safe to call on
every startup.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def seed_if_empty(conn: sqlite3.Connection) -> None:
    _seed_airports(conn)
    _seed_ports(conn)
    conn.commit()


def _seed_airports(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM airports").fetchone()[0]
    if count > 0:
        return
    path = DATA_DIR / "airports_seed.csv"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        rows = [
            (r["airport_id"], r["name"], r["country"], float(r["latitude"]), float(r["longitude"]))
            for r in csv.DictReader(f)
        ]
    conn.executemany(
        "INSERT OR IGNORE INTO airports (airport_id, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
        rows,
    )


def _seed_ports(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM ports").fetchone()[0]
    if count > 0:
        return
    path = DATA_DIR / "ports_seed.csv"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        rows = [
            (r["port_id"], r["name"], r["country"], float(r["latitude"]), float(r["longitude"]))
            for r in csv.DictReader(f)
        ]
    conn.executemany(
        "INSERT OR IGNORE INTO ports (port_id, name, country, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
