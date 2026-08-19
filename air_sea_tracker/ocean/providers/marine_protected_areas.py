"""Marine protected area provider (Ocean & Environment SDR §11).

The official Protected Planet REST API requires a registered token, but
UNEP-WCMC — the same body that maintains the WDPA (World Database on
Protected Areas) behind Protected Planet — separately publishes the
identical, monthly-updated WDPA polygon data as a public ArcGIS
FeatureServer with no authentication at all (verified live: a query
over the Great Barrier Reef correctly returns "Great Barrier Reef,
World Heritage Site"). That's the source used here instead of gating
this layer behind a token nobody's supplied yet.

Point-in-polygon queries against this server error generically with
esriGeometryPoint (a quirk of this specific service); a small envelope
(bounding box) around the point works reliably and is used instead.
"""

from __future__ import annotations

import logging
from datetime import datetime

import aiohttp

from ocean.models.ocean_data import STATUS_STATIC, SourcedValue
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider

logger = logging.getLogger(__name__)

QUERY_URL = (
    "https://data-gis.unep-wcmc.org/server/rest/services/ProtectedSites/WDPA_Marine_and_Coastal/FeatureServer/1/query"
)
BOX_DEGREES = 0.02  # ~2km — small enough to identify "this point", large enough to tolerate coordinate jitter


class MarineProtectedAreaProvider(OceanProvider):
    name = "WDPA / UNEP-WCMC"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict[str, SourcedValue]:
        try:
            areas = await self._query(lat, lon)
        except Exception:
            logger.exception("WDPA marine protected area query failed")
            return {"marine_protected_area": SourcedValue.unavailable(self.name, "WDPA service unreachable")}

        if not areas:
            return {
                "marine_protected_area": SourcedValue(
                    value="Not within a known protected area", source=self.name, status=STATUS_STATIC
                )
            }

        unique_names = list(dict.fromkeys(a["name"] for a in areas))
        names = ", ".join(unique_names[:3])
        designations = "; ".join(f"{a['name']} — {a['designation']}" for a in areas[:3] if a["designation"])
        return {
            "marine_protected_area": SourcedValue(
                value=names, source=self.name, status=STATUS_STATIC, note=designations or None
            )
        }

    async def _query(self, lat: float, lon: float) -> list[dict]:
        half = BOX_DEGREES / 2
        params = {
            "geometry": f"{lon - half},{lat - half},{lon + half},{lat + half}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "name_eng,desig_eng",
            "returnGeometry": "false",
            "f": "json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                QUERY_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        if "error" in data:
            raise RuntimeError(f"WDPA query error: {data['error']}")

        areas = []
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            name = attrs.get("name_eng")
            if name:
                areas.append({"name": name, "designation": attrs.get("desig_eng")})
        return areas
