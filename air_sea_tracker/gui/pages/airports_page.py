"""Airport Mode (SDR §9, §11, GUI §14).

Only shows OBSERVED ADS-B traffic — no free scheduled-flight-data source
is wired up (that's Phase 5, §29), so "expected arrivals/departures"
from a timetable isn't implemented. The label makes that explicit rather
than presenting inferred traffic as a real schedule.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidgetItem, QSpinBox, QVBoxLayout, QWidget,
)

from gui.widgets.copyable_list import SEARCH_KIND_ROLE, SEARCH_TEXT_ROLE, CopyableListWidget
from services import airport_service, geofence_service
from services.target_manager import TargetManager

REFRESH_MS = 5000


class AirportsPage(QWidget):
    def __init__(self, target_manager: TargetManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_manager = target_manager
        self._selected_airport = None

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        left = QVBoxLayout()
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Nearest airports"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 20)
        self.count_spin.setValue(5)
        self.count_spin.valueChanged.connect(self.refresh_list)
        count_row.addWidget(self.count_spin)
        left.addLayout(count_row)

        self.airport_list = CopyableListWidget()
        self.airport_list.currentItemChanged.connect(self._on_airport_selected)
        left.addWidget(self.airport_list)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(280)
        root.addWidget(left_widget)

        right = QVBoxLayout()
        self.detail_label = QLabel("Select an airport")
        self.detail_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        right.addWidget(self.detail_label)

        note = QLabel("Observed ADS-B traffic only — no scheduled-flight data source configured.")
        note.setProperty("role", "secondary")
        right.addWidget(note)

        self.status_lists: dict[str, CopyableListWidget] = {}
        groups_row = QHBoxLayout()
        for status in [
            geofence_service.STATUS_ON_GROUND, geofence_service.STATUS_AIRPORT_APPROACHING,
            geofence_service.STATUS_AIRPORT_DEPARTING, geofence_service.STATUS_AIRPORT_NEARBY,
        ]:
            col = QVBoxLayout()
            col.addWidget(QLabel(status))
            lst = CopyableListWidget()
            self.status_lists[status] = lst
            col.addWidget(lst)
            groups_row.addLayout(col)
        right.addLayout(groups_row, stretch=1)

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
            self.airport_list.clear()
            self.airport_list.addItem("Set an observer location in Nearby mode first")
            return
        airports = airport_service.nearest_airports(conn, lat, lon, self.count_spin.value())
        self.airport_list.clear()
        for airport in airports:
            item = QListWidgetItem(f"{airport.name} ({airport.country or '—'})")
            item.setData(Qt.UserRole, airport)
            self.airport_list.addItem(item)
        if self.airport_list.count():
            self.airport_list.setCurrentRow(0)

    def _on_airport_selected(self, current: QListWidgetItem | None, _previous) -> None:
        self._selected_airport = current.data(Qt.UserRole) if current else None
        self.refresh_detail()

    def refresh_detail(self) -> None:
        airport = self._selected_airport
        for lst in self.status_lists.values():
            lst.clear()
        if airport is None:
            self.detail_label.setText("Select an airport")
            return

        aircraft_list = self._target_manager.all_aircraft()
        groups = geofence_service.airport_traffic(airport, aircraft_list)
        nearby_count = sum(len(a) for a in groups.values())
        self.detail_label.setText(f"{airport.name} · {nearby_count} aircraft near this airport")
        for status, group in groups.items():
            lst = self.status_lists[status]
            for a in group:
                name = a.callsign or a.registration or a.icao24
                item = QListWidgetItem(name)
                item.setData(SEARCH_TEXT_ROLE, name)
                item.setData(SEARCH_KIND_ROLE, "aircraft")
                lst.addItem(item)
            if not group:
                lst.addItem("—")
