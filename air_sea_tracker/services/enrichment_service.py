"""Public-source ownership/operator enrichment (SDR §12, Phase 4).

Best-effort, source-attributed, confidence-labeled. See SDR §12 and
§20.1 (Responsible Use & Opt-Out Handling) before implementing owner
lookups — LADD-style opt-out lists must be honored and speculative
ownership must never be presented as confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EnrichmentResult:
    field: str
    value: str
    confidence: str  # HIGH | MEDIUM | LOW | UNVERIFIED
    source: str


def research_vessel(mmsi: str | None = None, imo: str | None = None) -> list[EnrichmentResult]:
    # TODO(Phase 4): concrete free sources not yet finalized (SDR §12)
    raise NotImplementedError


def research_aircraft(registration: str | None = None, icao24: str | None = None) -> list[EnrichmentResult]:
    # TODO(Phase 4): concrete free sources not yet finalized (SDR §12)
    raise NotImplementedError
