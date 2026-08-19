"""Tropical storm/hurricane overlay (Ocean & Environment SDR §11).

NOAA's National Hurricane Center publishes a public ArcGIS MapServer
(mapservices.weather.noaa.gov) with a WMS interface — free, keyless,
verified live. Layer 0 ("Graphical Tropical Weather Outlook") is NHC's
own at-a-glance public summary graphic: current/developing tropical
systems and their formation-risk areas across all basins. The
alternative — combining the per-storm forecast-track/cone sub-layers
(IDs 4-29 for slot AT1, 30-55 for AT2, etc.) — would show exact tracks
but depends on NHC's internal slot numbering staying stable; layer 0 is
the documented, stable, always-present layer and degrades gracefully
(renders empty, not broken) when no storms are active.
"""

from __future__ import annotations

from datetime import datetime

from ocean.providers.base import OceanProvider, TileLayerSpec

WMS_URL = "https://mapservices.weather.noaa.gov/tropical/services/tropical/NHC_tropical_weather/MapServer/WMSServer"
LAYER = "0"


class StormsProvider(OceanProvider):
    name = "NOAA NHC"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict:
        return {}

    def get_layer(self) -> TileLayerSpec:
        return TileLayerSpec(
            kind="wms",
            url=WMS_URL,
            layers=LAYER,
            extra_params={"TRANSPARENT": "TRUE"},
            attribution="NOAA National Hurricane Center",
            opacity=0.85,
        )
