"""Ocean & Environment location/vessel info sidebar (Ocean & Environment SDR §2, §5, §6, §7, §12, §13, §15, §19).

Renders whatever OceanData actually has — every field goes through
SourcedValue, so missing data always shows an explicit "No data
available" plus source/status rather than a blank or a substituted 0
(SDR §5, §18). Freshness is shown as a small status badge next to each
value (SDR §19).
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote_plus

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ocean.models.ocean_data import (
    STATUS_FORECAST,
    STATUS_HISTORICAL,
    STATUS_LIVE,
    STATUS_NEAR_REAL_TIME,
    STATUS_STATIC,
    OceanData,
    SourcedValue,
)
from ocean.models.ocean_location import SelectedLocation

_BADGE_SYMBOLS = {
    STATUS_LIVE: "●",
    STATUS_NEAR_REAL_TIME: "●",
    STATUS_FORECAST: "●",
    STATUS_HISTORICAL: "●",
    STATUS_STATIC: "●",
}


def _freshness_badge(sv: SourcedValue) -> str:
    if not sv.available:
        return "○ unavailable"
    symbol = _BADGE_SYMBOLS.get(sv.status, "●")
    return f"{symbol} {sv.status.lower().replace('-', ' ')}"


def _format_timestamp(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y %H:%M UTC")
    except ValueError:
        return raw


class OceanSidebar(QScrollArea):
    use_as_observer = Signal(float, float)  # lat, lon

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFixedWidth(320)
        self.setProperty("role", "surfaceElevated")

        self._body = QWidget()
        self._layout = QVBoxLayout(self._body)
        self.setWidget(self._body)

        self._placeholder = QLabel("Click anywhere on the map for ocean & environment data.")
        self._placeholder.setWordWrap(True)
        self._placeholder.setProperty("role", "secondary")
        self._layout.addWidget(self._placeholder)
        self._layout.addStretch()

    # --- building blocks -------------------------------------------------

    def _clear(self) -> None:
        self._clear_layout(self._layout)

    @classmethod
    def _clear_layout(cls, layout) -> None:
        # Section content is added via addLayout() (each section is its own
        # QFormLayout), not addWidget() — takeAt(0).widget() is None for
        # those items, so a shallow clear leaves every previous section's
        # rows still parented to self._body, just outside any layout, where
        # they stay frozen in their last painted position and visually
        # overlap the next render. Recurse into nested layouts too.
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                continue
            child_layout = item.layout()
            if child_layout is not None:
                cls._clear_layout(child_layout)

    @staticmethod
    def _section_header(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "sectionHeader")
        return label

    @staticmethod
    def _species_link_label(obs) -> QLabel:
        # Google Images search, not a fixed image URL — OBIS has no photo
        # field, and a search link degrades gracefully for any scientific
        # name rather than risking a broken direct image link.
        image_search_url = f"https://www.google.com/search?tbm=isch&q={quote_plus(obs.scientific_name)}"
        suffix = f" ({obs.classification})" if obs.classification else ""
        date_suffix = f" — last observed {obs.observed_on}" if obs.observed_on else ""
        label = QLabel(f'· <a href="{image_search_url}">{obs.scientific_name}</a>{suffix}{date_suffix}')
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _field_row(form: QFormLayout, label: str, sv: SourcedValue | None, fmt) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        if sv is None or not sv.available:
            text = "No data available"
            badge = "○ unavailable" if sv is not None else ""
            tooltip = sv.note if sv is not None else None
        else:
            text = fmt(sv.value)
            badge = _freshness_badge(sv)
            tooltip = sv.note

        value_label = QLabel(text)
        value_label.setWordWrap(True)
        if tooltip:
            value_label.setToolTip(tooltip)
        row_layout.addWidget(value_label, stretch=1)
        if badge:
            badge_label = QLabel(badge)
            badge_label.setProperty("role", "secondary")
            row_layout.addWidget(badge_label)
        form.addRow(label, row)

    # --- public API --------------------------------------------------------

    def show_loading(self) -> None:
        self._clear()
        label = QLabel("Loading ocean & environment data…")
        label.setProperty("role", "secondary")
        self._layout.addWidget(label)
        self._layout.addStretch()

    def show_location(self, location: SelectedLocation, data: OceanData) -> None:
        self._clear()

        self._layout.addWidget(self._section_header("LOCATION"))
        loc_form = QFormLayout()
        loc_form.addRow("Latitude", QLabel(f"{location.latitude:.5f}°"))
        loc_form.addRow("Longitude", QLabel(f"{location.longitude:.5f}°"))
        self._layout.addLayout(loc_form)

        observer_button = QPushButton("Use as observer location")
        observer_button.setToolTip("Set this point as the observer location on the Nearby tab and switch to it.")
        observer_button.clicked.connect(
            lambda: self.use_as_observer.emit(location.latitude, location.longitude)
        )
        self._layout.addWidget(observer_button)

        self._layout.addWidget(self._section_header("OCEAN"))
        ocean_form = QFormLayout()
        self._field_row(ocean_form, "Depth", data.depth_m, lambda v: f"{v:.0f} m")
        self._field_row(ocean_form, "Elevation", data.seabed_elevation_m, lambda v: f"{v:.0f} m")
        self._field_row(ocean_form, "Sea surface temperature", data.sea_surface_temperature_c, lambda v: f"{v:.1f} °C")
        self._layout.addLayout(ocean_form)

        note = QLabel("Approximate bathymetric data. Not for navigation.")
        note.setWordWrap(True)
        note.setProperty("role", "secondary")
        self._layout.addWidget(note)

        self._layout.addWidget(self._section_header("GEOGRAPHY"))
        geo_form = QFormLayout()
        self._field_row(geo_form, "Water body", data.water_body, str)
        self._field_row(geo_form, "Nearest coast", data.nearest_coast_distance_km, lambda v: f"{v:.1f} km")
        self._layout.addLayout(geo_form)

        self._add_phase2_sections(data)

        self._layout.addWidget(self._section_header("DATA"))
        data_form = QFormLayout()
        self._add_source_rows(data_form, data)
        self._layout.addLayout(data_form)

        self._layout.addStretch()

    # --- Phase 2 -------------------------------------------------------

    def _add_phase2_sections(self, data: OceanData) -> None:
        if data.waves is not None or data.current is not None:
            self._layout.addWidget(self._section_header("OCEAN CONDITIONS"))
            form = QFormLayout()
            if data.waves is not None:
                self._field_row(form, "Wave height", data.waves.height_m, lambda v: f"{v:.1f} m")
                self._field_row(form, "Wave direction", data.waves.direction_deg, lambda v: f"{v:.0f}°")
                self._field_row(form, "Wave period", data.waves.period_s, lambda v: f"{v:.1f} s")
            if data.current is not None:
                self._field_row(form, "Current speed", data.current.speed_kn, lambda v: f"{v:.2f} kn")
                self._field_row(form, "Current direction", data.current.direction_deg, lambda v: f"{v:.0f}°")
            self._layout.addLayout(form)

        if data.wind is not None or data.rain_mm is not None or data.cloud_cover_pct is not None:
            self._layout.addWidget(self._section_header("WEATHER"))
            form = QFormLayout()
            if data.wind is not None:
                self._field_row(form, "Wind speed", data.wind.speed_kn, lambda v: f"{v:.1f} kn")
                self._field_row(form, "Wind direction", data.wind.direction_deg, lambda v: f"{v:.0f}°")
                self._field_row(form, "Gust", data.wind.gust_kn, lambda v: f"{v:.1f} kn")
            if data.rain_mm is not None:
                self._field_row(form, "Rain (1h)", data.rain_mm, lambda v: f"{v:.1f} mm")
            if data.cloud_cover_pct is not None:
                self._field_row(form, "Cloud cover", data.cloud_cover_pct, lambda v: f"{v:.0f}%")
            self._layout.addLayout(form)

        if data.salinity is not None or data.sea_level_anomaly_cm is not None:
            self._layout.addWidget(self._section_header("SALINITY & SEA LEVEL"))
            form = QFormLayout()
            if data.salinity is not None:
                self._field_row(form, "Salinity", data.salinity, lambda v: f"{v:.1f} PSU")
            if data.sea_level_anomaly_cm is not None:
                self._field_row(form, "Sea level anomaly", data.sea_level_anomaly_cm, lambda v: f"{v:+.1f} cm")
            self._layout.addLayout(form)

            hint = QLabel(
                "Salinity: ~32-37 PSU typical, lower = fresher, higher = saltier. Sea level "
                "anomaly: deviation from this location's long-term average, not tide or depth. "
                "Map colours for both run blue/purple (low) to red (high) — hover a value above "
                "for the exact scale."
            )
            hint.setWordWrap(True)
            hint.setProperty("role", "secondary")
            self._layout.addWidget(hint)

        if data.fishing_activity_hours is not None or data.marine_protected_area is not None:
            self._layout.addWidget(self._section_header("HUMAN ACTIVITY & PROTECTION"))
            form = QFormLayout()
            if data.fishing_activity_hours is not None:
                self._field_row(form, "Fishing activity", data.fishing_activity_hours, lambda v: f"{v:.1f} vessel-hrs")
            if data.marine_protected_area is not None:
                self._field_row(form, "Protected area", data.marine_protected_area, str)
            self._layout.addLayout(form)

            fa = data.fishing_activity_hours
            if fa is not None and fa.available and fa.timestamp:
                freshness = QLabel(f"Fishing activity data covers up to {fa.timestamp} (GFW's pipeline lags real time by a few days).")
                freshness.setWordWrap(True)
                freshness.setProperty("role", "secondary")
                self._layout.addWidget(freshness)

        if data.species is not None:
            self._layout.addWidget(self._section_header("SPECIES OBSERVATIONS"))
            species = data.species
            if species.note and species.records == 0:
                label = QLabel(species.note)
                label.setWordWrap(True)
                label.setProperty("role", "secondary")
                self._layout.addWidget(label)
            else:
                form = QFormLayout()
                form.addRow("Radius", QLabel(f"{species.radius_km:.0f} km"))
                form.addRow("Records", QLabel(str(species.records)))
                form.addRow("Species", QLabel(str(species.species_count)))
                self._layout.addLayout(form)
                if species.recent:
                    recent_header = QLabel("Species observed nearby")
                    recent_header.setProperty("role", "secondary")
                    self._layout.addWidget(recent_header)
                    for obs in species.recent:
                        self._layout.addWidget(self._species_link_label(obs))
                source_label = QLabel(f"Source: {species.source} · historical/recent observations, not live tracking")
                source_label.setProperty("role", "secondary")
                source_label.setWordWrap(True)
                self._layout.addWidget(source_label)

    # --- source/timestamp summary ---------------------------------------

    @staticmethod
    def _add_source_rows(form: QFormLayout, data: OceanData) -> None:
        rows = [
            ("Depth source", data.depth_m),
            ("SST source", data.sea_surface_temperature_c),
            ("SST timestamp", data.sea_surface_temperature_c, "timestamp"),
            ("Water body source", data.water_body),
            ("Nearest coast source", data.nearest_coast_distance_km),
        ]
        for row in rows:
            label = row[0]
            sv: SourcedValue = row[1]
            if not sv.available:
                continue
            if len(row) == 3:
                ts = _format_timestamp(sv.timestamp)
                if ts:
                    form.addRow(label, QLabel(ts))
                continue
            form.addRow(label, QLabel(sv.source))
