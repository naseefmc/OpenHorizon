"""Secure API credential storage (SDR §27.1 — hard requirement).

API keys MUST NOT be stored via QSettings or any plaintext config
file. This module is the only place credentials are read/written, and
it always goes through the OS keychain via `keyring`.
"""

from __future__ import annotations

import keyring

_SERVICE = "AirSeaLiveTracker"

# Known credential slots (SDR §27.6)
AISSTREAM_API_KEY = "aisstream_api_key"
BARENTSWATCH_CLIENT_ID = "barentswatch_client_id"
BARENTSWATCH_CLIENT_SECRET = "barentswatch_client_secret"
AISHUB_USERNAME = "aishub_username"
VESSELAPI_API_KEY = "vesselapi_api_key"
OPENSKY_CLIENT_ID = "opensky_client_id"
OPENSKY_CLIENT_SECRET = "opensky_client_secret"
AIRPORT_PROVIDER_API_KEY = "airport_provider_api_key"
PORT_PROVIDER_API_KEY = "port_provider_api_key"
ENRICHMENT_PROVIDER_API_KEY = "enrichment_provider_api_key"


def get_credential(name: str) -> str | None:
    return keyring.get_password(_SERVICE, name)


def set_credential(name: str, value: str) -> None:
    keyring.set_password(_SERVICE, name, value)


def delete_credential(name: str) -> None:
    try:
        keyring.delete_password(_SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass
