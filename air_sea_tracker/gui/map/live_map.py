"""Live map widget: QWebEngineView + Leaflet, bridged via QWebChannel (SDR §16, GUI §6-7)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from gui.map.map_bridge import MapBridge

MAP_HTML_PATH = Path(__file__).parent / "assets" / "map.html"
logger = logging.getLogger(__name__)


class _LoggingPage(QWebEnginePage):
    """Routes the Leaflet map's JS console output into our own logging, so
    a JS-side error (e.g. a bad call from set_radius_km/sync_markers) shows
    up in the app log instead of being silently invisible from Python."""

    def javaScriptConsoleMessage(self, level, message, line, source_id) -> None:
        log_fn = logger.error if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel else logger.debug
        log_fn("map JS console [%s:%d]: %s", source_id, line, message)


class LiveMap(QWebEngineView):
    marker_clicked = Signal(str)  # target_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPage(_LoggingPage(self))

        # map.html is loaded from file:// and pulls Leaflet from a CDN;
        # Chromium blocks local pages from fetching remote resources
        # unless explicitly allowed.
        web_settings = self.settings()
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self._bridge = MapBridge()
        self._bridge.marker_clicked.connect(self.marker_clicked)

        self._channel = QWebChannel(self.page())
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)

        self.load(QUrl.fromLocalFile(str(MAP_HTML_PATH)))

    def _run_js(self, script: str) -> None:
        self.page().runJavaScript(script)

    def set_observer(self, lat: float, lon: float) -> None:
        self._run_js(f"window.setObserver && window.setObserver({lat}, {lon});")

    def set_radius_km(self, lat: float, lon: float, radius_km: float) -> None:
        self._run_js(f"window.setRadiusKm && window.setRadiusKm({lat}, {lon}, {radius_km});")

    def sync_markers(self, targets: list[dict]) -> None:
        """targets: [{id, lat, lon, heading, category, label}, ...]"""
        payload = json.dumps(targets)
        self._run_js(f"window.syncMarkers && window.syncMarkers({payload});")

    def highlight_marker(self, target_id: str | None) -> None:
        payload = json.dumps(target_id)
        self._run_js(f"window.highlightMarker && window.highlightMarker({payload});")

    def draw_track(self, points: list[tuple[float, float]]) -> None:
        payload = json.dumps(points)
        self._run_js(f"window.drawTrack && window.drawTrack({payload});")

    def clear_track(self) -> None:
        self._run_js("window.clearTrack && window.clearTrack();")
