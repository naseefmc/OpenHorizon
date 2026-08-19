"""Open-Meteo Marine API provider — waves and ocean currents (Ocean & Environment SDR §11).

Substitutes for the SDR's named primary Phase 2 provider, Copernicus
Marine, which requires a registered account and its own client tooling
rather than a simple keyless REST call. Open-Meteo is free, keyless,
and global, at the cost of being a downstream/derived product rather
than Copernicus's own analysis — attributed honestly as "Open-Meteo"
throughout, never mislabeled as Copernicus.

`past_days=1, forecast_days=3` gives roughly a -24h..+72h hourly window,
comfortably covering the Time Control range (SDR §14) around "now".
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiohttp

from ocean.models.ocean_data import STATUS_FORECAST, STATUS_NEAR_REAL_TIME, CurrentData, SourcedValue, WaveData
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider

logger = logging.getLogger(__name__)

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
HOURLY_FIELDS = "wave_height,wave_direction,wave_period,ocean_current_velocity,ocean_current_direction"
KMH_TO_KN = 0.539957


def _nearest_index(times: list[str], when: datetime | None) -> int | None:
    if not times:
        return None
    target = (when or datetime.now(timezone.utc)).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    best_i, best_diff = 0, None
    for i, t in enumerate(times):
        diff = abs((datetime.fromisoformat(t) - target).total_seconds())
        if best_diff is None or diff < best_diff:
            best_i, best_diff = i, diff
    return best_i


def _status_for(times: list[str], index: int) -> str:
    dt = datetime.fromisoformat(times[index])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return STATUS_FORECAST if dt > now else STATUS_NEAR_REAL_TIME


class OpenMeteoMarineProvider(OceanProvider):
    name = "Open-Meteo"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": HOURLY_FIELDS,
            "timezone": "UTC",
            "past_days": 1,
            "forecast_days": 3,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    MARINE_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
        except Exception:
            logger.exception("Open-Meteo marine query failed")
            unavailable = SourcedValue.unavailable(self.name, "Open-Meteo marine service unreachable")
            return {
                "waves": WaveData(unavailable, unavailable, unavailable),
                "current": CurrentData(unavailable, unavailable),
            }

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        idx = _nearest_index(times, when)
        if idx is None:
            unavailable = SourcedValue.unavailable(self.name, "No marine forecast data at this point")
            return {
                "waves": WaveData(unavailable, unavailable, unavailable),
                "current": CurrentData(unavailable, unavailable),
            }

        status = _status_for(times, idx)
        timestamp = times[idx] + ":00Z"

        def sv(field: str, unit: str) -> SourcedValue:
            values = hourly.get(field, [])
            value = values[idx] if idx < len(values) else None
            if value is None:
                return SourcedValue.unavailable(self.name, "No data at this hour")
            return SourcedValue(value=round(value, 2), unit=unit, source=self.name, status=status, timestamp=timestamp)

        waves = WaveData(
            height_m=sv("wave_height", "m"),
            direction_deg=sv("wave_direction", "°"),
            period_s=sv("wave_period", "s"),
        )

        current_speed = sv("ocean_current_velocity", "km/h")
        if current_speed.available:
            current_speed = SourcedValue(
                value=round(current_speed.value * KMH_TO_KN, 2),
                unit="kn",
                source=self.name,
                status=status,
                timestamp=timestamp,
            )
        current = CurrentData(speed_kn=current_speed, direction_deg=sv("ocean_current_direction", "°"))

        return {"waves": waves, "current": current}
