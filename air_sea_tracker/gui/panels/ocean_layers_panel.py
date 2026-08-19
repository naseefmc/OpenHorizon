"""Layer Controls panel (Ocean & Environment SDR §4, §11).

Built directly off ocean/layers/layer_registry.py's LayerDef list, so a
new layer only needs adding there — this panel renders whatever it's
given, grouped by LayerDef.group. Layers with no working provider
(unavailable_reason set) render disabled with a tooltip explaining why,
rather than being hidden — SDR §18/§19's "explicit unavailable" applies
to the controls themselves, not just query results.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit, QVBoxLayout, QWidget

from ocean.layers.layer_registry import LayerDef

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

        layout.addStretch()

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

    def enabled_layer_ids(self) -> frozenset[str]:
        return frozenset(layer_id for layer_id, cb in self._checkboxes.items() if cb.isChecked())

    def is_enabled(self, layer_id: str) -> bool:
        checkbox = self._checkboxes.get(layer_id)
        return checkbox is not None and checkbox.isChecked()
