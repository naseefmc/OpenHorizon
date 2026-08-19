"""Ocean & Environment map widget: QWebEngineView + Leaflet, bridged via
QWebChannel (Ocean & Environment SDR §2, §4, §5). Sibling of
gui/map/live_map.py — separate widget because this map's primary
interaction is "click anywhere for data", not "click a live target",
and its overlays are WMS raster layers rather than live target markers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from gui.map.ocean_map_bridge import OceanMapBridge
from ocean.providers.base import TileLayerSpec

MAP_HTML_PATH = Path(__file__).parent / "assets" / "ocean_map.html"
logger = logging.getLogger(__name__)


class _LoggingPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source_id) -> None:
        log_fn = logger.error if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel else logger.debug
        log_fn("ocean map JS console [%s:%d]: %s", source_id, line, message)


class OceanMap(QWebEngineView):
    location_clicked = Signal(float, float)  # lat, lon

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPage(_LoggingPage(self))

        web_settings = self.settings()
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self._bridge = OceanMapBridge()
        self._bridge.location_clicked.connect(self.location_clicked)

        self._channel = QWebChannel(self.page())
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)

        self.load(QUrl.fromLocalFile(str(MAP_HTML_PATH)))

    def _run_js(self, script: str) -> None:
        self.page().runJavaScript(script)

    def set_layer(self, layer_id: str, spec: TileLayerSpec | None, visible: bool) -> None:
        cfg_json = json.dumps(asdict(spec)) if spec else "null"
        self._run_js(f"window.setLayer && window.setLayer({json.dumps(layer_id)}, {cfg_json}, {json.dumps(visible)});")

    def set_layer_visible(self, layer_id: str, visible: bool) -> None:
        self._run_js(f"window.setLayerVisible && window.setLayerVisible({json.dumps(layer_id)}, {json.dumps(visible)});")

    def set_selected_marker(self, lat: float, lon: float) -> None:
        self._run_js(f"window.setSelectedMarker && window.setSelectedMarker({lat}, {lon});")

    def zoom_in(self) -> None:
        self._run_js("window.zoomIn && window.zoomIn();")

    def zoom_out(self) -> None:
        self._run_js("window.zoomOut && window.zoomOut();")

    def toggle_dark_layer(self) -> None:
        self._run_js("window.toggleDarkLayer && window.toggleDarkLayer();")
