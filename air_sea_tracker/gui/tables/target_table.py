"""Live target table view: sortable, filterable, synced to map selection (GUI §8)."""

from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMenu, QTableView, QWidget
from PySide6.QtCore import Signal

from gui.tables.target_model import TargetTableModel
from utils.web_search import open_google_image_search


class TargetTable(QTableView):
    row_selected = Signal(str)  # target_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = TargetTableModel(self)
        self.setModel(self._model)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.clicked.connect(self._on_row_clicked)

    def _on_row_clicked(self, index) -> None:
        target_id = self._model.target_id_at(index.row())
        if target_id:
            self.row_selected.emit(target_id)

    def keyPressEvent(self, event) -> None:
        # No default copy support on QTableView — cells aren't editable, so
        # there's normally no way to select/copy a name (or any cell) at all.
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selection()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        index = self.indexAt(event.pos())
        menu = QMenu(self)
        menu.addAction("Copy", self._copy_selection)
        if index.isValid():
            name = self._model.name_at(index.row())
            if name:
                kind = self._model.kind_at(index.row())
                label = name if len(name) <= 40 else f"{name[:37]}..."
                menu.addAction(
                    f'Search "{label}" on Google Images',
                    lambda: open_google_image_search(name, kind),
                )
        menu.exec(event.globalPos())

    def _copy_selection(self) -> None:
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        indexes.sort(key=lambda i: (i.row(), i.column()))
        rows: dict[int, dict[int, str]] = {}
        for idx in indexes:
            rows.setdefault(idx.row(), {})[idx.column()] = str(idx.data() or "")
        lines = ["\t".join(cols[c] for c in sorted(cols)) for cols in rows.values()]
        QApplication.clipboard().setText("\n".join(lines))

    @property
    def model_(self) -> TargetTableModel:
        return self._model
