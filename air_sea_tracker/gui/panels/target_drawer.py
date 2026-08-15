"""Target detail drawer, slides in from the right (SDR §15, GUI §10).

Common panel for all target types: identity, live telemetry, distance,
history controls, research entry point. Never opens a separate window.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.widgets.status_badge import StatusBadge
from gui.widgets.telemetry_widget import TelemetryWidget


class TargetDrawer(QWidget):
    closed = Signal()
    track_requested = Signal(str)  # target_id
    research_requested = Signal(str)  # target_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailDrawer")
        self.setFixedWidth(360)
        self._target_id: str | None = None

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.name_label = QLabel("—")
        self.name_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        header.addWidget(self.name_label)
        header.addStretch()
        close_btn = QPushButton("×")
        close_btn.clicked.connect(self.closed)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setProperty("role", "secondary")
        layout.addWidget(self.subtitle_label)

        self.status_badge = StatusBadge("offline")
        layout.addWidget(self.status_badge)

        self.telemetry = TelemetryWidget(["Speed", "Course", "Distance"])
        layout.addWidget(self.telemetry)

        actions = QHBoxLayout()
        track_btn = QPushButton("Track History")
        track_btn.clicked.connect(lambda: self._target_id and self.track_requested.emit(self._target_id))
        research_btn = QPushButton("Research")
        research_btn.clicked.connect(lambda: self._target_id and self.research_requested.emit(self._target_id))
        actions.addWidget(track_btn)
        actions.addWidget(research_btn)
        layout.addLayout(actions)

        layout.addStretch()

    def show_target(self, target_id: str, name: str, subtitle: str) -> None:
        self._target_id = target_id
        self.name_label.setText(name)
        self.subtitle_label.setText(subtitle)
