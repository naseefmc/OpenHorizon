"""Approximate vessel/aircraft market value estimation (SDR §13-14, Phase 4).

Output must always be labeled an estimate, never a formal valuation.
Deferred/scoped-down if no free source of comparable sales is
identified (SDR §13) rather than scraping commercial listings.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValueEstimate:
    low: float
    high: float
    currency: str
    confidence: str  # HIGH | MEDIUM | LOW
    comparable_count: int


def estimate_vessel_value(**specs) -> ValueEstimate | None:
    # TODO(Phase 4): no free comparable-sales source identified yet (SDR §13)
    raise NotImplementedError
