"""Runs all configured AIS providers concurrently and aggregates their health.

Each provider contributes to the same normalized Vessel stream; a
provider that isn't configured (missing credentials) simply never
starts, and one that goes silent is demoted to NO_DATA by its own
periodic `check_silence()` rather than being torn down — the next poll
tick or reconnect may bring it back to LIVE on its own.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from models.vessel import Vessel
from services.ais_providers.aishub_provider import AISHubProvider
from services.ais_providers.aisstream_provider import AISStreamProvider
from services.ais_providers.barentswatch_provider import BarentsWatchProvider
from services.ais_providers.base import AISProvider, ProviderStatus
from services.ais_providers.vesselapi_provider import VesselApiProvider

logger = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL_SECONDS = 10


def default_providers() -> list[AISProvider]:
    return [AISStreamProvider(), BarentsWatchProvider(), AISHubProvider(), VesselApiProvider()]


class AISProviderManager:
    def __init__(
        self,
        on_vessel_update: Callable[[Vessel], None],
        on_provider_status_change: Callable[[str, ProviderStatus], None] | None = None,
        providers: list[AISProvider] | None = None,
    ) -> None:
        self._on_vessel_update = on_vessel_update
        self._on_provider_status_change = on_provider_status_change
        self.providers = providers if providers is not None else default_providers()
        for provider in self.providers:
            provider.on_status_change = self._handle_status_change
            provider.is_free_source_live = self._any_free_provider_live
        self._tasks: list[asyncio.Task] = []
        self._health_task: asyncio.Task | None = None

    def _handle_status_change(self, name: str, status: ProviderStatus) -> None:
        if self._on_provider_status_change:
            self._on_provider_status_change(name, status)

    def _any_free_provider_live(self) -> bool:
        """Lets a rate-limited provider (e.g. VesselAPI) defer to a free
        source that's already delivering data for this area, so its
        metered budget is only spent when the free tier isn't covering."""
        return any(p.is_free_tier and p.status == ProviderStatus.LIVE for p in self.providers)

    def start(self, bbox: tuple[float, float, float, float]) -> None:
        self.stop()
        for provider in self.providers:
            self._tasks.append(asyncio.ensure_future(self._run_provider(provider, bbox)))
        self._health_task = asyncio.ensure_future(self._health_loop())

    async def _run_provider(self, provider: AISProvider, bbox: tuple[float, float, float, float]) -> None:
        try:
            await provider.run(self._on_vessel_update, bbox)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("%s provider crashed", provider.name)
            provider._set_status(ProviderStatus.OFFLINE)  # noqa: SLF001 — manager owns provider lifecycle

    async def _health_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
                for provider in self.providers:
                    provider.check_silence()
        except asyncio.CancelledError:
            pass

    def stop(self) -> None:
        for provider in self.providers:
            if provider.status != ProviderStatus.DISABLED:
                try:
                    provider.stop()
                except NotImplementedError:
                    pass
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        if self._health_task is not None:
            self._health_task.cancel()
            self._health_task = None

    def statuses(self) -> list[tuple[str, ProviderStatus]]:
        return [(p.name, p.status) for p in self.providers]
