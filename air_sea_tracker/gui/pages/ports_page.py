"""Port Mode (SDR §9-10, GUI §13)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PortsPage(QWidget):
    """Phase 3. TODO: nearest-port cards, geofence-based in-port/approaching/departing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Ports Mode (Phase 3)"))
