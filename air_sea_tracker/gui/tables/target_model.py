"""Qt model/view table model for live targets (GUI §34, SDR §8).

Uses QAbstractTableModel rather than one widget per cell so the table
stays responsive with tens of thousands of rows (SDR §24).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

COLUMNS = ["Type", "Name", "Distance", "Speed", "Heading", "Altitude/Status", "Destination", "Updated"]


class TargetTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        row = self._rows[index.row()]
        key = COLUMNS[index.column()].lower().replace("/", "_").replace(" ", "_")
        return row.get(key, "")

    def target_id_at(self, row: int) -> str | None:
        if 0 <= row < len(self._rows):
            return self._rows[row].get("target_id")
        return None

    def replace_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
