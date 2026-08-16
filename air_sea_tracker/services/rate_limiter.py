"""API rate-limit / daily quota tracking (SDR §22, §27.6).

Sits in front of poll-based sources (e.g. OpenSky's free REST tier,
400 credits/day). WebSocket push sources (AISStream) don't consume
quota the same way and generally don't need this.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from config.settings import Settings


@dataclass
class QuotaState:
    used: int = 0
    limit: int = 400
    resets_at: float = 0.0  # unix timestamp of next daily reset

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


class RateLimiter:
    """Tracks quota usage for one named source and applies backoff.

    The backoff deadline is persisted (SDR §27) — not just held in memory —
    because a server-side 429 (e.g. OpenSky's real per-IP throttle, which
    can hand out an hours-long Retry-After) must survive an app restart.
    An in-memory-only backoff would let every relaunch immediately retry
    and get blocked again, which at best does nothing and at worst resets
    or extends the server's own cooldown timer.
    """

    def __init__(self, name: str, daily_limit: int) -> None:
        self.name = name
        self.state = QuotaState(limit=daily_limit, resets_at=self._next_midnight_utc())
        self._settings = Settings()
        self._backoff_key = f"backoff/{name}/until"

    @staticmethod
    def _next_midnight_utc() -> float:
        now = time.time()
        return (now // 86400 + 1) * 86400

    def _maybe_reset(self) -> None:
        if time.time() >= self.state.resets_at:
            self.state.used = 0
            self.state.resets_at = self._next_midnight_utc()

    def backoff_seconds_remaining(self) -> float:
        until = self._settings.get(self._backoff_key)
        if until is None:
            return 0.0
        return max(0.0, float(until) - time.time())

    def can_call(self, cost: int = 1) -> bool:
        self._maybe_reset()
        if self.backoff_seconds_remaining() > 0:
            return False
        return self.state.remaining >= cost

    def record_call(self, cost: int = 1) -> None:
        self._maybe_reset()
        self.state.used += cost

    def apply_backoff(self, seconds: float) -> None:
        self._settings.set(self._backoff_key, time.time() + seconds)

    def quota_summary(self) -> str:
        self._maybe_reset()
        return f"{self.state.used} / {self.state.limit} credits today"


class MonthlyRateLimiter:
    """Tracks quota for a source billed per calendar month (e.g. VesselAPI's
    150 calls/month free tier), persisted via Settings/QSettings (SDR §27)
    so the count survives app restarts instead of quietly resetting every
    relaunch — the whole point of counting a monthly cap this small."""

    def __init__(self, name: str, monthly_limit: int) -> None:
        self.name = name
        self.limit = monthly_limit
        self._settings = Settings()
        self._used_key = f"quota/{name}/used"
        self._period_key = f"quota/{name}/period"

    @staticmethod
    def _current_period() -> str:
        return time.strftime("%Y-%m", time.gmtime())

    def _sync_period(self) -> None:
        current = self._current_period()
        if self._settings.get(self._period_key) != current:
            self._settings.set(self._period_key, current)
            self._settings.set(self._used_key, 0)

    @property
    def used(self) -> int:
        self._sync_period()
        return int(self._settings.get(self._used_key, 0))

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def can_call(self, cost: int = 1) -> bool:
        return self.remaining >= cost

    def record_call(self, cost: int = 1) -> None:
        self._sync_period()
        self._settings.set(self._used_key, self.used + cost)

    def quota_summary(self) -> str:
        return f"{self.used} / {self.limit} calls this month"


class PersistentPollGate:
    """Ensures at least `min_interval_seconds` of real wall-clock time has
    passed since a poll-based provider's last call for a given area,
    persisted via Settings so it survives app restarts — otherwise every
    relaunch fires an immediate request regardless of how recently the
    app was last open, which is wasteful against a metered/rate-limited
    source.

    Keyed by a coarse (~0.5°, ~55km) location bucket rather than just the
    provider name: gating purely on wall-clock time would otherwise block
    a genuinely new observer location (e.g. after pressing "Set" to move
    to a different area) using a timer left over from a previous,
    unrelated location — that's a stale-cache bug, not a quota saving.
    """

    def __init__(self, name: str, min_interval_seconds: float) -> None:
        self._settings = Settings()
        self._name = name
        self.min_interval_seconds = min_interval_seconds

    @staticmethod
    def _location_bucket(lat: float, lon: float) -> str:
        return f"{round(lat * 2) / 2:.1f},{round(lon * 2) / 2:.1f}"

    def _key(self, lat: float, lon: float) -> str:
        return f"poll_gate/{self._name}/{self._location_bucket(lat, lon)}/last_call_at"

    def seconds_until_ready(self, lat: float, lon: float) -> float:
        last = self._settings.get(self._key(lat, lon))
        if last is None:
            return 0.0
        elapsed = time.time() - float(last)
        return max(0.0, self.min_interval_seconds - elapsed)

    def record_call(self, lat: float, lon: float) -> None:
        self._settings.set(self._key(lat, lon), time.time())
