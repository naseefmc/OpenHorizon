"""Sea level anomaly provider (Ocean & Environment SDR §11).

Same "Copernicus-substitution" rationale as salinity.py: NOAA CoastWatch's
public ERDDAP hosts an altimetry-derived sea-surface-height-anomaly
product (`nesdisSSH1day`, RADS-based) — free, keyless, same pattern as
noaa_sst.py.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime

import aiohttp

from ocean.models.ocean_data import STATUS_NEAR_REAL_TIME, SourcedValue
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider, TileLayerSpec

logger = logging.getLogger(__name__)

GRIDDAP_URL = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/nesdisSSH1day.csv"
WMS_URL = "https://coastwatch.pfeg.noaa.gov/erddap/wms/nesdisSSH1day/request"
LAYER = "nesdisSSH1day:sla"


class SeaLevelProvider(OceanProvider):
    name = "NOAA / RADS Altimetry"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict[str, SourcedValue]:
        url = f"{GRIDDAP_URL}?sla[(last)][({lat})][({lon})]"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT) as resp:
                    resp.raise_for_status()
                    text = await resp.text()
        except Exception:
            logger.exception("Sea level anomaly point query failed")
            return {"sea_level_anomaly_cm": SourcedValue.unavailable(self.name, "Altimetry service unreachable")}

        lines = [line for line in text.strip().splitlines() if line]
        if len(lines) < 3:
            return {"sea_level_anomaly_cm": SourcedValue.unavailable(self.name, "No sea level data at this point")}

        try:
            timestamp, _lat, _lon, sla_raw = lines[2].split(",")
            sla_m = float(sla_raw)
        except (ValueError, IndexError):
            return {
                "sea_level_anomaly_cm": SourcedValue.unavailable(self.name, "No sea level data at this point (likely land)")
            }

        if math.isnan(sla_m):
            return {
                "sea_level_anomaly_cm": SourcedValue.unavailable(
                    self.name, "No reliable altimetry reading this close to the coast"
                )
            }

        return {
            "sea_level_anomaly_cm": SourcedValue(
                value=round(sla_m * 100, 1), unit="cm", source=self.name, status=STATUS_NEAR_REAL_TIME, timestamp=timestamp
            )
        }

    def get_layer(self) -> TileLayerSpec:
        return TileLayerSpec(
            kind="wms",
            url=WMS_URL,
            layers=LAYER,
            extra_params={"TRANSPARENT": "TRUE"},
            attribution="NOAA CoastWatch / RADS Altimetry",
            opacity=0.65,
        )
