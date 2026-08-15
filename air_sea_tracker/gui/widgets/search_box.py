"""Global search field, Ctrl/Cmd+K (GUI §16)."""

from __future__ import annotations

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QLineEdit, QWidget


class SearchBox(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Search aircraft, vessels, ports...")

    @staticmethod
    def bind_global_shortcut(target_window: QWidget, on_activate) -> QShortcut:
        shortcut = QShortcut(QKeySequence("Ctrl+K"), target_window)
        shortcut.activated.connect(on_activate)
        return shortcut
