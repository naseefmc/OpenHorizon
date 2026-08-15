"""Python <-> JS bridge for the live map, via QWebChannel (SDR §16).

Carries marker add/update/remove and click-to-select events between
the JS mapping layer and Python-side selection state.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class MapBridge(QObject):
    marker_clicked = Signal(str)  # target_id

    @Slot(str)
    def on_marker_clicked(self, target_id: str) -> None:
        self.marker_clicked.emit(target_id)
