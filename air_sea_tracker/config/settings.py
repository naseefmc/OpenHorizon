"""Persistent, non-sensitive application settings (SDR §27, §27.1).

Backed by QSettings. Never store API credentials here — use
config/credentials.py instead.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings

ORG_NAME = "AirSeaTracker"
APP_NAME = "AirSeaLiveTracker"

# Default observer location used until the user sets/saves one (SDR §27.4).
DEFAULT_OBSERVER_LAT = 0.0
DEFAULT_OBSERVER_LON = 0.0


class Settings:
    def __init__(self) -> None:
        self._qsettings = QSettings(ORG_NAME, APP_NAME)

    def get(self, key: str, default: Any = None) -> Any:
        return self._qsettings.value(key, default)

    def set(self, key: str, value: Any) -> None:
        self._qsettings.setValue(key, value)
        self._qsettings.sync()

    # --- Convenience accessors for values persisted per SDR §27 ---

    @property
    def observer_lat(self) -> float | None:
        val = self.get("observer/lat", DEFAULT_OBSERVER_LAT)
        return float(val) if val is not None else None

    @property
    def observer_lon(self) -> float | None:
        val = self.get("observer/lon", DEFAULT_OBSERVER_LON)
        return float(val) if val is not None else None

    def set_observer_location(self, lat: float, lon: float) -> None:
        self.set("observer/lat", lat)
        self.set("observer/lon", lon)

    @property
    def radius_km(self) -> float:
        return float(self.get("observer/radius_km", 100.0))

    @radius_km.setter
    def radius_km(self, value: float) -> None:
        self.set("observer/radius_km", value)

    @property
    def theme(self) -> str:
        return str(self.get("appearance/theme", "system"))

    @theme.setter
    def theme(self, value: str) -> None:
        self.set("appearance/theme", value)

    @property
    def last_mode(self) -> str:
        return str(self.get("session/last_mode", "nearby"))

    @last_mode.setter
    def last_mode(self, value: str) -> None:
        self.set("session/last_mode", value)

    @property
    def history_retention_days(self) -> int:
        return int(self.get("history/retention_days", 7))

    @history_retention_days.setter
    def history_retention_days(self, value: int) -> None:
        self.set("history/retention_days", value)
