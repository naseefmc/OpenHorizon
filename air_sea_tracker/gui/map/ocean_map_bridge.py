"""Python <-> JS bridge for the Ocean & Environment map, via QWebChannel.

Carries click-to-select (SDR §5) events from the JS mapping layer to
Python-side selection state — separate from gui/map/map_bridge.py
(LiveMap's target-marker-click bridge) since the Ocean map's only
interaction is "click anywhere", not "click a target".
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class OceanMapBridge(QObject):
    location_clicked = Signal(float, float)  # lat, lon

    @Slot(float, float)
    def on_map_clicked(self, lat: float, lon: float) -> None:
        self.location_clicked.emit(lat, lon)
