"""Top bar: app identity, observer location, data status, theme toggle (GUI §4)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class StatusIndicator(QWidget):
    """Colored dot + text, e.g. '● LIVE'. Color must never be the only signal."""

    def __init__(self, label: str, state: str = "disabled", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel()
        layout.addWidget(self._label)
        self.set_state(label, state)

    def set_state(self, label: str, state: str) -> None:
        symbols = {
            "live": "●",
            "cached": "◐",
            "no_data": "◐",
            "rate_limited": "◑",
            "connecting": "◔",
            "offline": "○",
            "disabled": "○",
        }
        self._label.setText(f"{symbols.get(state, '○')} {label}")
        self._label.setProperty("state", state)


class TopBar(QWidget):
    theme_toggle_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        self.app_name = QLabel("AIRSEA")
        self.app_name.setStyleSheet("font-weight: 600; font-size: 16px;")
        layout.addWidget(self.app_name)

        self.location_label = QLabel("No observer location set")
        self.location_label.setProperty("role", "secondary")
        layout.addWidget(self.location_label)

        layout.addStretch()

        self.overall_status = StatusIndicator("OFFLINE", "offline")
        self.ais_status = StatusIndicator("AIS", "disabled")
        self.adsb_status = StatusIndicator("ADS-B", "disabled")
        layout.addWidget(self.overall_status)
        layout.addWidget(self.ais_status)
        layout.addWidget(self.adsb_status)

        theme_btn = QPushButton("◐")
        theme_btn.setToolTip("Toggle theme")
        theme_btn.clicked.connect(self.theme_toggle_requested)
        layout.addWidget(theme_btn)

        settings_btn = QPushButton("⚙")
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self.settings_requested)
        layout.addWidget(settings_btn)

    def set_observer_location(self, name: str) -> None:
        self.location_label.setText(name)
