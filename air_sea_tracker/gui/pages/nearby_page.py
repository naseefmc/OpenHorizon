"""Nearby / Observer Mode (SDR §4, GUI §5) — map + synced live table."""

from __future__ import annotations

import asyncio
from typing import Callable

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from config.settings import Settings
from gui.map.live_map import LiveMap
from gui.map.map_controls import MapControls
from gui.panels.observer_panel import ObserverPanel
from gui.panels.research_dialog import ResearchDialog
from gui.panels.target_drawer import TargetDrawer
from gui.tables.target_table import TargetTable
from models.aircraft import Aircraft
from services import enrichment_service, value_estimator
from services.geo_service import is_geometrically_visible
from services.target_manager import TargetManager
from utils.time_format import timestamp_with_age
from utils.units import speed_label

MAP_REFRESH_MS = 2000  # SDR §24: map refresh ~1-5s in Nearby Mode


class NearbyPage(QWidget):
    observer_changed = Signal(float, float)  # lat, lon — bubbled up so main.py can (re)start collectors

    def __init__(self, target_manager: TargetManager, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_manager = target_manager
        self._settings = settings
        self._selected_id: str | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- map + table (vertical split) ---
        center = QSplitter(Qt.Vertical)

        self._map_container = QWidget()
        map_layout = QVBoxLayout(self._map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(0)

        # Observer/map controls are docked in a row above the map rather than
        # floated on top of it: QWebEngineView paints through its own native
        # compositor surface, so plain QWidgets positioned via move()/raise_()
        # on top of it do not reliably stack above it (notably on macOS) and
        # end up invisible/unclickable. Docking sidesteps that entirely.
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(12, 12, 12, 8)

        self.observer_panel = ObserverPanel()
        self.observer_panel.altitude_spin.setValue(settings.observer_altitude_m)
        self.observer_panel.radius_changed.connect(self._on_radius_changed)
        self.observer_panel.observer_set.connect(self._on_observer_set)
        self.observer_panel.filters_changed.connect(self._on_filters_changed)
        self.observer_panel.vessel_class_filter_changed.connect(self._on_vessel_class_filter_changed)
        self.observer_panel.altitude_changed.connect(self._on_altitude_changed)
        controls_row.addWidget(self.observer_panel)
        controls_row.addStretch(1)

        self.map_controls = MapControls()
        self.map_controls.zoom_in_requested.connect(self._on_zoom_in)
        self.map_controls.zoom_out_requested.connect(self._on_zoom_out)
        self.map_controls.center_requested.connect(self._on_center_requested)
        self.map_controls.layers_requested.connect(self._on_layers_requested)
        self.map_controls.fullscreen_requested.connect(self._on_fullscreen_requested)
        controls_row.addWidget(self.map_controls, alignment=Qt.AlignTop)

        map_layout.addLayout(controls_row)

        self.live_map = LiveMap()
        map_layout.addWidget(self.live_map, stretch=1)

        self.table = TargetTable()
        self.table.row_selected.connect(self._on_row_selected)

        center.addWidget(self._map_container)
        center.addWidget(self.table)
        center.setStretchFactor(0, 7)  # GUI §2: map ~65-75%, table ~25-35%
        center.setStretchFactor(1, 3)
        root.addWidget(center, stretch=1)

        # --- target detail drawer (SDR §15, GUI §10) ---
        self.drawer = TargetDrawer()
        self.drawer.closed.connect(self._on_drawer_closed)
        self.drawer.track_requested.connect(self._on_track_requested)
        self.drawer.research_requested.connect(self._on_research_requested)
        self.drawer.hide()
        root.addWidget(self.drawer)

        self.live_map.marker_clicked.connect(self._on_marker_clicked)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(MAP_REFRESH_MS)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()

    # --- observer / filter wiring ---

    def _on_observer_set(self, lat: float, lon: float) -> None:
        self._target_manager.set_observer(lat, lon)
        self.live_map.set_observer(lat, lon)
        self.live_map.set_radius_km(lat, lon, self.observer_panel.radius_km)
        self.observer_changed.emit(lat, lon)
        self.refresh()

    def _on_radius_changed(self, radius_km: float) -> None:
        self._target_manager.set_radius(radius_km)
        if self._target_manager.observer_lat is not None:
            self.live_map.set_radius_km(self._target_manager.observer_lat, self._target_manager.observer_lon, radius_km)
        self.refresh()

    def _on_filters_changed(self, air_enabled: bool, sea_enabled: bool) -> None:
        self._target_manager.set_filters(air_enabled, sea_enabled)
        self.refresh()

    def _on_vessel_class_filter_changed(self, class_a_enabled: bool, class_b_enabled: bool) -> None:
        self._target_manager.set_vessel_class_filter(class_a_enabled, class_b_enabled)
        self.refresh()

    def _on_altitude_changed(self, altitude_m: float) -> None:
        self._settings.observer_altitude_m = altitude_m

    # --- map controls (SDR §16-17, GUI §7) ---

    def _on_zoom_in(self) -> None:
        self.live_map.zoom_in()

    def _on_zoom_out(self) -> None:
        self.live_map.zoom_out()

    def _on_center_requested(self) -> None:
        lat, lon = self._target_manager.observer_lat, self._target_manager.observer_lon
        if lat is not None and lon is not None:
            self.live_map.set_observer(lat, lon)

    def _on_layers_requested(self) -> None:
        self.live_map.toggle_dark_layer()

    def _on_fullscreen_requested(self) -> None:
        window = self.window()
        if window.isFullScreen():
            window.showNormal()
        else:
            window.showFullScreen()

    def set_initial_observer(self, lat: float, lon: float, radius_km: float) -> None:
        """Called on startup to restore last session (SDR §27.3) without re-emitting observer_changed."""
        self.observer_panel.set_coordinates(lat, lon)
        self.observer_panel.radius_slider.setValue(int(radius_km))
        self.observer_panel.set_observer_location(f"{lat:.4f}, {lon:.4f}")
        self._target_manager.set_observer(lat, lon)
        self._target_manager.set_radius(radius_km)
        self.live_map.set_observer(lat, lon)
        self.live_map.set_radius_km(lat, lon, radius_km)

    # --- selection sync (map <-> table <-> drawer) ---

    def _on_row_selected(self, target_id: str) -> None:
        self._select_target(target_id)

    def _on_marker_clicked(self, target_id: str) -> None:
        self._select_target(target_id)

    def select_target(self, target_id: str) -> None:
        """Public entry point for other pages (e.g. Search) to jump here."""
        self._select_target(target_id)

    def _select_target(self, target_id: str) -> None:
        self._selected_id = target_id
        self.live_map.highlight_marker(target_id)

        for target, distance_km, _bearing in self._target_manager.nearby():
            if target.target_id == target_id:
                is_aircraft = isinstance(target, Aircraft)
                name = (target.callsign or target.icao24) if is_aircraft else (target.name or target.mmsi)
                subtitle = f"{'Aircraft' if is_aircraft else 'Vessel'} • {distance_km:.1f} km away"
                self.drawer.show_target(target_id, name, subtitle)
                speed = target.ground_speed if is_aircraft else target.speed_over_ground
                heading = target.track if is_aircraft else target.effective_heading
                self.drawer.telemetry.set_value("Speed", speed_label(speed))
                self.drawer.telemetry.set_value("Course", f"{heading:.0f}°" if heading is not None else "—")
                self.drawer.telemetry.set_value("Distance", f"{distance_km:.1f} km")
                target_alt = target.altitude_m if is_aircraft else 0.0
                visible = is_geometrically_visible(distance_km, self._settings.observer_altitude_m, target_alt)
                self.drawer.telemetry.set_value("Visibility", "In view" if visible else "Below horizon")
                self.drawer.status_badge.set_state("live")
                self.drawer.set_details(self._target_details(target, is_aircraft))
                self.drawer.show()
                break

    @staticmethod
    def _target_details(target, is_aircraft: bool) -> list[tuple[str, str]]:
        def field(label: str, value) -> tuple[str, str] | None:
            return (label, str(value)) if value not in (None, "") else None

        if is_aircraft:
            rows = [
                field("Last update", timestamp_with_age(target.last_update)),
                field("ICAO24", target.icao24),
                field("Registration", target.registration),
                field("Callsign", target.callsign),
                field("Type", target.aircraft_type),
                field("Origin country", target.origin_country),
                field("Squawk", target.squawk),
                field("Source", target.source),
            ]
        else:
            rows = [
                field("Last update", timestamp_with_age(target.last_update)),
                field("MMSI", target.mmsi),
                field("IMO", target.imo),
                field("Callsign", target.callsign),
                field("Class", target.ais_class),
                field("Ship type", target.ship_type),
                field("Flag", target.flag),
                field("Length", f"{target.length_m:.0f} m" if target.length_m else None),
                field("Width", f"{target.width_m:.0f} m" if target.width_m else None),
                field("Draught", f"{target.draught_m:.1f} m" if target.draught_m else None),
                field("Destination", target.destination),
                field("Nav status", target.navigation_status),
                field("Source", target.source),
            ]
        return [r for r in rows if r is not None]

    def _on_track_requested(self, target_id: str) -> None:
        if self.drawer.track_btn.isChecked():
            points = [(p["lat"], p["lon"]) for p in self._target_manager.track(target_id)]
            self.live_map.draw_track(points)
        else:
            self.live_map.clear_track()

    def _on_research_requested(self, target_id: str) -> None:
        target = self._target_manager.get_target(target_id)
        if target is None:
            return
        is_aircraft = isinstance(target, Aircraft)
        title = (target.callsign or target.icao24) if is_aircraft else (target.name or target.mmsi)
        dialog = ResearchDialog(title, self)
        dialog.show_loading()
        dialog.show()
        asyncio.ensure_future(self._run_research(dialog, target, is_aircraft))

    @staticmethod
    async def _run_research(dialog: ResearchDialog, target, is_aircraft: bool) -> None:
        if is_aircraft:
            result = await enrichment_service.research_aircraft(target.registration, target.icao24)
            dialog.show_result(result)
            return

        result = await enrichment_service.research_vessel(target.mmsi, target.imo)
        dialog.show_result(result)

        build_year = None
        for f in result.fields:
            if f.label == "Built":
                try:
                    build_year = int(f.value[:4])
                except ValueError:
                    pass
        estimate = value_estimator.estimate_vessel_value(target.length_m, target.ship_type, build_year)
        dialog.show_value_estimate(estimate)

    def _on_drawer_closed(self) -> None:
        self._selected_id = None
        self.live_map.highlight_marker(None)
        self.live_map.clear_track()
        self.drawer.hide()

    # --- periodic refresh (SDR §24) ---

    def refresh(self) -> None:
        rows = self._target_manager.table_rows()
        self.table.model_.replace_rows(rows)

        markers = []
        for target, _distance_km, _bearing in self._target_manager.nearby():
            is_aircraft = isinstance(target, Aircraft)
            heading = target.track if is_aircraft else target.effective_heading
            label = (target.callsign or target.icao24) if is_aircraft else (target.name or target.mmsi)
            markers.append({
                "id": target.target_id,
                "lat": target.latitude,
                "lon": target.longitude,
                "heading": heading,
                "category": "aircraft" if is_aircraft else "vessel",
                "label": label,
            })
        self.live_map.sync_markers(markers)
