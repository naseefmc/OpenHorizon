"""Port Mode (SDR §9-10, GUI §13).

List-based rather than another embedded map: nearest-port search, traffic
by geofence status, and Inbound Radar are all fundamentally list/table
data — a second Leaflet view didn't add enough over Nearby Mode's map to
justify the complexity here.
"""

from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QInputDialog, QLabel, QListWidgetItem, QPushButton,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from config.credentials import VESSELAPI_API_KEY, get_credential
from gui.widgets.copyable_list import SEARCH_KIND_ROLE, SEARCH_TEXT_ROLE, CopyableListWidget
from services import geofence_service, port_service
from services.ais_providers.vesselapi_provider import VesselApiError, fetch_inbound
from services.rate_limiter import MonthlyRateLimiter
from services.target_manager import TargetManager
from utils.time_format import eta_label

logger = logging.getLogger(__name__)

REFRESH_MS = 5000


class PortsPage(QWidget):
    def __init__(self, target_manager: TargetManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_manager = target_manager
        self._selected_port = None
        self._vesselapi_rate_limiter = MonthlyRateLimiter(name="vesselapi", monthly_limit=150)

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

        vesselapi_row = QHBoxLayout()
        self.unlocode_label = QLabel("VesselAPI UN/LOCODE: not set")
        vesselapi_row.addWidget(self.unlocode_label)
        set_unlocode_btn = QPushButton("Set…")
        set_unlocode_btn.clicked.connect(self._on_set_unlocode)
        vesselapi_row.addWidget(set_unlocode_btn)
        self.vesselapi_btn = QPushButton("Check VesselAPI Inbound")
        self.vesselapi_btn.clicked.connect(self._on_check_vesselapi_inbound)
        vesselapi_row.addWidget(self.vesselapi_btn)
        vesselapi_row.addStretch(1)
        right.addLayout(vesselapi_row)

        self.vesselapi_list = CopyableListWidget()
        right.addWidget(self.vesselapi_list)

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
        self._update_unlocode_label()
        self.vesselapi_list.clear()
        self.refresh_detail()

    def _update_unlocode_label(self) -> None:
        port = self._selected_port
        code = port.unlocode if port else None
        self.unlocode_label.setText(f"VesselAPI UN/LOCODE: {code or 'not set'}")

    def _on_set_unlocode(self) -> None:
        port = self._selected_port
        if port is None:
            return
        text, ok = QInputDialog.getText(
            self, "VesselAPI UN/LOCODE",
            f"UN/LOCODE for {port.name} (e.g. HRSPU) — VesselAPI's inbound-ETA "
            "endpoint is keyed by this code; VesselAPI's own port search doesn't "
            "return it, so it has to be entered manually:",
            text=port.unlocode or "",
        )
        if not ok:
            return
        code = text.strip().upper() or None
        conn = self._target_manager.db_conn
        if conn is not None:
            port_service.set_unlocode(conn, port.port_id, code)
        port.unlocode = code
        self._update_unlocode_label()
        self.vesselapi_list.clear()

    def _on_check_vesselapi_inbound(self) -> None:
        port = self._selected_port
        if port is None:
            return
        if not port.unlocode:
            self.vesselapi_list.clear()
            self.vesselapi_list.addItem("Set a UN/LOCODE for this port first")
            return
        api_key = get_credential(VESSELAPI_API_KEY)
        if not api_key:
            self.vesselapi_list.clear()
            self.vesselapi_list.addItem("VesselAPI not configured (add an API key in Settings)")
            return
        if not self._vesselapi_rate_limiter.can_call():
            self.vesselapi_list.clear()
            self.vesselapi_list.addItem(
                f"VesselAPI monthly quota exhausted ({self._vesselapi_rate_limiter.quota_summary()})"
            )
            return
        self.vesselapi_btn.setEnabled(False)
        self.vesselapi_list.clear()
        self.vesselapi_list.addItem("Checking VesselAPI (can take up to ~30s)…")
        asyncio.ensure_future(self._check_vesselapi_inbound(port.unlocode, api_key))

    async def _check_vesselapi_inbound(self, unlocode: str, api_key: str) -> None:
        try:
            inbound = await fetch_inbound(unlocode, api_key)
        except Exception as exc:
            logger.warning("VesselAPI inbound check failed: %s", exc)
            self.vesselapi_list.clear()
            self.vesselapi_list.addItem("VesselAPI request failed — see logs")
            self.vesselapi_btn.setEnabled(True)
            return
        self._vesselapi_rate_limiter.record_call()
        self.vesselapi_list.clear()
        if not inbound:
            self.vesselapi_list.addItem("No vessels currently declaring this port as destination")
        for v in inbound:
            extra = f" · draught {v.draught:.0f}m" if v.draught else ""
            display = f"{v.name or v.mmsi} — ETA {eta_label(v.eta)}{extra}"
            self._add_vessel_item(self.vesselapi_list, display, v.name or v.mmsi)
        self.vesselapi_btn.setEnabled(True)

    def refresh_detail(self) -> None:
        port = self._selected_port
        for lst in self.status_lists.values():
            lst.clear()
        self.radar_list.clear()
        if port is None:
            self.detail_label.setText("Select a port")
            return

        vessels = self._target_manager.all_vessels()
        groups = geofence_service.port_traffic(port, vessels)
        nearby_count = sum(len(v) for v in groups.values())
        self.detail_label.setText(
            f"{port.name} — geofence {port.geofence_radius_km:.0f} km · {nearby_count} vessel(s) near this port"
        )
        for status, vessel_list in groups.items():
            lst = self.status_lists[status]
            for v in vessel_list:
                self._add_vessel_item(lst, v.name or v.mmsi, v.name or v.mmsi)
            if not vessel_list:
                lst.addItem("—")

        radar_hits = geofence_service.inbound_radar(port, vessels, self.radar_radius_spin.value())
        for vessel, distance_km in radar_hits:
            display = f"{vessel.name or vessel.mmsi} — {distance_km:.0f} km out, heading in"
            self._add_vessel_item(self.radar_list, display, vessel.name or vessel.mmsi)
        if not radar_hits:
            self.radar_list.addItem("No inbound vessels detected in range")

    @staticmethod
    def _add_vessel_item(lst: CopyableListWidget, display_text: str, search_name: str) -> None:
        item = QListWidgetItem(display_text)
        item.setData(SEARCH_TEXT_ROLE, search_name)
        item.setData(SEARCH_KIND_ROLE, "vessel")
        lst.addItem(item)
