"""Floating map control stack: zoom, center, layers, fullscreen (GUI §7)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class MapControls(QWidget):
    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    center_requested = Signal()
    layers_requested = Signal()
    fullscreen_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        buttons = [
            ("+", "Zoom in", self.zoom_in_requested),
            ("−", "Zoom out", self.zoom_out_requested),
            ("◎", "Center on observer", self.center_requested),
            ("◈", "Toggle dark map layer", self.layers_requested),
            ("⛶", "Toggle fullscreen", self.fullscreen_requested),
        ]
        for symbol, tooltip, signal in buttons:
            btn = QPushButton(symbol)
            btn.setToolTip(tooltip)
            btn.setFixedSize(36, 36)
            btn.clicked.connect(signal)
            layout.addWidget(btn)
