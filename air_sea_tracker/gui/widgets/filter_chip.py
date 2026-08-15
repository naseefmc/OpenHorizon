"""Toggleable filter chip, e.g. [ Yacht ] [ Cargo ] (GUI §9)."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton


class FilterChip(QPushButton):
    def __init__(self, label: str, checked: bool = False) -> None:
        super().__init__(label)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setProperty("role", "chip")
