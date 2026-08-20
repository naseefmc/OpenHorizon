"""Layer Controls panel (Ocean & Environment SDR §4, §11).

Built directly off ocean/layers/layer_registry.py's LayerDef list, so a
new layer only needs adding there — this panel renders whatever it's
given, grouped by LayerDef.group. Layers with no working provider
(unavailable_reason set) render disabled with a tooltip explaining why,
rather than being hidden — SDR §18/§19's "explicit unavailable" applies
to the controls themselves, not just query results.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from ocean.layers.layer_registry import LayerDef

# Map-colour legends for layers whose WMS tiles use a continuous colour
# ramp with no built-in key — NOAA ERDDAP's WMS doesn't support
# GetLegendGraphic (verified live: returns a ServiceException), so this
# is a static approximation of its default "Rainbow" palette against
# each dataset's own colorBarMinimum/colorBarMaximum (from the
# datasets' .das metadata), not a fetched legend image.
_LEGENDS: dict[str, tuple[str, str]] = {
    "salinity": ("32 PSU (fresher)", "37 PSU (saltier)"),
    "sea_level": ("-200 cm (low)", "+200 cm (high)"),
}
_LEGEND_GRADIENT = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:0,"
    " stop:0 #3a4cc0, stop:0.25 #1fb8c4, stop:0.5 #2ecc71,"
    " stop:0.75 #f2d13a, stop:1 #e0392b)"
)

# Common-name presets mapped to real WoRMS/OBIS taxonomic groups (verified
# live against api.obis.org/v3/occurrence — each returns real records).
# "Whales & dolphins" is one entry because OBIS has no clean single term
# that means "whale but not dolphin"; the sidebar's own classifier still
# labels each result distinctly once results come back.
_SPECIES_PRESETS = [
    ("All species", None),
    ("Whales & dolphins", "Cetacea"),
    ("Sharks & rays", "Elasmobranchii"),
    ("Lobsters & crabs", "Decapoda"),
    ("Seabirds", "Aves"),
]


class OceanLayersPanel(QWidget):
    layer_toggled = Signal(str, bool)  # layer_id, enabled
    species_filter_changed = Signal(object)  # str | None

    def __init__(self, layer_defs: list[LayerDef], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "surfaceElevated")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        self._checkboxes: dict[str, QCheckBox] = {}

        groups: dict[str, list[LayerDef]] = {}
        for layer_def in layer_defs:
            groups.setdefault(layer_def.group, []).append(layer_def)

        for group_name, defs in groups.items():
            header = QLabel(group_name)
            header.setProperty("role", "sectionHeader")
            layout.addWidget(header)
            for layer_def in defs:
                checkbox = QCheckBox(layer_def.label)
                if layer_def.available:
                    checkbox.setChecked(layer_def.default_on)
                else:
                    checkbox.setChecked(False)
                    checkbox.setEnabled(False)
                    checkbox.setToolTip(layer_def.unavailable_reason or "Not available")
                checkbox.toggled.connect(
                    lambda checked, layer_id=layer_def.layer_id: self.layer_toggled.emit(layer_id, checked)
                )
                self._checkboxes[layer_def.layer_id] = checkbox
                layout.addWidget(checkbox)
                if layer_def.layer_id == "marine_life":
                    layout.addWidget(self._build_species_filter())
                if layer_def.layer_id in _LEGENDS:
                    min_text, max_text = _LEGENDS[layer_def.layer_id]
                    layout.addWidget(self._build_legend(min_text, max_text))

        layout.addStretch()

    @staticmethod
    def _build_legend(min_text: str, max_text: str) -> QWidget:
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(16, 0, 4, 4)
        box_layout.setSpacing(2)

        bar = QLabel()
        bar.setFixedHeight(8)
        bar.setStyleSheet(f"background: {_LEGEND_GRADIENT}; border-radius: 2px;")
        box_layout.addWidget(bar)

        labels_row = QHBoxLayout()
        labels_row.setContentsMargins(0, 0, 0, 0)
        min_label = QLabel(min_text)
        min_label.setProperty("role", "secondary")
        max_label = QLabel(max_text)
        max_label.setProperty("role", "secondary")
        max_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        labels_row.addWidget(min_label)
        labels_row.addWidget(max_label)
        box_layout.addLayout(labels_row)

        return box

    def _build_species_filter(self) -> QWidget:
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(16, 0, 0, 4)
        box_layout.setSpacing(2)

        self._species_preset = QComboBox()
        for label, _ in _SPECIES_PRESETS:
            self._species_preset.addItem(label)
        self._species_preset.currentIndexChanged.connect(self._on_species_filter_changed)
        box_layout.addWidget(self._species_preset)

        self._species_custom = QLineEdit()
        self._species_custom.setPlaceholderText("Or type a scientific name…")
        self._species_custom.editingFinished.connect(self._on_species_filter_changed)
        box_layout.addWidget(self._species_custom)

        return box

    def _on_species_filter_changed(self) -> None:
        custom = self._species_custom.text().strip()
        taxon = custom or _SPECIES_PRESETS[self._species_preset.currentIndex()][1]
        self.species_filter_changed.emit(taxon)

    def species_filter(self) -> str | None:
        custom = self._species_custom.text().strip()
        return custom or _SPECIES_PRESETS[self._species_preset.currentIndex()][1]

    def refresh_availability(self, layer_defs: list[LayerDef]) -> None:
        """Re-checks each layer's availability (e.g. a credential-gated
        provider like Global Fishing Watch) and enables/disables its
        checkbox accordingly. `LayerDef.available` is a live check, not a
        snapshot, so this reflects credentials added since the panel was
        built without needing to reconstruct it."""
        for layer_def in layer_defs:
            checkbox = self._checkboxes.get(layer_def.layer_id)
            if checkbox is None:
                continue
            available = layer_def.available
            if checkbox.isEnabled() == available:
                continue
            checkbox.setEnabled(available)
            checkbox.setToolTip("" if available else (layer_def.unavailable_reason or "Not available"))

    def enabled_layer_ids(self) -> frozenset[str]:
        return frozenset(layer_id for layer_id, cb in self._checkboxes.items() if cb.isChecked())

    def is_enabled(self, layer_id: str) -> bool:
        checkbox = self._checkboxes.get(layer_id)
        return checkbox is not None and checkbox.isChecked()
