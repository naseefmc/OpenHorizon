"""Environmental time slider (Ocean & Environment SDR §14).

Drives the Phase 2 layers backed by hourly forecast data (SST, wind,
waves, currents, rain, clouds via Open-Meteo); layers without hourly
resolution (bathymetry, coastline, the Copernicus-shaped stubs) simply
ignore the `when` value the controller passes them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

PAST_HOURS = 24
FUTURE_HOURS = 48


class TimeControl(QWidget):
    time_changed = Signal(object)  # datetime | None ("None" == now)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        tooltip = (
            "Drag to view sea temperature, wind, waves, rain, and clouds at a "
            "different time (24h in the past to 48h in the future, from hourly "
            "forecast/historical data). Doesn't affect bathymetry, coastline, "
            "or other layers that don't change hour to hour."
        )
        self.setToolTip(tooltip)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        caption = QLabel("Time — scrub to see forecast/historical conditions for the time-varying layers")
        caption.setProperty("role", "secondary")
        caption.setToolTip(tooltip)
        layout.addWidget(caption)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"−{PAST_HOURS}h"))
        header.addStretch()
        self.time_label = QLabel("Now")
        self.time_label.setProperty("role", "secondary")
        header.addWidget(self.time_label)
        header.addStretch()
        header.addWidget(QLabel(f"+{FUTURE_HOURS}h"))
        layout.addLayout(header)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(-PAST_HOURS, FUTURE_HOURS)
        self.slider.setValue(0)
        self.slider.setToolTip(tooltip)
        self.slider.valueChanged.connect(self._on_changed)
        layout.addWidget(self.slider)

    def _on_changed(self, hours: int) -> None:
        if hours == 0:
            self.time_label.setText("Now")
            self.time_changed.emit(None)
            return
        when = datetime.now(timezone.utc) + timedelta(hours=hours)
        sign = "+" if hours > 0 else ""
        self.time_label.setText(f"{when.strftime('%d %b %H:%M UTC')} ({sign}{hours}h)")
        self.time_changed.emit(when)

    def reset_to_now(self) -> None:
        self.slider.setValue(0)

    @property
    def current_when(self) -> datetime | None:
        hours = self.slider.value()
        if hours == 0:
            return None
        return datetime.now(timezone.utc) + timedelta(hours=hours)
