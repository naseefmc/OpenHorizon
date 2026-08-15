"""Vertical icon navigation rail (GUI Design Guide §3)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget

from gui.theme.icons import NAV_ICONS

MODES = ["global", "nearby", "ports", "airports", "history", "search", "settings"]
MODE_LABELS = {
    "global": "Global",
    "nearby": "Nearby",
    "ports": "Ports",
    "airports": "Airports",
    "history": "History",
    "search": "Search",
    "settings": "Settings",
}


class Sidebar(QWidget):
    mode_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(88)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for mode in MODES:
            btn = QPushButton(f"{NAV_ICONS[mode]}\n{MODE_LABELS[mode]}")
            btn.setProperty("role", "nav")
            btn.setCheckable(True)
            btn.setFixedHeight(64)
            btn.clicked.connect(lambda checked, m=mode: self.mode_selected.emit(m))
            self._group.addButton(btn)
            layout.addWidget(btn)
            if mode == "nearby":
                btn.setChecked(True)

        layout.addStretch()

    def select_mode(self, mode: str) -> None:
        for btn in self._group.buttons():
            if MODE_LABELS.get(mode, "") in btn.text():
                btn.setChecked(True)
