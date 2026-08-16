"""History Mode (SDR §8, GUI §11) — pick a target, view its track and stats."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from database.repository import track_stats
from gui.map.live_map import LiveMap
from gui.widgets.telemetry_widget import TelemetryWidget
from services.target_manager import TargetManager
from utils.units import speed_label

RANGES = {"Live (1h)": 1, "24 hours": 24, "7 days": 24 * 7}


class HistoryPage(QWidget):
    def __init__(self, target_manager: TargetManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_manager = target_manager

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        controls = QHBoxLayout()
        controls.setContentsMargins(12, 8, 12, 8)
        self.target_combo = QComboBox()
        self.target_combo.setMinimumWidth(240)
        self.range_combo = QComboBox()
        self.range_combo.addItems(list(RANGES.keys()))
        self.range_combo.setCurrentText("24 hours")
        load_btn = QPushButton("Load")
        load_btn.setProperty("role", "primary")
        load_btn.clicked.connect(self._on_load)
        refresh_btn = QPushButton("Refresh list")
        refresh_btn.clicked.connect(self.refresh_target_list)
        controls.addWidget(self.target_combo)
        controls.addWidget(self.range_combo)
        controls.addWidget(load_btn)
        controls.addWidget(refresh_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self.stats = TelemetryWidget(["Distance", "Max speed", "Avg speed", "Points"])
        root.addWidget(self.stats)

        self.live_map = LiveMap()
        root.addWidget(self.live_map, stretch=1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.target_combo.count() == 0:
            self.refresh_target_list()

    def refresh_target_list(self) -> None:
        current = self.target_combo.currentData()
        self.target_combo.clear()
        for row in self._target_manager.known_targets():
            label = f"{row['name']} ({row['target_type']})"
            self.target_combo.addItem(label, row["target_id"])
        if current:
            idx = self.target_combo.findData(current)
            if idx >= 0:
                self.target_combo.setCurrentIndex(idx)

    def _on_load(self) -> None:
        target_id = self.target_combo.currentData()
        if not target_id:
            return
        hours = RANGES[self.range_combo.currentText()]
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        points = self._target_manager.track(target_id, since)

        stats = track_stats(points)
        self.stats.set_value("Distance", f"{stats['distance_km']:.1f} km")
        self.stats.set_value("Max speed", speed_label(stats["max_speed"]))
        self.stats.set_value("Avg speed", speed_label(stats["avg_speed"]))
        self.stats.set_value("Points", str(len(points)))

        self.live_map.draw_track([(p["lat"], p["lon"]) for p in points])
