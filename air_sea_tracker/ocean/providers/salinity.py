"""Sea surface salinity provider (Ocean & Environment SDR §11).

Same "Copernicus-substitution" rationale as open_meteo_marine.py/
open_meteo_weather.py: rather than leave this unavailable pending a
Copernicus Marine account, NOAA CoastWatch's public ERDDAP hosts SMOS
satellite sea-surface-salinity as a free, keyless near-real-time daily
product — same host/pattern as noaa_sst.py's SST provider, just with an
extra `altitude` axis (fixed at the surface, 0.0) that SST's dataset
doesn't have.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime

import aiohttp

from ocean.models.ocean_data import STATUS_NEAR_REAL_TIME, SourcedValue
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider, TileLayerSpec

logger = logging.getLogger(__name__)

GRIDDAP_URL = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/coastwatchSMOSv662SSS1day.csv"
WMS_URL = "https://coastwatch.pfeg.noaa.gov/erddap/wms/coastwatchSMOSv662SSS1day/request"
LAYER = "coastwatchSMOSv662SSS1day:sss"


class SalinityProvider(OceanProvider):
    name = "NOAA / SMOS"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict[str, SourcedValue]:
        url = f"{GRIDDAP_URL}?sss[(last)][(0.0)][({lat})][({lon})]"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT) as resp:
                    resp.raise_for_status()
                    text = await resp.text()
        except Exception:
            logger.exception("Salinity point query failed")
            return {"salinity": SourcedValue.unavailable(self.name, "SMOS salinity service unreachable")}

        lines = [line for line in text.strip().splitlines() if line]
        if len(lines) < 3:
            return {"salinity": SourcedValue.unavailable(self.name, "No salinity data at this point")}

        try:
            timestamp, _lat, _lon, _alt, sss_raw = lines[2].split(",")
            sss_val = float(sss_raw)
        except (ValueError, IndexError):
            return {"salinity": SourcedValue.unavailable(self.name, "No salinity data at this point (likely land)")}

        if math.isnan(sss_val):
            # SMOS' passive-microwave retrieval is unreliable within ~50km of
            # a coastline (land contamination in the sensor footprint) — the
            # grid cell exists but is masked, not a service failure.
            return {
                "salinity": SourcedValue.unavailable(
                    self.name, "No reliable satellite salinity reading this close to the coast"
                )
            }

        return {
            "salinity": SourcedValue(
                value=round(sss_val, 1), unit="PSU", source=self.name, status=STATUS_NEAR_REAL_TIME, timestamp=timestamp
            )
        }

    def get_layer(self) -> TileLayerSpec:
        return TileLayerSpec(
            kind="wms",
            url=WMS_URL,
            layers=LAYER,
            extra_params={"TRANSPARENT": "TRUE"},
            attribution="NOAA CoastWatch / SMOS",
            opacity=0.65,
        )
