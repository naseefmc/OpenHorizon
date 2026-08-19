"""Ocean Controller — orchestrates provider calls for a selected location
or vessel and assembles a unified OceanData (Ocean & Environment SDR §5, §8, §15).

    GUI -> OceanController -> Provider abstraction -> GEBCO/NOAA/OSM/... (SDR §8)

Every provider call is awaited via asyncio.gather(..., return_exceptions=True)
so one dead external service never prevents the rest of the sidebar
from populating (SDR §18). Results are cached spatially (SDR §17,
ocean/cache/ocean_cache.py) with per-data-kind TTLs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from ocean.cache.ocean_cache import (
    BATHYMETRY_TTL_SECONDS,
    COASTLINE_TTL_SECONDS,
    FISHING_ACTIVITY_TTL_SECONDS,
    MPA_TTL_SECONDS,
    SALINITY_TTL_SECONDS,
    SEA_LEVEL_TTL_SECONDS,
    SPECIES_TTL_SECONDS,
    SST_TTL_SECONDS,
    WATER_BODY_TTL_SECONDS,
    WAVES_TTL_SECONDS,
    WIND_TTL_SECONDS,
    OceanCache,
)
from ocean.models.ocean_data import OceanData
from ocean.models.ocean_location import SelectedLocation
from ocean.providers.base import OceanProvider
from ocean.providers.fishing_activity import FishingActivityProvider
from ocean.providers.gebco import GebcoProvider
from ocean.providers.marine_protected_areas import MarineProtectedAreaProvider
from ocean.providers.noaa_sst import NoaaSstProvider
from ocean.providers.obis import ObisProvider
from ocean.providers.open_meteo_marine import OpenMeteoMarineProvider
from ocean.providers.open_meteo_weather import OpenMeteoWeatherProvider
from ocean.providers.osm_water import CoastlineProvider, WaterBodyProvider
from ocean.providers.salinity import SalinityProvider
from ocean.providers.sea_level import SeaLevelProvider

logger = logging.getLogger(__name__)


def _hour_bucket(when: datetime | None) -> str:
    dt = when or datetime.now(timezone.utc)
    return dt.strftime("%Y%m%dT%H")


def _apply_fields(data: OceanData, merged: dict) -> None:
    # Every provider returns field_name -> value using OceanData's own
    # attribute names, so this is a direct pass-through rather than a
    # per-field mapping table.
    for key, value in merged.items():
        if hasattr(data, key):
            setattr(data, key, value)


class OceanController:
    def __init__(self) -> None:
        self.cache = OceanCache()
        self._gebco = GebcoProvider()
        self._noaa_sst = NoaaSstProvider()
        self._water_body = WaterBodyProvider()
        self._coastline = CoastlineProvider()
        self._open_meteo_marine = OpenMeteoMarineProvider()
        self._open_meteo_weather = OpenMeteoWeatherProvider()
        self._obis = ObisProvider()
        self._salinity = SalinityProvider()
        self._sea_level = SeaLevelProvider()
        self._fishing_activity = FishingActivityProvider()
        self._mpa = MarineProtectedAreaProvider()

    async def _fetch_kind(
        self,
        kind: str,
        provider: OceanProvider,
        lat: float,
        lon: float,
        when: datetime | None,
        ttl_seconds: float,
        cache_extra: str = "",
        **provider_kwargs,
    ) -> dict:
        key = self.cache.spatial_key(kind, lat, lon, cache_extra)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        try:
            result = await provider.get_point_data(lat, lon, when, **provider_kwargs)
        except Exception:
            logger.exception("Provider %s failed for %s", provider.name, kind)
            result = {}
        self.cache.put(key, result, ttl_seconds)
        return result

    async def query_location(
        self,
        location: SelectedLocation,
        *,
        enabled_layers: frozenset[str] = frozenset(),
        when: datetime | None = None,
        species_filter: str | None = None,
    ) -> OceanData:
        lat, lon = location.latitude, location.longitude
        data = OceanData(latitude=lat, longitude=lon)

        # Phase 1 fields are the tab's baseline, not toggleable "extras"
        # like the Phase 2 dynamic layers — always queried on click.
        tasks: dict[str, asyncio.Future] = {
            "depth": self._fetch_kind("depth", self._gebco, lat, lon, when, BATHYMETRY_TTL_SECONDS),
            "sst": self._fetch_kind("sst", self._noaa_sst, lat, lon, when, SST_TTL_SECONDS),
            "water_body": self._fetch_kind("water_body", self._water_body, lat, lon, when, WATER_BODY_TTL_SECONDS),
            "coast": self._fetch_kind("coast", self._coastline, lat, lon, when, COASTLINE_TTL_SECONDS),
        }

        hour_bucket = _hour_bucket(when)
        if enabled_layers & {"waves", "currents"}:
            tasks["marine"] = self._fetch_kind(
                "marine", self._open_meteo_marine, lat, lon, when, WAVES_TTL_SECONDS, hour_bucket
            )
        if enabled_layers & {"wind", "rain", "clouds"}:
            tasks["weather"] = self._fetch_kind(
                "weather", self._open_meteo_weather, lat, lon, when, WIND_TTL_SECONDS, hour_bucket
            )
        if "salinity" in enabled_layers:
            tasks["salinity"] = self._fetch_kind("salinity", self._salinity, lat, lon, when, SALINITY_TTL_SECONDS)
        if "sea_level" in enabled_layers:
            tasks["sea_level"] = self._fetch_kind("sea_level", self._sea_level, lat, lon, when, SEA_LEVEL_TTL_SECONDS)
        if "fishing_activity" in enabled_layers:
            tasks["fishing_activity"] = self._fetch_kind(
                "fishing_activity", self._fishing_activity, lat, lon, when, FISHING_ACTIVITY_TTL_SECONDS
            )
        if "marine_protected_areas" in enabled_layers:
            tasks["mpa"] = self._fetch_kind("mpa", self._mpa, lat, lon, when, MPA_TTL_SECONDS)
        if "marine_life" in enabled_layers:
            tasks["species"] = self._fetch_kind(
                "species",
                self._obis,
                lat,
                lon,
                when,
                SPECIES_TTL_SECONDS,
                cache_extra=species_filter or "",
                taxon_filter=species_filter,
            )

        kinds = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        merged: dict = {}
        for kind, result in zip(kinds, results):
            if isinstance(result, BaseException):
                logger.error("Ocean provider job %s raised", kind, exc_info=result)
                continue
            merged.update(result)

        _apply_fields(data, merged)
        return data
