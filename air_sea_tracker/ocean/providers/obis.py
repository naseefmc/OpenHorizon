"""OBIS (Ocean Biodiversity Information System) marine-life provider (Ocean & Environment SDR §13).

Queries OBIS's public occurrence API against a small bounding-box
polygon around the clicked point — an exact-point query almost never
matches a real observation, whereas a ~10km box reliably does.

OBIS records carry `scientificName` but no vernacular/common name, so
recent observations are shown by scientific name. Sidebar wording must
say "Species observed nearby", never "present now" — these are
historical/recent biodiversity records, not live animal tracking
(SDR §13's explicit requirement).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import aiohttp

from ocean.models.ocean_data import SourcedValue, SpeciesObservation, SpeciesResult, WorldwideSpeciesPoint
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider

logger = logging.getLogger(__name__)

OBIS_URL = "https://api.obis.org/v3/occurrence"
DEFAULT_RADIUS_KM = 10.0
# Sidebar list cap — was 5, which made the "N species" summary count look
# wrong next to a 5-row list. Raised so the list matches the summary for
# any realistic query (the query itself is capped at 100 occurrence records).
MAX_RECENT = 100
WORLDWIDE_DEFAULT_LIMIT = 200
WORLDWIDE_YEARS_BACK = 3  # keep the worldwide overview to recent sightings, not centuries of museum records

# Plain-language classification derived from real OBIS/WoRMS taxonomy
# (class/phylum/order/family on each occurrence record) — not guessed
# per species, so it's only as good as what OBIS reports for that record.
_CLASS_LABELS = {
    "Elasmobranchii": "shark/ray",
    "Chondrichthyes": "shark/ray",
    "Teleostei": "fish",
    "Actinopterygii": "fish",
    "Sarcopterygii": "fish",
    "Reptilia": "reptile",
    "Aves": "seabird",
    "Gastropoda": "snail/mollusk",
    "Bivalvia": "bivalve/mollusk",
    "Cephalopoda": "octopus/squid",
    "Echinoidea": "sea urchin",
    "Asteroidea": "starfish",
    "Holothuroidea": "sea cucumber",
    "Malacostraca": "crab/shrimp",
    "Anthozoa": "coral/anemone",
    "Demospongiae": "sponge",
    "Polychaeta": "marine worm",
}
_PHYLUM_LABELS = {
    "Mollusca": "mollusk",
    "Cnidaria": "coral/cnidarian",
    "Echinodermata": "echinoderm",
    "Arthropoda": "crustacean/arthropod",
    "Porifera": "sponge",
    "Annelida": "marine worm",
}


def _classify(rec: dict) -> str | None:
    klass = rec.get("class")
    if klass == "Mammalia":
        order = rec.get("order") or ""
        # WoRMS now nests whales/dolphins under order Cetartiodactyla with
        # Cetacea demoted to infraorder, so "order" alone no longer catches them.
        infraorder = rec.get("infraorder") or ""
        if "Cetacea" in order or "Cetacea" in infraorder:
            return "dolphin" if rec.get("family") == "Delphinidae" else "whale"
        if "Carnivora" in order:
            return "seal/sea lion"
        return "marine mammal"
    if klass in _CLASS_LABELS:
        return _CLASS_LABELS[klass]
    phylum = rec.get("phylum")
    if phylum in _PHYLUM_LABELS:
        return _PHYLUM_LABELS[phylum]
    return klass or phylum or rec.get("kingdom")


def _event_date(rec: dict) -> str | None:
    raw = rec.get("eventDate")
    if not raw:
        return None
    # Some OBIS records carry a date *range* ("2023-07-13T22:00:00Z/2023-07-13T23:00:00Z");
    # take the start of the range and drop the time-of-day for display.
    return raw.split("/")[0][:10]


def _bbox_polygon(lat: float, lon: float, radius_km: float) -> str:
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.1))
    return (
        f"POLYGON(({lon - dlon} {lat - dlat}, {lon + dlon} {lat - dlat}, "
        f"{lon + dlon} {lat + dlat}, {lon - dlon} {lat + dlat}, {lon - dlon} {lat - dlat}))"
    )


class ObisProvider(OceanProvider):
    name = "OBIS"

    def __init__(self, radius_km: float = DEFAULT_RADIUS_KM) -> None:
        self.radius_km = radius_km

    async def get_point_data(
        self, lat: float, lon: float, when: datetime | None = None, taxon_filter: str | None = None
    ) -> dict:
        try:
            result = await self._query(lat, lon, taxon_filter)
        except Exception:
            logger.exception("OBIS query failed")
            return {
                "species": SpeciesResult(
                    radius_km=self.radius_km,
                    records=0,
                    species_count=0,
                    source=self.name,
                    note="OBIS service unreachable",
                )
            }
        return {"species": result}

    async def _query(self, lat: float, lon: float, taxon_filter: str | None) -> SpeciesResult:
        params = {"geometry": _bbox_polygon(lat, lon, self.radius_km), "size": 100}
        if taxon_filter:
            params["scientificname"] = taxon_filter
        async with aiohttp.ClientSession() as session:
            async with session.get(
                OBIS_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        results = data.get("results", [])
        total = data.get("total", len(results))

        # sci name -> {classification, observed_on}; observed_on tracks the
        # *latest* eventDate seen across all matching records for that
        # species, so the sidebar can show "last observed" per species.
        species_info: dict[str, dict[str, str | None]] = {}
        for rec in results:
            sci = rec.get("scientificName")
            if not sci:
                continue
            date = _event_date(rec)
            entry = species_info.get(sci)
            if entry is None:
                species_info[sci] = {"classification": _classify(rec), "observed_on": date}
            elif date and (entry["observed_on"] is None or date > entry["observed_on"]):
                entry["observed_on"] = date

        recent = [
            SpeciesObservation(scientific_name=sci, classification=info["classification"], observed_on=info["observed_on"])
            for sci, info in list(species_info.items())[:MAX_RECENT]
        ]

        return SpeciesResult(
            radius_km=self.radius_km,
            records=total,
            species_count=len(species_info),
            recent=recent,
            source=self.name,
            note=None
            if total
            else (
                f"No {taxon_filter} observations recorded nearby" if taxon_filter else "No species observations recorded nearby"
            ),
        )

    async def query_worldwide(self, taxon: str, limit: int = WORLDWIDE_DEFAULT_LIMIT) -> list[WorldwideSpeciesPoint]:
        """Individual, geolocated sightings of `taxon` from anywhere in the
        world (last WORLDWIDE_YEARS_BACK years), for the map's worldwide
        species-search overlay — not gated by a clicked point at all."""
        start = (datetime.now(timezone.utc) - timedelta(days=365 * WORLDWIDE_YEARS_BACK)).strftime("%Y-%m-%d")
        params = {"scientificname": taxon, "size": limit, "startdate": start}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                OBIS_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        points: list[WorldwideSpeciesPoint] = []
        for rec in data.get("results", []):
            lat, lon, sci = rec.get("decimalLatitude"), rec.get("decimalLongitude"), rec.get("scientificName")
            if lat is None or lon is None or not sci:
                continue
            points.append(
                WorldwideSpeciesPoint(
                    scientific_name=sci,
                    latitude=lat,
                    longitude=lon,
                    classification=_classify(rec),
                    observed_on=_event_date(rec),
                )
            )
        return points
