"""NOAA sea-surface-temperature provider (Ocean & Environment SDR §7).

Point value comes from NOAA CoastWatch's public ERDDAP, dataset
`jplMURSST41` (JPL MUR L4 daily global SST analysis) via a plain
griddap point query — no auth, no key. The same dataset's ERDDAP-hosted
WMS supplies the map overlay.
"""

from __future__ import annotations

import logging
from datetime import datetime

import aiohttp

from ocean.models.ocean_data import STATUS_NEAR_REAL_TIME, SourcedValue
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider, TileLayerSpec

logger = logging.getLogger(__name__)

GRIDDAP_URL = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.csv"
WMS_URL = "https://coastwatch.pfeg.noaa.gov/erddap/wms/jplMURSST41/request"
LAYER = "jplMURSST41:analysed_sst"


class NoaaSstProvider(OceanProvider):
    name = "NOAA"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict[str, SourcedValue]:
        # jplMURSST41 is a daily analysis, not truly sub-daily, so a
        # requested `when` still resolves to "the day's analysis" —
        # ERDDAP's `(last)` selector already gets us that.
        url = f"{GRIDDAP_URL}?analysed_sst[(last)][({lat})][({lon})]"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT) as resp:
                    resp.raise_for_status()
                    text = await resp.text()
        except Exception:
            logger.exception("NOAA SST point query failed")
            return {"sea_surface_temperature_c": SourcedValue.unavailable(self.name, "NOAA SST service unreachable")}

        lines = [line for line in text.strip().splitlines() if line]
        if len(lines) < 3:
            return {"sea_surface_temperature_c": SourcedValue.unavailable(self.name, "No SST data at this point")}

        try:
            timestamp, _lat, _lon, sst_raw = lines[2].split(",")
            sst_val = float(sst_raw)
        except (ValueError, IndexError):
            return {
                "sea_surface_temperature_c": SourcedValue.unavailable(
                    self.name, "No SST data at this point (likely land)"
                )
            }

        return {
            "sea_surface_temperature_c": SourcedValue(
                value=round(sst_val, 1),
                unit="°C",
                source=self.name,
                status=STATUS_NEAR_REAL_TIME,
                timestamp=timestamp,
            )
        }

    def get_layer(self) -> TileLayerSpec:
        return TileLayerSpec(
            kind="wms",
            url=WMS_URL,
            layers=LAYER,
            extra_params={"TRANSPARENT": "TRUE"},
            attribution="NOAA CoastWatch / JPL MUR SST",
            opacity=0.65,
        )
