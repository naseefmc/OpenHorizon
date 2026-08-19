"""Worldwide species search panel (Nearby tab).

Plots real OBIS sightings of a chosen marine-life group anywhere in the
world — independent of the observer location/radius that drives the rest
of Nearby Mode. Lives on Nearby (not the Ocean & Environment tab) since
it's a standalone "go find whales/sharks/dolphins" tool, not tied to a
clicked point the way the Ocean tab's local species query is.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

# Common-name presets mapped to real WoRMS/OBIS taxonomic groups (verified
# live against api.obis.org/v3/occurrence — each returns real records).
_SPECIES_PRESETS = [
    ("All species", None),
    ("Whales & dolphins", "Cetacea"),
    ("Sharks & rays", "Elasmobranchii"),
    ("Lobsters & crabs", "Decapoda"),
    ("Seabirds", "Aves"),
]


class SpeciesSearchPanel(QWidget):
    search_requested = Signal(str)  # taxon
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "surfaceElevated")
        self.setFixedWidth(260)

        layout = QVBoxLayout(self)
        header = QLabel("SPECIES SEARCH (WORLDWIDE)")
        header.setProperty("role", "sectionHeader")
        layout.addWidget(header)

        self._preset = QComboBox()
        for label, _ in _SPECIES_PRESETS:
            self._preset.addItem(label)
        self._preset.currentIndexChanged.connect(self._update_button_state)
        layout.addWidget(self._preset)

        self._custom = QLineEdit()
        self._custom.setPlaceholderText("Or type a scientific name…")
        self._custom.textChanged.connect(self._update_button_state)
        layout.addWidget(self._custom)

        row = QHBoxLayout()
        self._search_button = QPushButton("Search worldwide")
        self._search_button.clicked.connect(self._on_search_clicked)
        row.addWidget(self._search_button)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_requested)
        row.addWidget(clear_button)
        layout.addLayout(row)

        self._status = QLabel("")
        self._status.setProperty("role", "secondary")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._update_button_state()

    def taxon(self) -> str | None:
        custom = self._custom.text().strip()
        return custom or _SPECIES_PRESETS[self._preset.currentIndex()][1]

    def _update_button_state(self) -> None:
        taxon = self.taxon()
        self._search_button.setEnabled(taxon is not None)
        self._search_button.setToolTip(
            "Pick a specific group or type a scientific name first — worldwide search "
            "needs a taxon, not \"All species\" (too broad to plot)."
            if taxon is None
            else "Plot real OBIS sightings of this group from anywhere in the world (last 3 years)."
        )

    def _on_search_clicked(self) -> None:
        taxon = self.taxon()
        if taxon is not None:
            self.search_requested.emit(taxon)

    def set_status(self, text: str) -> None:
        self._status.setText(text)
