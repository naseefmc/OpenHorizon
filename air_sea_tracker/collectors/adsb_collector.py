"""OpenSky REST collector (SDR §6, §22).

Poll-based and quota-limited (400 credits/day on the anonymous free
tier). Uses a RateLimiter to track quota and back off rather than
polling on a fixed short interval regardless of remaining credits.

OpenSky's anonymous tier also enforces its own server-side per-IP
throttle, separate from and much stricter than the simple 400/day
budget — a 429 there can carry an hours-long Retry-After, so on a 429
this reads and respects the actual header instead of a flat guess.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
DEFAULT_POLL_INTERVAL_SECONDS = 30  # realistic for free tier; see SDR §6-§7
FALLBACK_BACKOFF_SECONDS = 60  # used only if the 429 response has no retry-after header


class ADSBCollector:
    def __init__(
        self,
        on_state_update,
        bbox: tuple[float, float, float, float] | None = None,
        poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        """bbox: (lat_min, lon_min, lat_max, lon_max). A bounded query both
        matches Nearby Mode's scope and reduces OpenSky credit cost versus
        a global /states/all poll (SDR §6)."""
        self._on_state_update = on_state_update
        self._bbox = bbox
        self._poll_interval = poll_interval
        self._rate_limiter = RateLimiter(name="opensky", daily_limit=400)
        self._stop = asyncio.Event()

    async def run(self) -> None:
        async with aiohttp.ClientSession() as session:
            while not self._stop.is_set():
                backoff_remaining = self._rate_limiter.backoff_seconds_remaining()
                if backoff_remaining > 0:
                    logger.info(
                        "OpenSky server-side rate limit active; %.0fs remaining (persists across restarts)",
                        backoff_remaining,
                    )
                elif not self._rate_limiter.can_call():
                    logger.info("OpenSky daily budget exhausted: %s", self._rate_limiter.quota_summary())
                else:
                    try:
                        params = {}
                        if self._bbox:
                            lat_min, lon_min, lat_max, lon_max = self._bbox
                            params = {"lamin": lat_min, "lomin": lon_min, "lamax": lat_max, "lomax": lon_max}
                        async with session.get(
                            OPENSKY_STATES_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)
                        ) as resp:
                            self._rate_limiter.record_call()
                            if resp.status == 429:
                                retry_after = self._parse_retry_after(resp.headers)
                                self._rate_limiter.apply_backoff(retry_after)
                                logger.warning("OpenSky rate-limited us (429); backing off %.0fs", retry_after)
                            elif resp.status == 200:
                                data = await resp.json()
                                self._on_state_update(data)
                            else:
                                logger.warning("OpenSky returned status %s", resp.status)
                    except Exception:
                        logger.exception("OpenSky poll failed")

                await asyncio.sleep(self._poll_interval)

    @staticmethod
    def _parse_retry_after(headers) -> float:
        for key in ("X-Rate-Limit-Retry-After-Seconds", "Retry-After"):
            value = headers.get(key)
            if value is not None:
                try:
                    return float(value)
                except ValueError:
                    pass
        return FALLBACK_BACKOFF_SECONDS

    def quota_summary(self) -> str:
        return self._rate_limiter.quota_summary()

    def stop(self) -> None:
        self._stop.set()
