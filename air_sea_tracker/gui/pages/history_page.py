"""History Mode (SDR §8, GUI §11)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class HistoryPage(QWidget):
    """Phase 2. TODO: 1h/24h/7d timeline scrubber, stats (distance/avg/max speed)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("History Mode (Phase 2)"))
