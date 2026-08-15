"""Floating observer/range control over the map (SDR §4, GUI §5)."""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from config.settings import DEFAULT_OBSERVER_LAT, DEFAULT_OBSERVER_LON

QUICK_RADII_KM = [10, 25, 50, 100, 250, 500]

# Matches "43.5081, 16.4402" (also without a comma, or extra whitespace) —
# the format Google Maps puts on the clipboard when you copy coordinates.
COORD_PASTE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)\s*$")


class ObserverPanel(QWidget):
    radius_changed = Signal(float)
    observer_set = Signal(float, float)  # lat, lon
    filters_changed = Signal(bool, bool)  # air, sea
    vessel_class_filter_changed = Signal(bool, bool)  # class A, class B

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "surfaceElevated")
        self.setFixedWidth(340)

        layout = QVBoxLayout(self)
        self.location_label = QLabel("Observer: not set")
        layout.addWidget(self.location_label)

        coord_row = QHBoxLayout()
        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90.0, 90.0)
        self.lat_spin.setDecimals(4)
        self.lat_spin.setPrefix("Lat ")
        self.lat_spin.setValue(DEFAULT_OBSERVER_LAT)
        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180.0, 180.0)
        self.lon_spin.setDecimals(4)
        self.lon_spin.setPrefix("Lon ")
        self.lon_spin.setValue(DEFAULT_OBSERVER_LON)
        self.lat_spin.installEventFilter(self)
        self.lon_spin.installEventFilter(self)
        set_btn = QPushButton("Set")
        set_btn.setProperty("role", "primary")
        set_btn.clicked.connect(self._on_set_clicked)
        coord_row.addWidget(self.lat_spin)
        coord_row.addWidget(self.lon_spin)
        coord_row.addWidget(set_btn)
        layout.addLayout(coord_row)

        radius_row = QHBoxLayout()
        radius_row.addWidget(QLabel("Range"))
        self.radius_slider = QSlider(Qt.Horizontal)
        self.radius_slider.setRange(1, 500)
        self.radius_slider.setValue(100)
        self.radius_value_label = QLabel("100 km")
        self.radius_slider.valueChanged.connect(self._on_slider_changed)
        radius_row.addWidget(self.radius_slider)
        radius_row.addWidget(self.radius_value_label)
        layout.addLayout(radius_row)

        chips_row = QHBoxLayout()
        for km in QUICK_RADII_KM:
            btn = QPushButton(f"{km} km")
            btn.clicked.connect(lambda checked=False, k=km: self.radius_slider.setValue(k))
            chips_row.addWidget(btn)
        layout.addLayout(chips_row)

        filters_row = QHBoxLayout()
        self.air_checkbox = QCheckBox("Air")
        self.air_checkbox.setChecked(True)
        self.air_checkbox.toggled.connect(self._on_filters_changed)
        self.sea_checkbox = QCheckBox("Sea")
        self.sea_checkbox.setChecked(True)
        self.sea_checkbox.toggled.connect(self._on_filters_changed)
        filters_row.addWidget(self.air_checkbox)
        filters_row.addWidget(self.sea_checkbox)
        layout.addLayout(filters_row)

        class_row = QHBoxLayout()
        self.class_a_checkbox = QCheckBox("Class A")
        self.class_a_checkbox.setToolTip("Mandatory transponders — larger commercial vessels")
        self.class_a_checkbox.setChecked(True)
        self.class_a_checkbox.toggled.connect(self._on_vessel_class_filter_changed)
        self.class_b_checkbox = QCheckBox("Class B")
        self.class_b_checkbox.setToolTip("Lower-power transponders — leisure/small craft")
        self.class_b_checkbox.setChecked(True)
        self.class_b_checkbox.toggled.connect(self._on_vessel_class_filter_changed)
        class_row.addWidget(self.class_a_checkbox)
        class_row.addWidget(self.class_b_checkbox)
        layout.addLayout(class_row)

    def eventFilter(self, obj, event) -> bool:
        # QDoubleSpinBox only accepts a single number, so pasting a
        # "lat, lon" pair copied straight from Google Maps into either
        # field would just get rejected/mangled. Intercept paste and, if
        # the clipboard holds a coordinate pair, fill both fields at once.
        if obj in (self.lat_spin, self.lon_spin) and event.type() == QEvent.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Paste):
                match = COORD_PASTE_RE.match(QApplication.clipboard().text())
                if match:
                    lat, lon = float(match.group(1)), float(match.group(2))
                    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                        self.set_coordinates(lat, lon)
                        return True
        return super().eventFilter(obj, event)

    def _on_slider_changed(self, value: int) -> None:
        self.radius_value_label.setText(f"{value} km")
        self.radius_changed.emit(float(value))

    def _on_set_clicked(self) -> None:
        lat, lon = self.lat_spin.value(), self.lon_spin.value()
        self.observer_set.emit(lat, lon)
        self.set_observer_location(f"{lat:.4f}, {lon:.4f}")

    def _on_filters_changed(self) -> None:
        self.filters_changed.emit(self.air_checkbox.isChecked(), self.sea_checkbox.isChecked())

    def _on_vessel_class_filter_changed(self) -> None:
        self.vessel_class_filter_changed.emit(
            self.class_a_checkbox.isChecked(), self.class_b_checkbox.isChecked()
        )

    def set_observer_location(self, name: str) -> None:
        self.location_label.setText(f"Observer: {name}")

    def set_coordinates(self, lat: float, lon: float) -> None:
        self.lat_spin.setValue(lat)
        self.lon_spin.setValue(lon)

    @property
    def radius_km(self) -> float:
        return float(self.radius_slider.value())
