"""GEBCO global bathymetry provider (Ocean & Environment SDR §6).

Point depth comes from WMS GetFeatureInfo against GEBCO's public WMS,
querying the `GEBCO_LATEST_2` layer — the one queryable, colour-shaded
elevation layer in GEBCO's service (its sibling `GEBCO_LATEST` layer is
marked non-queryable in GetCapabilities).

GetFeatureInfo recipe note: this MapServer instance was found (by
direct testing against it) to silently return "no results" for
open-ocean points when WIDTH/HEIGHT/BBOX combinations don't align with
its internal raster tiling — even though the exact same area renders
fine via GetMap — while coastal points tolerated a wider range of
sizes. A fixed 256x256px query window sidesteps this reliably for both
coastal and open-ocean points and comfortably exceeds GEBCO's ~450m
native grid resolution.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import aiohttp

from ocean.models.ocean_data import STATUS_STATIC, SourcedValue
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider, TileLayerSpec

logger = logging.getLogger(__name__)

WMS_URL = "https://wms.gebco.net/mapserv?"
LAYER = "GEBCO_LATEST_2"
QUERY_BOX_DEGREES = 0.02
QUERY_SIZE_PX = 256

_VALUE_RE = re.compile(r"value_list\s*=\s*'([-\d.]+)'")


class GebcoProvider(OceanProvider):
    name = "GEBCO"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict[str, SourcedValue]:
        try:
            elevation = await self._query_elevation(lat, lon)
        except Exception:
            logger.exception("GEBCO point query failed")
            unavailable = SourcedValue.unavailable(self.name, "GEBCO service unreachable")
            return {"depth_m": unavailable, "seabed_elevation_m": unavailable}

        if elevation is None:
            unavailable = SourcedValue.unavailable(self.name, "No bathymetry data at this point")
            return {"depth_m": unavailable, "seabed_elevation_m": unavailable}

        depth = -elevation
        return {
            "depth_m": SourcedValue(
                value=round(depth, 1) if depth > 0 else None,
                unit="m",
                source=self.name,
                status=STATUS_STATIC,
                note=None if depth > 0 else "Point is above sea level (land)",
            ),
            "seabed_elevation_m": SourcedValue(value=round(elevation, 1), unit="m", source=self.name, status=STATUS_STATIC),
        }

    async def _query_elevation(self, lat: float, lon: float) -> float | None:
        half = QUERY_BOX_DEGREES / 2
        bbox = f"{lat - half},{lon - half},{lat + half},{lon + half}"
        center = QUERY_SIZE_PX // 2
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": LAYER,
            "QUERY_LAYERS": LAYER,
            "STYLES": "default",
            "CRS": "EPSG:4326",
            "BBOX": bbox,
            "WIDTH": str(QUERY_SIZE_PX),
            "HEIGHT": str(QUERY_SIZE_PX),
            "I": str(center),
            "J": str(center),
            "INFO_FORMAT": "text/plain",
            "FEATURE_COUNT": "1",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                WMS_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
        match = _VALUE_RE.search(text)
        return float(match.group(1)) if match else None

    def get_layer(self) -> TileLayerSpec:
        return TileLayerSpec(
            kind="wms",
            url=WMS_URL,
            layers=LAYER,
            extra_params={"STYLES": "default"},
            attribution="GEBCO Compilation Group",
            opacity=0.75,
        )
