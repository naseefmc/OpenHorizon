"""Ocean & Environment tab page (Ocean & Environment SDR §2-5, §14).

Assembles the Layer Controls panel, map, sidebar, and time control around
one OceanController, matching the SDR's architecture:

    GUI -> OceanController -> Provider abstraction -> GEBCO/NOAA/OSM/... (§8)
"""

from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from gui.map.ocean_map import OceanMap
from gui.panels.ocean_layers_panel import OceanLayersPanel
from gui.panels.ocean_sidebar import OceanSidebar
from gui.widgets.time_control import TimeControl
from ocean.layers.layer_registry import build_layers
from ocean.models.ocean_location import SelectedLocation
from ocean.ocean_controller import OceanController

logger = logging.getLogger(__name__)


class OceanPage(QWidget):
    use_as_observer_requested = Signal(float, float)  # lat, lon — bubbled up to MainWindow

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = OceanController()
        self._layer_defs = build_layers()
        self._layer_by_id = {d.layer_id: d for d in self._layer_defs}
        self._current_location: SelectedLocation | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.time_control = TimeControl()
        self.time_control.time_changed.connect(self._on_time_changed)
        root.addWidget(self.time_control)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, stretch=1)

        self.layers_panel = OceanLayersPanel(self._layer_defs)
        self.layers_panel.layer_toggled.connect(self._on_layer_toggled)
        self.layers_panel.species_filter_changed.connect(self._on_species_filter_changed)
        body.addWidget(self.layers_panel)

        self.map = OceanMap()
        self.map.loadFinished.connect(self._on_map_loaded)
        self.map.location_clicked.connect(self._on_map_clicked)
        body.addWidget(self.map, stretch=1)

        self.sidebar = OceanSidebar()
        self.sidebar.use_as_observer.connect(self.use_as_observer_requested)
        body.addWidget(self.sidebar)

    # --- map lifecycle ----------------------------------------------------

    def _on_map_loaded(self, ok: bool) -> None:
        if not ok:
            logger.error("Ocean map failed to load")
            return
        for layer_def in self._layer_defs:
            if layer_def.available and layer_def.default_on:
                self.map.set_layer(layer_def.layer_id, layer_def.tile_spec(), True)

    def _on_layer_toggled(self, layer_id: str, enabled: bool) -> None:
        layer_def = self._layer_by_id.get(layer_id)
        if layer_def is not None and layer_def.tile_spec() is not None:
            self.map.set_layer(layer_id, layer_def.tile_spec(), enabled)
        # A Phase 2 data-only layer (waves/wind/salinity/marine_life/...)
        # has no tile, but toggling it changes which fields the controller
        # queries — refresh whatever's currently shown so the sidebar
        # reflects the new set immediately rather than on the next click.
        self._refresh_current_selection()

    def _on_species_filter_changed(self, taxon) -> None:
        self._refresh_current_selection()

    # --- click / selection handling ---------------------------------------

    def _on_map_clicked(self, lat: float, lon: float) -> None:
        self._current_location = SelectedLocation.now(lat, lon)
        self.sidebar.show_loading()
        asyncio.ensure_future(self._load_location(self._current_location))

    def _on_time_changed(self, when) -> None:
        self._refresh_current_selection()

    def _refresh_current_selection(self) -> None:
        if self._current_location is not None:
            asyncio.ensure_future(self._load_location(self._current_location))

    async def _load_location(self, location: SelectedLocation) -> None:
        data = await self._controller.query_location(
            location,
            enabled_layers=self.layers_panel.enabled_layer_ids(),
            when=self.time_control.current_when,
            species_filter=self.layers_panel.species_filter(),
        )
        if self._current_location is not location:
            return  # a newer click superseded this one while we were awaiting
        self.sidebar.show_location(location, data)
