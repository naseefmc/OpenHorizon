"""Typed row helpers for raw SQL results (database/database.py).

Kept distinct from models/ (domain objects used across GUI/services).
These map 1:1 onto SQLite table columns.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionRecord:
    target_id: str
    target_type: str
    timestamp: str
    latitude: float
    longitude: float
    altitude_m: float | None
    speed: float | None
    heading: float | None
    destination: str | None
    source: str | None
