"""Global Mode (SDR §7, GUI §12) — worldwide traffic, clustered."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class GlobalPage(QWidget):
    """Phase 2. TODO: clustered WebGL/JS map rendering, not per-marker Qt widgets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Global Mode — worldwide clustered traffic (Phase 2)"))
