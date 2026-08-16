"""Global Mode (SDR §7, GUI §12) — worldwide traffic, clustered.

Reuses the same LiveMap (clustering is always on, see map.html) and
TargetTable widgets as Nearby Mode, but with no observer/radius — the
full live cache, filtered only by Air/Sea.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QSplitter, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from gui.map.live_map import LiveMap
from gui.tables.target_table import TargetTable
from models.aircraft import Aircraft
from services.target_manager import TargetManager

REFRESH_MS = 5000  # SDR §7: global refresh cadence is source-dependent, coarser than Nearby's 1-5s


class GlobalPage(QWidget):
    def __init__(self, target_manager: TargetManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_manager = target_manager

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        filters_row = QHBoxLayout()
        filters_row.setContentsMargins(12, 8, 12, 8)
        self.air_checkbox = QCheckBox("Air")
        self.air_checkbox.setChecked(True)
        self.air_checkbox.toggled.connect(self.refresh)
        self.sea_checkbox = QCheckBox("Sea")
        self.sea_checkbox.setChecked(True)
        self.sea_checkbox.toggled.connect(self.refresh)
        filters_row.addWidget(self.air_checkbox)
        filters_row.addWidget(self.sea_checkbox)
        filters_row.addStretch(1)
        root.addLayout(filters_row)

        center = QSplitter(Qt.Vertical)
        self.live_map = LiveMap()
        self.table = TargetTable()
        self.table.row_selected.connect(self.live_map.highlight_marker)
        center.addWidget(self.live_map)
        center.addWidget(self.table)
        center.setStretchFactor(0, 7)
        center.setStretchFactor(1, 3)
        root.addWidget(center, stretch=1)

        self.live_map.marker_clicked.connect(self.live_map.highlight_marker)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(REFRESH_MS)
        self._refresh_timer.timeout.connect(self.refresh)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_timer.start()
        self.refresh()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._refresh_timer.stop()

    def refresh(self) -> None:
        targets = self._target_manager.all_targets(
            self.air_checkbox.isChecked(), self.sea_checkbox.isChecked()
        )

        rows, markers = [], []
        for target in targets:
            is_aircraft = isinstance(target, Aircraft)
            heading = target.track if is_aircraft else target.effective_heading
            label = (target.callsign or target.icao24) if is_aircraft else (target.name or target.mmsi)
            markers.append({
                "id": target.target_id, "lat": target.latitude, "lon": target.longitude,
                "heading": heading, "category": "aircraft" if is_aircraft else "vessel", "label": label,
            })
            rows.append({
                "target_id": target.target_id,
                "type": "Aircraft" if is_aircraft else "Vessel",
                "name": label,
                "distance": "—",
                "speed": f"{(target.ground_speed if is_aircraft else target.speed_over_ground) or 0:.0f} kt",
                "heading": f"{heading:.0f}°" if heading is not None else "—",
                "altitude_status": f"{target.altitude_m:.0f} m" if is_aircraft and target.altitude_m else "—",
                "destination": "—" if is_aircraft else (target.destination or "—"),
                "updated": "live",
            })

        self.live_map.sync_markers(markers)
        self.table.model_.replace_rows(rows)
