"""Public-source ownership/operator enrichment (SDR §12, Phase 4).

Best-effort, source-attributed, confidence-labeled. See SDR §12 and
§20.1 (Responsible Use & Opt-Out Handling) — LADD-style opt-out lists
must be honored and speculative ownership must never be presented as
confirmed.

Sources, verified before use (not guessed):
  - Vessels: Wikidata SPARQL, matched by IMO number (P458) — a precise,
    unique identifier, so a match is HIGH confidence. Coverage is
    real but partial: only vessels notable enough to have a Wikidata
    entry (cruise ships, notable yachts, historic ships) — most cargo/
    small vessels will return no match, which is reported honestly as
    "not found" rather than guessed at.
  - Aircraft: FAA Releasable Aircraft Registry (US N-numbers only,
    public record). This endpoint blocks automated requests from at
    least some environments (confirmed 403/503 with browser-like
    headers during development) — treat failure as "registry
    unreachable", not "no data", and never let it crash the caller.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
from platformdirs import user_cache_dir

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
FAA_REGISTRY_URL = "https://registry.faa.gov/database/ReleasableAircraft.zip"
FAA_CACHE_TTL_SECONDS = 7 * 24 * 3600  # SDR §26.2-adjacent: registry refreshes daily, cache a week
USER_AGENT = "OpenHorizonAirSeaTracker/1.0 (https://github.com/naseefmc/OpenHorizon)"


@dataclass
class EnrichmentField:
    label: str
    value: str
    confidence: str  # HIGH | MEDIUM | LOW | UNVERIFIED
    source: str


@dataclass
class EnrichmentResult:
    found: bool
    fields: list[EnrichmentField] = field(default_factory=list)
    image_url: str | None = None
    note: str = ""


async def research_vessel(mmsi: str | None = None, imo: str | None = None) -> EnrichmentResult:
    if not imo:
        return EnrichmentResult(found=False, note="No IMO number known for this vessel — Wikidata lookup needs one.")

    query = f"""
    SELECT ?itemLabel ?builderLabel ?operatorLabel ?ownerLabel ?countryLabel ?inception ?tonnage ?lengthVal ?image WHERE {{
      ?item wdt:P458 "{imo}".
      OPTIONAL {{ ?item wdt:P176 ?builder. }}
      OPTIONAL {{ ?item wdt:P137 ?operator. }}
      OPTIONAL {{ ?item wdt:P127 ?owner. }}
      OPTIONAL {{ ?item wdt:P17 ?country. }}
      OPTIONAL {{ ?item wdt:P571 ?inception. }}
      OPTIONAL {{ ?item wdt:P1093 ?tonnage. }}
      OPTIONAL {{ ?item wdt:P2043 ?lengthVal. }}
      OPTIONAL {{ ?item wdt:P18 ?image. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 1
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                WIKIDATA_SPARQL_URL,
                params={"query": query},
                headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status != 200:
                    return EnrichmentResult(found=False, note=f"Wikidata returned status {resp.status}")
                data = await resp.json()
    except Exception:
        logger.exception("Wikidata lookup failed")
        return EnrichmentResult(found=False, note="Wikidata lookup failed (network error)")

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return EnrichmentResult(found=False, note=f"No Wikidata entry found for IMO {imo}")

    row = bindings[0]

    def val(key: str) -> str | None:
        return row.get(key, {}).get("value")

    fields: list[EnrichmentField] = []
    src = "Wikidata (wikidata.org), matched by IMO — HIGH confidence identifier match"
    if val("builderLabel"):
        fields.append(EnrichmentField("Builder", val("builderLabel"), "HIGH", src))
    if val("operatorLabel"):
        fields.append(EnrichmentField("OPERATOR", val("operatorLabel"), "MEDIUM", src))
    if val("ownerLabel"):
        fields.append(EnrichmentField("REPORTED OWNER", val("ownerLabel"), "MEDIUM", src))
    if val("countryLabel"):
        fields.append(EnrichmentField("Country", val("countryLabel"), "MEDIUM", src))
    if val("inception"):
        fields.append(EnrichmentField("Built", val("inception")[:10], "HIGH", src))
    if val("tonnage"):
        fields.append(EnrichmentField("Gross tonnage", val("tonnage"), "MEDIUM", src))
    if val("lengthVal"):
        fields.append(EnrichmentField("Length", f"{val('lengthVal')} m", "MEDIUM", src))

    if not fields:
        return EnrichmentResult(found=False, note=f"Wikidata has an entry for IMO {imo} but no usable fields")

    return EnrichmentResult(found=True, fields=fields, image_url=val("image"))


async def research_aircraft(registration: str | None = None, icao24: str | None = None) -> EnrichmentResult:
    if not registration or not registration.upper().startswith("N"):
        return EnrichmentResult(
            found=False,
            note="Only US-registered aircraft (N-numbers) are supported — no other free registry source is wired up.",
        )

    try:
        index = await _get_faa_index()
    except Exception:
        logger.exception("FAA registry fetch failed")
        return EnrichmentResult(found=False, note="FAA registry unreachable right now (network/availability issue)")

    row = index.get(registration.upper().lstrip("N"))
    if row is None:
        return EnrichmentResult(found=False, note=f"{registration} not found in the FAA registry")

    src = "FAA Releasable Aircraft Registry (registry.faa.gov), public record"
    fields = [
        EnrichmentField("REGISTERED OWNER", row["name"], "HIGH", src),
        EnrichmentField("Location", f"{row['city']}, {row['state']}", "HIGH", src),
        EnrichmentField("Year mfr.", row["year_mfr"], "HIGH", src),
    ]
    return EnrichmentResult(found=True, fields=[f for f in fields if f.value.strip(", ")])


_faa_index_cache: dict | None = None


async def _get_faa_index() -> dict[str, dict]:
    global _faa_index_cache
    if _faa_index_cache is not None:
        return _faa_index_cache

    cache_path = Path(user_cache_dir("AirSeaLiveTracker", "AirSeaTracker")) / "faa_registry.json"
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime) < FAA_CACHE_TTL_SECONDS:
        _faa_index_cache = json.loads(cache_path.read_text())
        return _faa_index_cache

    async with aiohttp.ClientSession() as session:
        async with session.get(
            FAA_REGISTRY_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OpenHorizonAirSeaTracker/1.0)"},
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"FAA registry returned status {resp.status}")
            raw = await resp.read()

    index: dict[str, dict] = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with zf.open("MASTER.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"))
            for row in reader:
                n_number = (row.get("N-NUMBER") or "").strip()
                if not n_number:
                    continue
                index[n_number] = {
                    "name": (row.get("NAME") or "").strip(),
                    "city": (row.get("CITY") or "").strip(),
                    "state": (row.get("STATE") or "").strip(),
                    "year_mfr": (row.get("YEAR MFR") or "").strip(),
                }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(index))
    _faa_index_cache = index
    return index
