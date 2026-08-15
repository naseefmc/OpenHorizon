"""Row of large telemetry StatCards, e.g. SPEED / COURSE / DISTANCE (GUI §10)."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget

from gui.widgets.stat_card import StatCard


class TelemetryWidget(QWidget):
    def __init__(self, fields: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._cards: dict[str, StatCard] = {}
        for field in fields:
            card = StatCard(field)
            self._cards[field] = card
            layout.addWidget(card)

    def set_value(self, field: str, value: str) -> None:
        if field in self._cards:
            self._cards[field].set_value(value)
