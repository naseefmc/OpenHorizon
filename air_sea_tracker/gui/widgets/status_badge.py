"""LIVE / CACHED / OFFLINE badge (GUI §25). Never color-only."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel


class StatusBadge(QLabel):
    SYMBOLS = {"live": "●", "cached": "◐", "offline": "○"}

    def __init__(self, state: str = "offline", detail: str = "") -> None:
        super().__init__()
        self.set_state(state, detail)

    def set_state(self, state: str, detail: str = "") -> None:
        symbol = self.SYMBOLS.get(state, "○")
        text = f"{symbol} {state.upper()}"
        if detail:
            text += f" · {detail}"
        self.setText(text)
        self.setProperty("state", state)
