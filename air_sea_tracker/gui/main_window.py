"""Main application window: nav rail + top bar + stacked pages (GUI §2)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from config.settings import Settings
from gui.navigation.sidebar import MODES, Sidebar
from gui.navigation.topbar import TopBar
from gui.pages.airports_page import AirportsPage
from gui.pages.global_page import GlobalPage
from gui.pages.history_page import HistoryPage
from gui.pages.nearby_page import NearbyPage
from gui.pages.ports_page import PortsPage
from gui.pages.search_page import SearchPage
from gui.pages.settings_page import SettingsPage
from gui.theme.theme_manager import ThemeManager
from services.target_manager import TargetManager


class MainWindow(QMainWindow):
    observer_changed = Signal(float, float)  # bubbled up so main.py can (re)start collectors
    ais_credential_changed = Signal()
    closing = Signal()

    def __init__(self, settings: Settings, theme_manager: ThemeManager, target_manager: TargetManager) -> None:
        super().__init__()
        self._settings = settings
        self._theme_manager = theme_manager
        self._target_manager = target_manager

        self.setWindowTitle("AIRSEA — Air & Sea Live Tracker")
        self.resize(1440, 900)
        self.setMinimumSize(1280, 720)  # GUI §31: usable down to 1280x720

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.top_bar = TopBar()
        self.top_bar.theme_toggle_requested.connect(self._cycle_theme)
        self.top_bar.settings_requested.connect(lambda: self._select_mode("settings"))
        root_layout.addWidget(self.top_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root_layout.addLayout(body)

        self.sidebar = Sidebar()
        self.sidebar.mode_selected.connect(self._select_mode)
        body.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        self._page_index: dict[str, int] = {}
        self._register_page("global", GlobalPage(target_manager))
        self.nearby_page = NearbyPage(target_manager, settings)
        self.nearby_page.observer_changed.connect(self._on_observer_changed)
        self._register_page("nearby", self.nearby_page)
        self._register_page("ports", PortsPage(target_manager))
        self._register_page("airports", AirportsPage(target_manager))
        self._register_page("history", HistoryPage(target_manager))
        self.search_page = SearchPage(target_manager)
        self.search_page.target_activated.connect(self._on_search_target_activated)
        self._register_page("search", self.search_page)
        self.settings_page = SettingsPage(settings, theme_manager)
        self.settings_page.ais_credential_changed.connect(self.ais_credential_changed)
        self._register_page("settings", self.settings_page)
        body.addWidget(self.pages, stretch=1)

        self._select_mode(settings.last_mode if settings.last_mode in MODES else "nearby")

    def restore_last_observer(self) -> None:
        # Called explicitly by main.py, after LiveDataController is wired to
        # observer_changed — NOT from __init__: emitting here would fire
        # before any listener is connected (signals with no connected slots
        # are a silent no-op), so the initial restore would never actually
        # start the AIS/ADS-B providers.
        # SDR §27.3: restore previous session's observer location/radius on startup.
        lat, lon = self._settings.observer_lat, self._settings.observer_lon
        if lat is not None and lon is not None:
            self.nearby_page.set_initial_observer(lat, lon, self._settings.radius_km)
            self.top_bar.set_observer_location(f"{lat:.4f}, {lon:.4f}")
            self.observer_changed.emit(lat, lon)

    def _on_observer_changed(self, lat: float, lon: float) -> None:
        self._settings.set_observer_location(lat, lon)
        self._settings.radius_km = self.nearby_page.observer_panel.radius_km
        self.top_bar.set_observer_location(f"{lat:.4f}, {lon:.4f}")
        self.observer_changed.emit(lat, lon)

    def _on_search_target_activated(self, target_id: str) -> None:
        self._select_mode("nearby")
        self.nearby_page.select_target(target_id)

    def _register_page(self, mode: str, widget: QWidget) -> None:
        self._page_index[mode] = self.pages.addWidget(widget)

    def _select_mode(self, mode: str) -> None:
        if mode not in self._page_index:
            return
        self.pages.setCurrentIndex(self._page_index[mode])
        self.sidebar.select_mode(mode)
        self._settings.last_mode = mode

    def _cycle_theme(self) -> None:
        order = ["system", "light", "dark"]
        current = self._settings.theme if self._settings.theme in order else "system"
        next_mode = order[(order.index(current) + 1) % len(order)]
        self._settings.theme = next_mode
        self._theme_manager.set_mode(next_mode)

    def closeEvent(self, event) -> None:
        # SDR §27.2: critical settings persisted immediately, not only on clean shutdown,
        # but flush explicitly here too.
        self._settings.set("window/geometry", self.saveGeometry())
        self.closing.emit()
        super().closeEvent(event)
