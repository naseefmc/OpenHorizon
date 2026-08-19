"""Selected-location model (Ocean & Environment SDR §5).

Every map click on the Ocean & Environment tab produces one of these;
the Ocean Controller fans it out to every enabled/required provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SelectedLocation:
    latitude: float
    longitude: float
    timestamp: datetime

    @classmethod
    def now(cls, latitude: float, longitude: float) -> "SelectedLocation":
        return cls(latitude=latitude, longitude=longitude, timestamp=datetime.now(timezone.utc))
