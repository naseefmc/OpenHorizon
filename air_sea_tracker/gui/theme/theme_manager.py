"""Applies semantic theme tokens app-wide (GUI Design Guide §33).

Never hard-code colors in widgets; read them from ThemeManager.tokens
so Light/Dark/System switching stays instantaneous and consistent.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from gui.theme.dark_theme import DARK_THEME
from gui.theme.light_theme import LIGHT_THEME

THEMES = {"light": LIGHT_THEME, "dark": DARK_THEME}


class ThemeManager(QObject):
    theme_changed = Signal(str)  # emits 'light' or 'dark'

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._mode = "system"  # 'system' | 'light' | 'dark'

    @property
    def tokens(self) -> dict:
        return THEMES[self.effective_theme()]

    def effective_theme(self) -> str:
        if self._mode in ("light", "dark"):
            return self._mode
        # 'system': infer from the app's current palette
        is_dark = self._app.styleHints().colorScheme().name.lower() == "dark" if hasattr(
            self._app.styleHints(), "colorScheme"
        ) else self._app.palette().color(QPalette.Window).lightness() < 128
        return "dark" if is_dark else "light"

    def set_mode(self, mode: str) -> None:
        assert mode in ("system", "light", "dark")
        self._mode = mode
        self.apply()

    def apply(self) -> None:
        theme = self.effective_theme()
        t = THEMES[theme]
        self._app.setStyleSheet(self._build_stylesheet(t))
        self.theme_changed.emit(theme)

    @staticmethod
    def _build_stylesheet(t: dict) -> str:
        return f"""
        QWidget {{
            background-color: {t['background']};
            color: {t['text_primary']};
        }}
        QMainWindow, #Sidebar, #TopBar, #DetailDrawer {{
            background-color: {t['surface']};
        }}
        QWidget[role="surfaceElevated"] {{
            background-color: {t['surface_elevated']};
            border-radius: 12px;
        }}
        QLabel[role="secondary"] {{
            color: {t['text_secondary']};
        }}
        QLabel[role="muted"] {{
            color: {t['text_muted']};
        }}
        QFrame[role="separator"] {{
            background-color: {t['border']};
            max-height: 1px;
        }}
        QPushButton[role="primary"] {{
            background-color: {t['accent']};
            color: white;
            border-radius: 8px;
            padding: 8px 16px;
        }}
        QPushButton[role="primary"]:hover {{
            background-color: {t['accent_hover']};
        }}
        QPushButton[role="nav"]:checked {{
            background-color: {t['selection']};
        }}
        """
