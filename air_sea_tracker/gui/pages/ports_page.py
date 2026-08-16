"""Port Mode (SDR §9-10, GUI §13).

List-based rather than another embedded map: nearest-port search, traffic
by geofence status, and Inbound Radar are all fundamentally list/table
data — a second Leaflet view didn't add enough over Nearby Mode's map to
justify the complexity here.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidgetItem, QPushButton,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from gui.widgets.copyable_list import CopyableListWidget
from services import geofence_service, port_service
from services.target_manager import TargetManager

REFRESH_MS = 5000


class PortsPage(QWidget):
    def __init__(self, target_manager: TargetManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_manager = target_manager
        self._selected_port = None

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        left = QVBoxLayout()
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Nearest ports"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 20)
        self.count_spin.setValue(5)  # SDR §9: default 5, configurable 1-20
        self.count_spin.valueChanged.connect(self.refresh_list)
        count_row.addWidget(self.count_spin)
        left.addLayout(count_row)

        self.port_list = CopyableListWidget()
        self.port_list.currentItemChanged.connect(self._on_port_selected)
        left.addWidget(self.port_list)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(280)
        root.addWidget(left_widget)

        right = QVBoxLayout()
        self.detail_label = QLabel("Select a port")
        self.detail_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        right.addWidget(self.detail_label)

        self.status_lists: dict[str, CopyableListWidget] = {}
        groups_row = QHBoxLayout()
        for status in [
            geofence_service.STATUS_IN_PORT, geofence_service.STATUS_ANCHORED,
            geofence_service.STATUS_APPROACHING, geofence_service.STATUS_DEPARTING,
            geofence_service.STATUS_PASSING,
        ]:
            col = QVBoxLayout()
            col.addWidget(QLabel(status))
            lst = CopyableListWidget()
            self.status_lists[status] = lst
            col.addWidget(lst)
            groups_row.addLayout(col)
        right.addLayout(groups_row, stretch=1)

        radar_row = QHBoxLayout()
        radar_row.addWidget(QLabel("Inbound Radar radius (km)"))
        self.radar_radius_spin = QSpinBox()
        self.radar_radius_spin.setRange(10, 500)
        self.radar_radius_spin.setValue(100)
        radar_btn = QPushButton("Scan")
        radar_btn.clicked.connect(self.refresh_detail)
        radar_row.addWidget(self.radar_radius_spin)
        radar_row.addWidget(radar_btn)
        radar_row.addStretch(1)
        right.addLayout(radar_row)

        self.radar_list = CopyableListWidget()
        right.addWidget(self.radar_list)

        root.addLayout(right, stretch=1)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(REFRESH_MS)
        self._refresh_timer.timeout.connect(self.refresh_detail)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_list()
        self._refresh_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._refresh_timer.stop()

    def refresh_list(self) -> None:
        conn = self._target_manager.db_conn
        lat, lon = self._target_manager.observer_lat, self._target_manager.observer_lon
        if conn is None or lat is None or lon is None:
            self.port_list.clear()
            self.port_list.addItem("Set an observer location in Nearby mode first")
            return
        ports = port_service.nearest_ports(conn, lat, lon, self.count_spin.value())
        self.port_list.clear()
        for port in ports:
            item = QListWidgetItem(f"{port.name} ({port.country or '—'})")
            item.setData(Qt.UserRole, port)
            self.port_list.addItem(item)
        if self.port_list.count():
            self.port_list.setCurrentRow(0)

    def _on_port_selected(self, current: QListWidgetItem | None, _previous) -> None:
        self._selected_port = current.data(Qt.UserRole) if current else None
        self.refresh_detail()

    def refresh_detail(self) -> None:
        port = self._selected_port
        for lst in self.status_lists.values():
            lst.clear()
        self.radar_list.clear()
        if port is None:
            self.detail_label.setText("Select a port")
            return

        vessels = self._target_manager.all_vessels()
        self.detail_label.setText(
            f"{port.name} — geofence {port.geofence_radius_km:.0f} km · {len(vessels)} vessel(s) currently live"
        )
        groups = geofence_service.port_traffic(port, vessels)
        for status, vessel_list in groups.items():
            lst = self.status_lists[status]
            for v in vessel_list:
                lst.addItem(v.name or v.mmsi)
            if not vessel_list:
                lst.addItem("—")

        radar_hits = geofence_service.inbound_radar(port, vessels, self.radar_radius_spin.value())
        for vessel, distance_km in radar_hits:
            self.radar_list.addItem(f"{vessel.name or vessel.mmsi} — {distance_km:.0f} km out, heading in")
        if not radar_hits:
            self.radar_list.addItem("No inbound vessels detected in range")
