"""Geography provider: water-body naming, nearest-coast distance, and
the Coastline/Rivers/Lakes map overlays (Ocean & Environment SDR §4, §5).

Two free, keyless data sources cover what the SDR's single
"OpenStreetMap" line item asks for:

  - Water-body naming ("Adriatic Sea") comes from marineregions.org's
    gazetteer, which geocodes a point against named seas/oceans/marine
    regions — OSM itself has no equivalent global "what sea is this"
    lookup, so this one field intentionally isn't OSM-sourced.
  - Nearest-coast distance is computed from real OpenStreetMap
    coastline geometry (`natural=coastline` ways), fetched via the
    public Overpass API — this matches the SDR's named source.
  - The Coastline/Rivers/Lakes map overlays reuse the boundary layers
    NOAA's ERDDAP already serves from the same WMS endpoint as the SST
    layer (Coastlines / LakesAndRivers), since there's no free hosted
    OSM vector-tile boundary WMS to point Leaflet at directly. Rivers
    and Lakes share ERDDAP's one combined "LakesAndRivers" layer — it
    isn't split further — so both Layer Controls checkboxes (SDR §4)
    toggle the same overlay.
"""

from __future__ import annotations

import logging
import socket
import time
from datetime import datetime

import aiohttp

from ocean.models.ocean_data import STATUS_STATIC, SourcedValue
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider, TileLayerSpec
from utils.distance import haversine_km

logger = logging.getLogger(__name__)

MARINEREGIONS_URL = "https://www.marineregions.org/rest/getGazetteerRecordsByLatLong.json/{lat}/{lon}/"
# The public Overpass API is a small set of independently-run mirrors that
# routinely go down or rate-limit individually — falling through the list
# on failure is the normal way to use it, not a special-case workaround.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]
ERDDAP_WMS_URL = "https://coastwatch.pfeg.noaa.gov/erddap/wms/jplMURSST41/request"

# Most-specific-first: prefer a named sea over a whole ocean/basin.
_SEA_PLACE_TYPE_PRIORITY = [
    "IHO Sea Area",
    "Sea",
    "Ocean",
    "Large Marine Ecosystem",
    "General Sea Area",
    "FAO Subareas",
]

_COAST_SEARCH_RADII_KM = [20, 100, 300]

# Circuit breaker: when every Overpass mirror fails (common when the public
# API is blocked at the network level — a corporate/security-tool firewall,
# not something retrying fixes), stop burning ~30s and a full traceback on
# every single map click and just report "unavailable" until the cooldown
# passes. Module-level (not per-instance) so it's shared across every
# CoastlineProvider the app creates.
_OVERPASS_COOLDOWN_SECONDS = 10 * 60
_overpass_dead_until = 0.0


def _ipv4_connector() -> aiohttp.TCPConnector:
    # macOS + Python 3.12's asyncio hits `OSError: [Errno 22] Invalid
    # argument` from _set_nodelay() when happy-eyeballs races an IPv6
    # candidate on a network where that route is dead (overpass-api.de
    # and marineregions.org both resolve to IPv6 addresses). Forcing
    # IPv4-only sidesteps the broken code path entirely.
    return aiohttp.TCPConnector(family=socket.AF_INET)


class WaterBodyProvider(OceanProvider):
    name = "Marine Regions"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict[str, SourcedValue]:
        try:
            name = await self._lookup(lat, lon)
        except Exception:
            logger.exception("Marine Regions lookup failed")
            return {"water_body": SourcedValue.unavailable(self.name, "Marine Regions service unreachable")}
        if not name:
            return {"water_body": SourcedValue.unavailable(self.name, "No named water body found")}
        return {"water_body": SourcedValue(value=name, source=self.name, status=STATUS_STATIC)}

    async def _lookup(self, lat: float, lon: float) -> str | None:
        url = MARINEREGIONS_URL.format(lat=lat, lon=lon)
        async with aiohttp.ClientSession(connector=_ipv4_connector()) as session:
            async with session.get(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT) as resp:
                resp.raise_for_status()
                records = await resp.json(content_type=None)

        by_type: dict[str, str] = {}
        for rec in records:
            place_type = rec.get("placeType")
            if place_type and place_type not in by_type:
                by_type[place_type] = rec.get("preferredGazetteerName", "").strip()

        for place_type in _SEA_PLACE_TYPE_PRIORITY:
            if by_type.get(place_type):
                return by_type[place_type]
        return None


