"""QListWidget with Cmd+C/Ctrl+C copy support.

Plain QListWidget, like QTableView, has no built-in copy-to-clipboard —
used anywhere a page shows vessel/aircraft names in a list (Ports,
Airports, History) rather than the main TargetTable.
"""

from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QListWidget


class CopyableListWidget(QListWidget):
    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            selected = self.selectedItems() or [self.item(i) for i in range(self.count())]
            text = "\n".join(item.text() for item in selected)
            if text:
                QApplication.clipboard().setText(text)
            return
        super().keyPressEvent(event)
