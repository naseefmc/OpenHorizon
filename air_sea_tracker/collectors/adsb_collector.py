"""OpenSky REST collector (SDR §6, §22).

Poll-based and quota-limited (400 credits/day on the anonymous free
tier). Uses a RateLimiter to track quota and back off rather than
polling on a fixed short interval regardless of remaining credits.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
DEFAULT_POLL_INTERVAL_SECONDS = 30  # realistic for free tier; see SDR §6-§7


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
                if self._rate_limiter.can_call():
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
                                self._rate_limiter.apply_backoff(60)
                            elif resp.status == 200:
                                data = await resp.json()
                                self._on_state_update(data)
                            else:
                                logger.warning("OpenSky returned status %s", resp.status)
                    except Exception:
                        logger.exception("OpenSky poll failed")
                else:
                    logger.info("OpenSky quota exhausted: %s", self._rate_limiter.quota_summary())

                await asyncio.sleep(self._poll_interval)

    def quota_summary(self) -> str:
        return self._rate_limiter.quota_summary()

    def stop(self) -> None:
        self._stop.set()
