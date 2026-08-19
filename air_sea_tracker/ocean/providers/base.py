"""Common provider abstraction for the Ocean & Environment tab (SDR §16).

Every provider must fail independently (SDR §18): `get_point_data()`
must never raise out to the controller — network/HTTP/parse errors are
caught inside the provider and turned into an unavailable SourcedValue,
so one dead external service can't take down the rest of the sidebar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp

USER_AGENT = "OpenHorizonOceanEnvironment/1.0 (https://github.com/naseefmc/OpenHorizon)"
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)


@dataclass
class TileLayerSpec:
    """Describes one togglable map overlay, handed to the JS map layer
    as-is (no python-side tile fetching/compositing — Leaflet does it)."""

    kind: str  # "wms" | "xyz"
    url: str
    layers: str | None = None  # WMS layer name(s)
    extra_params: dict = field(default_factory=dict)
    attribution: str = ""
    opacity: float = 0.7


class OceanProvider(ABC):
    name: str = "provider"

    @abstractmethod
    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict:
        """Returns field_name -> SourcedValue (or a richer dataclass for
        composite fields like waves/wind/current). Must not raise."""
        raise NotImplementedError

    def get_layer(self) -> TileLayerSpec | None:
        return None

    def is_available(self) -> bool:
        return True
