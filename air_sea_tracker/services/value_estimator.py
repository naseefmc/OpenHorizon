"""Approximate vessel market value estimation (SDR §13-14, Phase 4).

No free source of comparable yacht/vessel sales was identified (they're
held by commercial brokerage sites — SDR §13 explicitly says not to
scrape those). Per SDR §13's own fallback, this is a rough
builder/length/age/type heuristic, not a real valuation — comparable_count
is always 0 and confidence is always LOW, and callers must display that
plainly rather than let this look like a market appraisal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Very rough $/meter of length by category, current-year new-build order
# of magnitude — not calibrated against any actual sales data.
BASE_RATE_PER_METER = {
    "yacht": 700_000,
    "sailing yacht": 200_000,
    "cruise ship": 3_000_000,
    "cargo": 150_000,
    "tanker": 180_000,
    "ferry": 250_000,
    "fishing": 60_000,
}
DEFAULT_RATE_PER_METER = 150_000
ANNUAL_DEPRECIATION = 0.05  # crude straight-ish line, floors at 15% of new-build estimate
MIN_VALUE_FRACTION = 0.15


@dataclass
class ValueEstimate:
    low: float
    high: float
    currency: str
    confidence: str  # always "LOW" here — see module docstring
    comparable_count: int
    note: str


def estimate_vessel_value(
    length_m: float | None, ship_type: str | None, build_year: int | None
) -> ValueEstimate | None:
    if not length_m or length_m <= 0:
        return None

    rate = BASE_RATE_PER_METER.get((ship_type or "").lower(), DEFAULT_RATE_PER_METER)
    base = rate * length_m

    age = max(0, date.today().year - build_year) if build_year else 10  # assume a decade if unknown
    depreciation_factor = max(MIN_VALUE_FRACTION, 1 - ANNUAL_DEPRECIATION * age)
    mid = base * depreciation_factor

    return ValueEstimate(
        low=mid * 0.6,
        high=mid * 1.6,
        currency="USD",
        confidence="LOW",
        comparable_count=0,
        note=(
            "Rough heuristic (length × type rate × age depreciation) — "
            "not based on comparable sales. No free comparable-sales source "
            "is available (SDR §13); treat as an order-of-magnitude estimate only."
        ),
    )