class CoastlineProvider(OceanProvider):
    name = "OpenStreetMap"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict[str, SourcedValue]:
        global _overpass_dead_until
        now = time.time()
        if now < _overpass_dead_until:
            remaining_min = int((_overpass_dead_until - now) // 60) + 1
            return {
                "nearest_coast_distance_km": SourcedValue.unavailable(
                    self.name,
                    f"OpenStreetMap Overpass unreachable from this network — not retrying for {remaining_min} more min",
                )
            }
        try:
            distance_km = await self._nearest_coast_km(lat, lon)
        except Exception:
            _overpass_dead_until = time.time() + _OVERPASS_COOLDOWN_SECONDS
            logger.exception(
                "Overpass coastline query failed on every mirror; pausing retries for %d minutes",
                _OVERPASS_COOLDOWN_SECONDS // 60,
            )
            return {
                "nearest_coast_distance_km": SourcedValue.unavailable(
                    self.name, "OpenStreetMap Overpass service unreachable"
                )
            }
        if distance_km is None:
            return {"nearest_coast_distance_km": SourcedValue.unavailable(self.name, "No coastline found nearby")}
        return {
            "nearest_coast_distance_km": SourcedValue(
                value=round(distance_km, 1), unit="km", source=self.name, status=STATUS_STATIC
            )
        }

    async def _nearest_coast_km(self, lat: float, lon: float) -> float | None:
        async with aiohttp.ClientSession(connector=_ipv4_connector()) as session:
            last_exc: Exception | None = None
            for url in OVERPASS_URLS:
                try:
                    for radius_km in _COAST_SEARCH_RADII_KM:
                        query = (
                            "[out:json][timeout:8];"
                            f'way(around:{int(radius_km * 1000)},{lat},{lon})["natural"="coastline"];'
                            "out geom 200;"
                        )
                        async with session.post(
                            url,
                            data={"data": query},
                            headers={"User-Agent": USER_AGENT},
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as resp:
                            resp.raise_for_status()
                            payload = await resp.json()

                        nearest: float | None = None
                        for element in payload.get("elements", []):
                            for point in element.get("geometry", []):
                                d = haversine_km(lat, lon, point["lat"], point["lon"])
                                if nearest is None or d < nearest:
                                    nearest = d
                        if nearest is not None:
                            return nearest
                    # This mirror answered at every radius and genuinely found
                    # nothing — trust it rather than hammering the next mirror.
                    return None
                except Exception as exc:
                    last_exc = exc
                    logger.warning("Overpass mirror %s failed, trying next", url)
                    continue
            if last_exc is not None:
                raise last_exc
        return None

    def get_layer(self) -> TileLayerSpec:
        return TileLayerSpec(
            kind="wms",
            url=ERDDAP_WMS_URL,
            layers="Coastlines",
            extra_params={"TRANSPARENT": "TRUE"},
            attribution="NOAA ERDDAP boundary data (GSHHS)",
            opacity=1.0,
        )


class RiversLakesProvider(OceanProvider):
    name = "OpenStreetMap"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict[str, SourcedValue]:
        return {}

    def get_layer(self) -> TileLayerSpec:
        return TileLayerSpec(
            kind="wms",
            url=ERDDAP_WMS_URL,
            layers="LakesAndRivers",
            extra_params={"TRANSPARENT": "TRUE"},
            attribution="NOAA ERDDAP boundary data",
            opacity=1.0,
        )
