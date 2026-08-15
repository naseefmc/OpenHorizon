"""Advanced filter drawer: type, distance, speed, length, status (GUI §9)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class FilterDrawer(QWidget):
    """TODO(Phase 1): type checkboxes, distance/speed sliders, moving/anchored toggles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "surfaceElevated")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("FILTERS"))
