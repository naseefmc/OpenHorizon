"""History Mode (SDR §8, GUI §11) — search a target, view its track and stats."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from database.repository import track_stats
from gui.map.live_map import LiveMap
from gui.widgets.copyable_list import SEARCH_KIND_ROLE, SEARCH_TEXT_ROLE, CopyableListWidget
from gui.widgets.telemetry_widget import TelemetryWidget
from services.target_manager import TargetManager
from utils.time_format import age_label, parse_iso
from utils.units import speed_label
from utils.web_search import open_google_image_search

RANGES = {"Live (1h)": 1, "24 hours": 24, "7 days": 24 * 7}


class HistoryPage(QWidget):
    def __init__(self, target_manager: TargetManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_manager = target_manager
        self._known: list[dict] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        left = QVBoxLayout()
        left.addWidget(QLabel("Search targets with recorded history"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by name, MMSI, ICAO24…")
        self.search_box.textChanged.connect(self._apply_filter)
        left.addWidget(self.search_box)

        type_row = QHBoxLayout()
        self.aircraft_checkbox = QCheckBox("Aircraft")
        self.aircraft_checkbox.setChecked(True)
        self.aircraft_checkbox.toggled.connect(self._apply_filter)
        self.vessel_checkbox = QCheckBox("Vessel")
        self.vessel_checkbox.setChecked(True)
        self.vessel_checkbox.toggled.connect(self._apply_filter)
        type_row.addWidget(self.aircraft_checkbox)
        type_row.addWidget(self.vessel_checkbox)
        left.addLayout(type_row)

        self.target_list = CopyableListWidget()
        self.target_list.currentItemChanged.connect(self._on_target_selected)
        left.addWidget(self.target_list, stretch=1)

        buttons_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh list")
        refresh_btn.clicked.connect(self.refresh_target_list)
        buttons_row.addWidget(refresh_btn)
        search_btn = QPushButton("Search Google")
        search_btn.clicked.connect(self._on_search_selected)
        buttons_row.addWidget(search_btn)
        left.addLayout(buttons_row)

        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(300)
        root.addWidget(left_widget)

        right = QVBoxLayout()
        controls = QHBoxLayout()
        self.range_combo = QComboBox()
        self.range_combo.addItems(list(RANGES.keys()))
        self.range_combo.setCurrentText("24 hours")
        self.range_combo.currentTextChanged.connect(self._on_load)
        controls.addWidget(QLabel("Range"))
        controls.addWidget(self.range_combo)
        controls.addStretch(1)
        right.addLayout(controls)

        self.status_label = QLabel("Select a target on the left")
        self.status_label.setProperty("role", "secondary")
        right.addWidget(self.status_label)

        self.stats = TelemetryWidget(["Distance", "Max speed", "Avg speed", "Points"])
        right.addWidget(self.stats)

        self.live_map = LiveMap()
        right.addWidget(self.live_map, stretch=1)
        root.addLayout(right, stretch=1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._known:
            self.refresh_target_list()

    def refresh_target_list(self) -> None:
        self._known = self._target_manager.known_targets()
        self._apply_filter()

    def _apply_filter(self, _changed: object = None) -> None:
        current_id = self.target_list.currentItem().data(Qt.UserRole) if self.target_list.currentItem() else None
        self.target_list.clear()
        needle = self.search_box.text().strip().lower()
        show_aircraft = self.aircraft_checkbox.isChecked()
        show_vessel = self.vessel_checkbox.isChecked()
        for row in self._known:
            if row["target_type"] == "aircraft" and not show_aircraft:
                continue
            if row["target_type"] == "vessel" and not show_vessel:
                continue
            haystack = f"{row['name']} {row['target_id']}".lower()
            if needle and needle not in haystack:
                continue
            last_seen = age_label(parse_iso(row.get("last_seen")))
            item = QListWidgetItem(f"{row['name']} ({row['target_type']}) — last seen {last_seen}")
            item.setData(Qt.UserRole, row["target_id"])
            item.setData(SEARCH_TEXT_ROLE, row["name"])
            item.setData(SEARCH_KIND_ROLE, row["target_type"])
            self.target_list.addItem(item)
        if current_id:
            for i in range(self.target_list.count()):
                if self.target_list.item(i).data(Qt.UserRole) == current_id:
                    self.target_list.setCurrentRow(i)
                    break

    def _on_search_selected(self) -> None:
        current = self.target_list.currentItem()
        if current is None:
            return
        open_google_image_search(
            current.data(SEARCH_TEXT_ROLE) or current.text(), current.data(SEARCH_KIND_ROLE)
        )

    def _on_target_selected(self, current: QListWidgetItem | None, _previous) -> None:
        self._on_load()

    def _on_load(self) -> None:
        current = self.target_list.currentItem()
        if current is None:
            self.live_map.clear_track()
            return
        target_id = current.data(Qt.UserRole)
        hours = RANGES[self.range_combo.currentText()]
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        points = self._target_manager.track(target_id, since)

        stats = track_stats(points)
        self.stats.set_value("Distance", f"{stats['distance_km']:.1f} km")
        self.stats.set_value("Max speed", speed_label(stats["max_speed"]))
        self.stats.set_value("Avg speed", speed_label(stats["avg_speed"]))
        self.stats.set_value("Points", str(len(points)))

        if points:
            self.status_label.setText(f"{current.text()} — {len(points)} point(s) in range")
            self.live_map.draw_track([(p["lat"], p["lon"]) for p in points])
        else:
            self.status_label.setText(f"{current.text()} — no recorded positions in this range")
            self.live_map.clear_track()
