"""Target detail drawer, slides in from the right (SDR §15, GUI §10).

Common panel for all target types: identity, live telemetry, distance,
history controls, research entry point. Never opens a separate window.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.widgets.status_badge import StatusBadge
from gui.widgets.telemetry_widget import TelemetryWidget


class TargetDrawer(QWidget):
    closed = Signal()
    track_requested = Signal(str)  # target_id
    research_requested = Signal(str)  # target_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailDrawer")
        self.setFixedWidth(420)
        self._target_id: str | None = None

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.name_label = QLabel("—")
        self.name_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.name_label.setWordWrap(True)
        header.addWidget(self.name_label, stretch=1)
        close_btn = QPushButton("×")
        close_btn.clicked.connect(self.closed)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setProperty("role", "secondary")
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        self.status_badge = StatusBadge("offline")
        layout.addWidget(self.status_badge)

        self.telemetry = TelemetryWidget(["Speed", "Course", "Distance", "Visibility"])
        layout.addWidget(self.telemetry)

        # Identity + technical characteristics (SDR §15) — rebuilt per
        # selection since the field set differs between vessels/aircraft.
        layout.addWidget(QLabel("DETAILS"))
        self._details_form = QFormLayout()
        self._details_form.setContentsMargins(0, 0, 0, 8)
        self._details_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._details_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        layout.addLayout(self._details_form)

        actions = QHBoxLayout()
        self.track_btn = QPushButton("Track History")
        self.track_btn.setCheckable(True)
        self.track_btn.clicked.connect(lambda: self._target_id and self.track_requested.emit(self._target_id))
        research_btn = QPushButton("Research")
        research_btn.clicked.connect(lambda: self._target_id and self.research_requested.emit(self._target_id))
        actions.addWidget(self.track_btn)
        actions.addWidget(research_btn)
        layout.addLayout(actions)

        layout.addStretch()

    def show_target(self, target_id: str, name: str, subtitle: str) -> None:
        self._target_id = target_id
        self.name_label.setText(name)
        self.subtitle_label.setText(subtitle)
        self.track_btn.setChecked(False)

    def set_details(self, fields: list[tuple[str, str]]) -> None:
        while self._details_form.rowCount():
            self._details_form.removeRow(0)
        for label, value in fields:
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            self._details_form.addRow(label, value_label)
