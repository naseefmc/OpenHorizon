"""Application entry point (SDR §31).

Wires: QApplication + asyncio event loop (qasync, so WebSocket/REST
collectors can run alongside the Qt GUI loop without blocking it —
SDR §24 "network collection never executes on GUI thread"), theming,
settings, the local SQLite database, and the AIS/ADS-B collectors.
"""

from __future__ import annotations

import asyncio
import logging
import sys

import qasync
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from collectors.adsb_collector import ADSBCollector
from config.settings import Settings
from database.database import connect as connect_db
from gui.main_window import MainWindow
from gui.theme.theme_manager import ThemeManager
from services.ais_provider_manager import AISProviderManager
from services.ais_providers.base import ProviderStatus
from services.geo_service import bounding_box_km
from services.target_manager import TargetManager
from utils.logging import setup_logging

logger = logging.getLogger(__name__)

# Collectors are subscribed to a fixed area sized to cover the largest
# quick-radius option (500 km, GUI §5) rather than the live slider value,
# so moving the radius slider never needs to reconnect AISStream or
# re-poll OpenSky with a new bbox — only a genuine observer location
# change does (SDR §22).
COLLECTOR_COVERAGE_RADIUS_KM = 500.0


class LiveDataController:
    """Owns collector lifecycles and restarts them when the observer moves."""

    # Aggregate priority when reducing all AIS providers' statuses down to
    # the single top-bar "AIS" indicator (SDR §26.6): show the most useful
    # signal available rather than e.g. one silent provider masking another
    # that's actually live.
    _STATUS_PRIORITY = ["live", "no_data", "rate_limited", "connecting", "offline", "disabled"]

    def __init__(self, target_manager: TargetManager, on_status_change) -> None:
        self._target_manager = target_manager
        self._on_status_change = on_status_change
        self._ais_manager = AISProviderManager(
            on_vessel_update=self._on_vessel_update,
            on_provider_status_change=self._on_provider_status_change,
        )
        self._provider_statuses: dict[str, ProviderStatus] = {}
        self._adsb_collector: ADSBCollector | None = None
        self._adsb_task: asyncio.Task | None = None
        self._quota_timer: QTimer | None = None
        self._last_bbox = None

    def set_observer(self, lat: float, lon: float) -> None:
        self._last_bbox = bounding_box_km(lat, lon, COLLECTOR_COVERAGE_RADIUS_KM)
        self._ais_manager.start(self._last_bbox)
        self._restart_adsb(self._last_bbox)

    def restart_ais(self) -> None:
        """Reconnect all AIS providers after a credential change (SDR §27.6):
        any provider may have just become configured/unconfigured."""
        if self._last_bbox is not None:
            self._ais_manager.start(self._last_bbox)

    def provider_statuses(self) -> list[tuple[str, ProviderStatus]]:
        return self._ais_manager.statuses()

    def _on_provider_status_change(self, name: str, status: ProviderStatus) -> None:
        self._provider_statuses[name] = status
        values = {s.value for s in self._provider_statuses.values()}
        aggregate = next((s for s in self._STATUS_PRIORITY if s in values), "disabled")
        self._on_status_change("ais", aggregate)

    def _restart_adsb(self, bbox) -> None:
        if self._adsb_collector is not None:
            self._adsb_collector.stop()
        if self._adsb_task is not None:
            self._adsb_task.cancel()

        self._adsb_collector = ADSBCollector(self._on_state_update, bbox=bbox)
        self._adsb_task = asyncio.ensure_future(self._run_adsb())
        self._on_status_change("adsb", "live")

    async def _run_adsb(self) -> None:
        try:
            await self._adsb_collector.run()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("ADS-B collector crashed")
            self._on_status_change("adsb", "offline")

    def _on_vessel_update(self, vessel) -> None:
        self._target_manager.update_vessel(vessel)

    def _on_state_update(self, payload: dict) -> None:
        self._target_manager.ingest_opensky_states(payload)

    def quota_summary(self) -> str | None:
        return self._adsb_collector.quota_summary() if self._adsb_collector else None

    def vesselapi_quota_summary(self) -> str | None:
        for provider in self._ais_manager.providers:
            if provider.name == "VesselAPI":
                return provider.quota_summary()
        return None


def main() -> int:
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("AirSeaLiveTracker")
    app.setOrganizationName("AirSeaTracker")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    settings = Settings()
    theme_manager = ThemeManager(app)
    theme_manager.set_mode(settings.theme)

    db_conn = connect_db()

    target_manager = TargetManager(db_conn)
    window = MainWindow(settings, theme_manager, target_manager)

    # SDR §26.4: batched write-through so relaunching soon after doesn't
    # start from an empty cache or force quota-limited providers to be
    # re-polled just to restore what was already known.
    flush_timer = QTimer()
    flush_timer.setInterval(20_000)
    flush_timer.timeout.connect(target_manager.flush_to_db)
    flush_timer.start()
    window.closing.connect(target_manager.flush_to_db)

    source_states = {"ais": "disabled", "adsb": "disabled"}

    def on_status_change(source: str, state: str) -> None:
        source_states[source] = state
        indicator = window.top_bar.ais_status if source == "ais" else window.top_bar.adsb_status
        indicator.set_state("AIS" if source == "ais" else "ADS-B", state)

        if "live" in source_states.values():
            window.top_bar.overall_status.set_state("LIVE", "live")
        elif "offline" in source_states.values():
            window.top_bar.overall_status.set_state("OFFLINE", "offline")
        else:
            window.top_bar.overall_status.set_state("OFFLINE", "disabled")

    controller = LiveDataController(target_manager, on_status_change)
    window.observer_changed.connect(controller.set_observer)
    window.ais_credential_changed.connect(controller.restart_ais)

    window.restore_last_observer()  # after the above connections, not from MainWindow.__init__
    window.show()

    with loop:
        return loop.run_forever()


if __name__ == "__main__":
    sys.exit(main())
