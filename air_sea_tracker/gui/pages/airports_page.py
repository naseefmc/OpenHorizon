"""Airport Mode (SDR §9, §11, GUI §14)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AirportsPage(QWidget):
    """Phase 3. TODO: mirror PortsPage; distinguish OBSERVED vs SCHEDULED traffic."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Airports Mode (Phase 3)"))
