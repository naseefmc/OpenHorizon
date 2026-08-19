"""Spatial TTL cache for ocean/environment provider results (Ocean & Environment SDR §17).

Keys combine a data-kind tag with coordinates rounded to 3 decimal
places (~110m at the equator) so repeated clicks within roughly the
same spot reuse cached data instead of re-hitting external providers.
Same shape as services/cache_service.LiveTargetCache, but keyed
spatially rather than by target id, per SDR §17's suggested key.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

# Suggested cache lifetimes (SDR §17 table), in seconds.
BATHYMETRY_TTL_SECONDS = 30 * 24 * 3600  # "days/months"
COASTLINE_TTL_SECONDS = 7 * 24 * 3600
WATER_BODY_TTL_SECONDS = 7 * 24 * 3600  # static-ish gazetteer lookup, same bucket as coastline
SST_TTL_SECONDS = 3 * 3600  # "1-6 hours"
WAVES_TTL_SECONDS = 2 * 3600  # "1-3 hours"
CURRENTS_TTL_SECONDS = 2 * 3600
WIND_TTL_SECONDS = 45 * 60  # "30-60 minutes"
RAIN_CLOUDS_TTL_SECONDS = 45 * 60
SPECIES_TTL_SECONDS = 24 * 3600
SALINITY_TTL_SECONDS = 3 * 3600  # SMOS is a daily composite, same bucket as SST
SEA_LEVEL_TTL_SECONDS = 3 * 3600  # altimetry is also ~daily
FISHING_ACTIVITY_TTL_SECONDS = 6 * 3600  # GFW's own pipeline is already days-delayed
MPA_TTL_SECONDS = 30 * 24 * 3600  # WDPA is updated monthly


@dataclass
class _Entry:
    value: Any
    expires_at: float


class OceanCache:
    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    @staticmethod
    def spatial_key(kind: str, lat: float, lon: float, extra: str = "") -> str:
        return f"{kind}:{round(lat, 3)}:{round(lon, 3)}:{extra}"

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._entries[key]
            return None
        return entry.value

    def put(self, key: str, value: Any, ttl_seconds: float) -> None:
        self._entries[key] = _Entry(value=value, expires_at=time.time() + ttl_seconds)

    def purge_expired(self) -> int:
        now = time.time()
        expired = [k for k, e in self._entries.items() if now > e.expires_at]
        for k in expired:
            del self._entries[k]
        return len(expired)

    def __len__(self) -> int:
        return len(self._entries)
