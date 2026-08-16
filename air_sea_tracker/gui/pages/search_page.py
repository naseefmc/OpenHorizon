"""Search & Intelligence Mode (SDR §3, §12, GUI §15-16).

Global search across live targets and everything with recorded history,
matched against name/MMSI/IMO/callsign/ICAO24/registration. Previously
just an unwired QLineEdit — pressing Enter did nothing.

Per-target Intelligence/Research (owner/operator enrichment, value
estimate) lives in `services/enrichment_service.py` /
`services/value_estimator.py`; wired in here as a "Research" action.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidgetItem, QVBoxLayout, QWidget

from gui.widgets.copyable_list import CopyableListWidget
from gui.widgets.search_box import SearchBox
from models.aircraft import Aircraft
from services.target_manager import TargetManager


class SearchPage(QWidget):
    target_activated = Signal(str)  # target_id — MainWindow jumps to it in Nearby Mode

    def __init__(self, target_manager: TargetManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_manager = target_manager

        layout = QVBoxLayout(self)
        self.search_box = SearchBox()
        self.search_box.returnPressed.connect(self._on_search)
        layout.addWidget(self.search_box)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "secondary")
        layout.addWidget(self.status_label)

        self.results_list = CopyableListWidget()
        self.results_list.itemDoubleClicked.connect(self._on_result_activated)
        layout.addWidget(self.results_list, stretch=1)

        hint = QLabel("Double-click a result to jump to it in Nearby Mode (if currently live).")
        hint.setProperty("role", "secondary")
        layout.addWidget(hint)

    def _on_search(self) -> None:
        query = self.search_box.text().strip().lower()
        self.results_list.clear()
        if not query:
            self.status_label.setText("")
            return

        seen_ids: set[str] = set()
        results: list[tuple[str, str, str]] = []  # (target_id, label, type)

        for target in list(self._target_manager.cache.values()):
            if self._matches(target, query) and target.target_id not in seen_ids:
                seen_ids.add(target.target_id)
                results.append((target.target_id, self._label(target), "live"))

        for row in self._target_manager.known_targets():
            haystack = f"{row['name']} {row['target_id']}".lower()
            if query in haystack and row["target_id"] not in seen_ids:
                seen_ids.add(row["target_id"])
                results.append((row["target_id"], f"{row['name']} ({row['target_type']})", "history only"))

        if not results:
            self.status_label.setText(f"No matches for \"{query}\"")
            return

        self.status_label.setText(f"{len(results)} match(es) for \"{query}\"")
        for target_id, label, source in results:
            item = QListWidgetItem(f"{label} — {source}")
            item.setData(Qt.UserRole, target_id)
            self.results_list.addItem(item)

    @staticmethod
    def _matches(target, query: str) -> bool:
        is_aircraft = isinstance(target, Aircraft)
        fields = (
            [target.icao24, target.registration, target.callsign, target.aircraft_type]
            if is_aircraft
            else [target.mmsi, target.imo, target.name, target.callsign, target.ship_type]
        )
        return any(f and query in str(f).lower() for f in fields)

    @staticmethod
    def _label(target) -> str:
        if isinstance(target, Aircraft):
            return target.callsign or target.registration or target.icao24
        return target.name or target.mmsi

    def _on_result_activated(self, item: QListWidgetItem) -> None:
        # Selection/navigation into Nearby Mode's map+table is handled by
        # MainWindow, which owns both pages; this just signals the target_id.
        self.target_activated.emit(item.data(Qt.UserRole))
