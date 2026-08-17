"""QListWidget with Cmd+C/Ctrl+C copy support and a right-click menu.

Plain QListWidget, like QTableView, has no built-in copy-to-clipboard —
used anywhere a page shows vessel/aircraft names in a list (Ports,
Airports, History) rather than the main TargetTable.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QListWidget, QMenu

from utils.web_search import open_google_image_search

# Optional per-item search text (e.g. a clean vessel/aircraft name) distinct
# from the item's display text, which may have extra annotations appended
# (type, last-seen age) that would pollute a Google search query.
SEARCH_TEXT_ROLE = Qt.UserRole + 1
# Optional per-item "vessel"/"aircraft" hint, appended to the search query
# for more relevant image-search results.
SEARCH_KIND_ROLE = Qt.UserRole + 2


class CopyableListWidget(QListWidget):
    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selection()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        menu = QMenu(self)
        menu.addAction("Copy", self._copy_selection)
        if item is not None:
            search_text = item.data(SEARCH_TEXT_ROLE) or item.text()
            kind = item.data(SEARCH_KIND_ROLE)
            label = search_text if len(search_text) <= 40 else f"{search_text[:37]}..."
            menu.addAction(
                f'Search "{label}" on Google Images',
                lambda: open_google_image_search(search_text, kind),
            )
        menu.exec(event.globalPos())

    def _copy_selection(self) -> None:
        selected = self.selectedItems() or [self.item(i) for i in range(self.count())]
        text = "\n".join(item.text() for item in selected)
        if text:
            QApplication.clipboard().setText(text)
