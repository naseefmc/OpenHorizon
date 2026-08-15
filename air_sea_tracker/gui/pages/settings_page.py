"""Settings (SDR §27, GUI §27) — categories, not one giant form."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.credentials import (
    AISHUB_USERNAME,
    AISSTREAM_API_KEY,
    BARENTSWATCH_CLIENT_ID,
    BARENTSWATCH_CLIENT_SECRET,
    VESSELAPI_API_KEY,
    get_credential,
    set_credential,
)
from config.settings import Settings
from gui.theme.theme_manager import ThemeManager

CATEGORIES = [
    "General", "Appearance", "Tracking", "Data Sources",
    "Cache & Storage", "Map", "Units", "Alerts", "Privacy", "Advanced",
]


class SettingsPage(QWidget):
    # Emitted after the AISStream key changes so the caller can restart
    # the AIS collector against the current observer (SDR §27.6).
    ais_credential_changed = Signal()

    def __init__(self, settings: Settings, theme_manager: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._theme_manager = theme_manager

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("SETTINGS"))

        # TODO(Phase 1): sidebar of CATEGORIES; this scaffold wires Appearance + Data Sources only.
        appearance_form = QFormLayout()
        theme_combo = QComboBox()
        theme_combo.addItems(["System", "Light", "Dark"])
        theme_combo.setCurrentText(settings.theme.capitalize())
        theme_combo.currentTextChanged.connect(self._on_theme_changed)
        appearance_form.addRow("Theme", theme_combo)
        layout.addLayout(appearance_form)

        separator = QFrame()
        separator.setProperty("role", "separator")
        separator.setFrameShape(QFrame.HLine)
        layout.addWidget(separator)

        layout.addWidget(QLabel("DATA SOURCES"))
        sources_form = QFormLayout()

        self.aisstream_key_input = self._add_credential_row(
            sources_form, "AISStream", AISSTREAM_API_KEY, "AISStream API key",
            "Not configured — free at aisstream.io",
        )
        self.barentswatch_id_input = self._add_credential_row(
            sources_form, "BarentsWatch client ID", BARENTSWATCH_CLIENT_ID, "Client ID",
            "Not configured — free registration at developer.barentswatch.no (Norway coverage only)",
            echo_password=False,
        )
        self.barentswatch_secret_input = self._add_credential_row(
            sources_form, "BarentsWatch secret", BARENTSWATCH_CLIENT_SECRET, "Client secret", None,
        )
        self.aishub_username_input = self._add_credential_row(
            sources_form, "AISHub username", AISHUB_USERNAME, "AISHub member username",
            "Not configured — requires contributing an AIS feed to AISHub",
            echo_password=False,
        )
        self.vesselapi_key_input = self._add_credential_row(
            sources_form, "VesselAPI", VESSELAPI_API_KEY, "VesselAPI API key",
            "Not configured — dashboard.vesselapi.com (150 calls/month on the free tier)",
        )

        opensky_note = QLabel("OpenSky (ADS-B) — anonymous free tier, no key required")
        opensky_note.setProperty("role", "secondary")
        sources_form.addRow("OpenSky", opensky_note)

        layout.addLayout(sources_form)
        layout.addStretch()

    def _add_credential_row(
        self,
        form: QFormLayout,
        label: str,
        credential_name: str,
        placeholder: str,
        empty_status: str | None,
        echo_password: bool = True,
    ) -> QLineEdit:
        """Adds a labeled secret input + Save button + status label, all wired
        to `config.credentials` (OS keychain, never QSettings — SDR §27.1)."""
        field = QLineEdit()
        if echo_password:
            field.setEchoMode(QLineEdit.Password)
        field.setPlaceholderText(placeholder)
        existing = get_credential(credential_name)
        if existing:
            field.setText(existing)
        save_btn = QPushButton("Save")
        form.addRow(label, field)
        form.addRow("", save_btn)

        status_label = QLabel("Configured" if existing else (empty_status or ""))
        status_label.setProperty("role", "secondary")
        if empty_status is not None:
            form.addRow("", status_label)

        def on_save() -> None:
            value = field.text().strip()
            if not value:
                return
            set_credential(credential_name, value)
            status_label.setText("Configured")
            self.ais_credential_changed.emit()

        save_btn.clicked.connect(on_save)
        return field

    def _on_theme_changed(self, text: str) -> None:
        mode = text.lower()
        self._settings.theme = mode
        self._theme_manager.set_mode(mode)
