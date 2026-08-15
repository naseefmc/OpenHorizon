"""Search & Intelligence Mode (SDR §3, §12, GUI §15-16)."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui.widgets.search_box import SearchBox


class SearchPage(QWidget):
    """Phase 1: global search. Phase 4: per-target Intelligence/Research view."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(SearchBox())
        layout.addStretch()
