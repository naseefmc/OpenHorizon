"""In-memory live target cache (SDR §26.1).

Keys: aircraft:{ICAO24}, vessel:{MMSI or IMO}
Default expiry: aircraft 120s, vessel 600s. Expired targets drop off
the live map but remain in position_history.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

AIRCRAFT_TTL_SECONDS = 120
VESSEL_TTL_SECONDS = 600


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class LiveTargetCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}

    def put(self, key: str, value: Any, ttl_seconds: float) -> None:
        self._entries[key] = CacheEntry(value=value, expires_at=time.time() + ttl_seconds)

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._entries[key]
            return None
        return entry.value

    def is_stale(self, key: str) -> bool:
        return self.get(key) is None and key in self._entries

    def purge_expired(self) -> int:
        now = time.time()
        expired = [k for k, e in self._entries.items() if now > e.expires_at]
        for k in expired:
            del self._entries[k]
        return len(expired)

    def values(self) -> list[Any]:
        self.purge_expired()
        return [e.value for e in self._entries.values()]

    def __len__(self) -> int:
        return len(self._entries)
