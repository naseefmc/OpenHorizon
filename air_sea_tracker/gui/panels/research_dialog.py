"""Research / Intelligence view (SDR §12-14, Phase 4).

Fetches enrichment + a photo (vessels only — see enrichment_service) and
a rough value estimate, over the network, without blocking the Qt event
loop (SDR §24) — the fetch runs as an asyncio task on the shared qasync
loop and the dialog is populated when it resolves.
"""

from __future__ import annotations

import asyncio

import aiohttp
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QVBoxLayout

from services import enrichment_service, value_estimator


class ResearchDialog(QDialog):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Research — {title}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(420)

        layout = QVBoxLayout(self)

        self.photo_label = QLabel("Loading…")
        self.photo_label.setAlignment(Qt.AlignCenter)
        self.photo_label.setFixedHeight(180)
        layout.addWidget(self.photo_label)

        self.note_label = QLabel("")
        self.note_label.setProperty("role", "secondary")
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)

        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.addLayout(self.form)

        self.value_label = QLabel("")
        self.value_label.setWordWrap(True)
        self.value_label.setProperty("role", "secondary")
        layout.addWidget(self.value_label)

    def show_loading(self) -> None:
        self.photo_label.setText("Loading…")
        self.note_label.setText("")

    def show_result(self, result: enrichment_service.EnrichmentResult) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)

        self.note_label.setText(result.note)
        if not result.found:
            self.photo_label.setText("No photo available")
            return

        for f in result.fields:
            label = QLabel(f"{f.value}  ·  {f.confidence.lower()}")
            label.setWordWrap(True)
            label.setToolTip(f.source)
            self.form.addRow(f.label, label)

        if result.image_url:
            self.photo_label.setText("Loading photo…")
            asyncio.ensure_future(self._load_photo(result.image_url))
        else:
            self.photo_label.setText("No photo available")

    def show_value_estimate(self, estimate: value_estimator.ValueEstimate | None) -> None:
        if estimate is None:
            return
        self.value_label.setText(
            f"Estimated value: ${estimate.low:,.0f} – ${estimate.high:,.0f} {estimate.currency} "
            f"({estimate.confidence.lower()} confidence, ESTIMATE not a valuation)\n{estimate.note}"
        )

    async def _load_photo(self, url: str) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        self.photo_label.setText("Photo failed to load")
                        return
                    data = await resp.read()
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.photo_label.setPixmap(
                    pixmap.scaledToHeight(180, Qt.SmoothTransformation)
                )
                self.photo_label.setText("")
            else:
                self.photo_label.setText("Photo failed to load")
        except Exception:
            self.photo_label.setText("Photo failed to load")
