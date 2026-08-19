"""Depth-contour line overlay (Ocean & Environment SDR §4, §6).

EMODnet Bathymetry's public WMS (`emodnet:contours`) supplies real vector
depth-contour lines (50/100/200/500/1000/2000/5000 m bands) — free,
keyless, verified live. This was previously marked unavailable because
GEBCO's own WMS only offers colour-shaded rasters, not contour lines;
EMODnet is a genuinely different (European bathymetry compilation)
source that does. Point depth itself is still GebcoProvider's job —
this class only supplies the line overlay.
"""

from __future__ import annotations

from datetime import datetime

from ocean.providers.base import OceanProvider, TileLayerSpec

WMS_URL = "https://ows.emodnet-bathymetry.eu/wms"
LAYER = "emodnet:contours"


class DepthContourProvider(OceanProvider):
    name = "EMODnet Bathymetry"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict:
        return {}

    def get_layer(self) -> TileLayerSpec:
        return TileLayerSpec(
            kind="wms",
            url=WMS_URL,
            layers=LAYER,
            extra_params={"TRANSPARENT": "TRUE"},
            attribution="EMODnet Bathymetry",
            opacity=0.9,
        )
