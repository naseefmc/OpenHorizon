"""Small labeled numeric stat block, e.g. SPEED / COURSE in the detail drawer (GUI §10)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StatCard(QWidget):
    def __init__(self, label: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._value_label = QLabel(value)
        self._value_label.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(self._value_label, alignment=Qt.AlignLeft)

        caption = QLabel(label.upper())
        caption.setProperty("role", "muted")
        caption.setStyleSheet("font-size: 11px; letter-spacing: 1px;")
        layout.addWidget(caption, alignment=Qt.AlignLeft)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)
