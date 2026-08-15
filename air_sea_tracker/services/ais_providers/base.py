"""Base class for a pluggable AIS provider with silence-based health tracking."""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Callable

from models.vessel import Vessel


class ProviderStatus(Enum):
    DISABLED = "disabled"  # not configured (missing credentials)
    CONNECTING = "connecting"
    LIVE = "live"  # connected and has delivered a packet within the health window
    NO_DATA = "no_data"  # connected/subscribed but silent past the health window
    RATE_LIMITED = "rate_limited"
    OFFLINE = "offline"  # connection or auth error


class AISProvider:
    """A single AIS data source.

    Subclasses implement `_run(on_vessel, bbox)` as a long-lived coroutine
    and must call `self._emit(vessel)` for every position they parse
    (instead of calling `on_vessel` directly) so the base class can track
    the last-received timestamp used for the LIVE/NO_DATA health rule.
    """

    name: str = "unnamed"
    no_data_timeout_seconds: float = 45.0
    is_free_tier: bool = True  # False for sources with a hard call-count budget (e.g. VesselAPI)

    def __init__(self) -> None:
        self.status: ProviderStatus = ProviderStatus.DISABLED
        self.on_status_change: Callable[[str, ProviderStatus], None] | None = None
        self._on_vessel: Callable[[Vessel], None] | None = None
        self._last_packet_at: float | None = None
        # Injected by AISProviderManager: lets a rate-limited provider check
        # whether a free source is already covering this area before it
        # spends part of its budget (the "free ones first" ordering).
        self.is_free_source_live: Callable[[], bool] | None = None
        self._stop = asyncio.Event()

    def is_configured(self) -> bool:
        """False if required credentials are missing (SDR §27.6)."""
        return True

    def _set_status(self, status: ProviderStatus) -> None:
        if status == self.status:
            return
        self.status = status
        if self.on_status_change:
            self.on_status_change(self.name, status)

    def _emit(self, vessel: Vessel) -> None:
        self._last_packet_at = time.monotonic()
        if self.status not in (ProviderStatus.LIVE,):
            self._set_status(ProviderStatus.LIVE)
        if self._on_vessel:
            self._on_vessel(vessel)

    def check_silence(self) -> None:
        """Called periodically by the manager; demotes LIVE -> NO_DATA after silence."""
        if self.status != ProviderStatus.LIVE or self._last_packet_at is None:
            return
        if time.monotonic() - self._last_packet_at > self.no_data_timeout_seconds:
            self._set_status(ProviderStatus.NO_DATA)

    async def run(self, on_vessel: Callable[[Vessel], None], bbox: tuple[float, float, float, float]) -> None:
        """bbox: (lat_min, lon_min, lat_max, lon_max)."""
        if not self.is_configured():
            self._set_status(ProviderStatus.DISABLED)
            return
        self._on_vessel = on_vessel
        self._last_packet_at = None
        # Reset in case a previous run() on this same provider instance was
        # stopped: Event.set() is permanent until cleared, so without this,
        # every start() after the first would exit its _run loop instantly
        # (self._stop already set from the prior stop()) and silently never
        # fetch anything again — exactly what a location change via the
        # manager's start()->stop()->start() cycle would trigger.
        self._stop.clear()
        self._set_status(ProviderStatus.CONNECTING)
        await self._run(bbox)

    async def _run(self, bbox: tuple[float, float, float, float]) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        self._stop.set()
