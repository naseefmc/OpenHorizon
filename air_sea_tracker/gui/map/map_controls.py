"""Floating map control stack: zoom, center, layers, fullscreen (GUI §7)."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class MapControls(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        for symbol, tooltip in [("+", "Zoom in"), ("−", "Zoom out"), ("◎", "Center observer"),
                                 ("◈", "Layers"), ("⛶", "Fullscreen")]:
            btn = QPushButton(symbol)
            btn.setToolTip(tooltip)
            btn.setFixedSize(36, 36)
            layout.addWidget(btn)
